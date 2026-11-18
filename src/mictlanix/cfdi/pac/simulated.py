"""A simulated PAC: the ``PacClient`` interface, offline, with every outcome configurable."""

from __future__ import annotations

import asyncio
import base64
import functools
import json
import secrets
import uuid
from collections.abc import Callable, Coroutine
from datetime import datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from typing import Any, Concatenate, Protocol

from lxml import etree

from mictlanix.cfdi import _mexico, tfd11
from mictlanix.cfdi._xml import CFDI40, XSI, serialize
from mictlanix.cfdi.pac._errors import PacRejected, PacTimeout, PacUnavailable
from mictlanix.cfdi.pac._input import Sealed, check, reject
from mictlanix.cfdi.pac._interface import (
    CancellationAnswer,
    CancellationRequest,
    PacClient,
    Stamp,
    stamp_of,
)

SIMULATED_PAC_RFC = 'SIM010101SI0'
_SAT_CERTIFICATE = '00001000000000000000'
_DEFAULT_CODE = 'CFDI40999'
_DEFAULT_MESSAGE = 'Rechazo simulado'
_WITHOUT_ACCEPTANCE = timedelta(hours=24)


class _SatState(StrEnum):
    """The simulated SAT's state of a UUID."""

    VALID = 'valid'
    CANCELLED = 'cancelled'


class _Cancellability(StrEnum):
    WITHOUT_ACCEPTANCE = 'without_acceptance'
    WITH_ACCEPTANCE = 'with_acceptance'
    NOT_CANCELLABLE = 'not_cancellable'


class _CancellationStatus(StrEnum):
    NONE = 'none'
    PENDING = 'pending'
    ACCEPTED = 'accepted'
    REJECTED = 'rejected'
    EXPIRED = 'expired'


class StampOutcome(StrEnum):
    """The outcome of the next ``stamp`` of a document."""

    STAMPED = 'stamped'
    REJECTED = 'rejected'
    UNAVAILABLE = 'unavailable'
    TIMEOUT_STAMPED = 'timeout_stamped'
    TIMEOUT_NOT_STAMPED = 'timeout_not_stamped'


class CancellationOutcome(StrEnum):
    """The outcome of the next ``request_cancellation`` of a UUID."""

    ACCEPTED = 'accepted'
    PENDING = 'pending'
    NOT_CANCELLABLE = 'not_cancellable'
    REJECTED = 'rejected'
    UNAVAILABLE = 'unavailable'
    TIMEOUT = 'timeout'


class ReceiverAnswer(StrEnum):
    """The recipient's answer to a pending cancellation."""

    ACCEPT = 'accept'
    REJECT = 'reject'
    EXPIRE = 'expire'


class SimulatorStore(Protocol):
    """Where a simulated PAC keeps its state: string values under string keys.

    The keys and values are the simulator's own; a store only keeps them. Share one store to
    share one simulated PAC's state between instances, in one process or several.
    """

    async def get(self, key: str) -> str | None: ...

    async def set(self, key: str, value: str) -> None: ...


class InMemoryStore:
    """A ``SimulatorStore`` in a dict, the default."""

    def __init__(self) -> None:
        self._values: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self._values.get(key)

    async def set(self, key: str, value: str) -> None:
        self._values[key] = value


def _locked[**P, R](
    method: Callable[Concatenate[SimulatedPac, P], Coroutine[Any, Any, R]],
) -> Callable[Concatenate[SimulatedPac, P], Coroutine[Any, Any, R]]:
    """Serialize the instance's operations, so concurrent calls never stamp twice."""

    async def run(self: SimulatedPac, /, *args: P.args, **kwargs: P.kwargs) -> R:
        async with self._lock:
            return await method(self, *args, **kwargs)

    functools.update_wrapper(run, method)
    return run


class SimulatedPac:
    """A PAC that stamps and cancels offline, for development and tests."""

    def __init__(
        self,
        store: SimulatorStore | None = None,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        """``store`` holds the state (a new ``InMemoryStore`` when omitted); ``clock`` returns
        naive Mexico City time (the current time when omitted).

        One instance serializes its own operations; separate instances do not lock each other.
        """
        self._store: SimulatorStore = InMemoryStore() if store is None else store
        self._clock = clock or _mexico.now
        self._lock = asyncio.Lock()

    async def _get(self, key: str) -> dict[str, Any]:
        try:
            raw = await self._store.get(key)
            record = {} if raw is None else json.loads(raw)
        except Exception:
            raise PacUnavailable() from None
        if not isinstance(record, dict):
            raise PacUnavailable() from None
        return record

    async def _set(self, key: str, record: dict[str, Any]) -> None:
        try:
            await self._store.set(key, json.dumps(record))
        except Exception:
            raise PacUnavailable() from None

    async def _known(self, sealed_xml: object) -> tuple[Sealed, dict[str, Any]]:
        """The checked document and its record; ``307`` for a TFD this PAC has no record of."""
        sealed = check(sealed_xml)
        record = await self._get(sealed.key)
        if record.get('stamped_xml') is None and sealed.has_timbre():
            reject('307', 'the document carries a stamp this PAC has no record of')
        return sealed, record

    @_locked
    async def stamp(self, sealed_xml: bytes) -> Stamp:
        sealed, record = await self._known(sealed_xml)
        outcome = record.pop('next_stamp', None)
        code = record.pop('code', None) or _DEFAULT_CODE
        message = record.pop('message', None) or _DEFAULT_MESSAGE
        stamped = record.get('stamped_xml')
        makes_stamp = stamped is None and outcome in (
            None,
            StampOutcome.STAMPED,
            StampOutcome.TIMEOUT_STAMPED,
        )
        if makes_stamp:
            record['stamped_xml'] = self._stamped_xml(sealed).decode('utf-8')
            await self._record_uuid(sealed, stamp_of(record['stamped_xml'].encode('utf-8')))
        if makes_stamp or outcome is not None:
            await self._set(sealed.key, record)
        if outcome == StampOutcome.REJECTED:
            raise PacRejected(code, message)
        if outcome == StampOutcome.UNAVAILABLE:
            raise PacUnavailable()
        if outcome in (StampOutcome.TIMEOUT_STAMPED, StampOutcome.TIMEOUT_NOT_STAMPED):
            raise PacTimeout()
        return stamp_of(record['stamped_xml'].encode('utf-8'))

    @_locked
    async def find_stamp(self, sealed_xml: bytes) -> Stamp | None:
        sealed = check(sealed_xml)
        stamped = (await self._get(sealed.key)).get('stamped_xml')
        return None if stamped is None else stamp_of(stamped.encode('utf-8'))

    @_locked
    async def configure_stamp(
        self,
        sealed_xml: bytes,
        outcome: StampOutcome,
        *,
        code: str | None = None,
        message: str | None = None,
    ) -> None:
        """The outcome of the next ``stamp`` of this document only."""
        sealed, record = await self._known(sealed_xml)
        record.update(next_stamp=StampOutcome(outcome).value, code=code, message=message)
        await self._set(sealed.key, record)

    async def _record_uuid(self, sealed: Sealed, stamp: Stamp) -> None:
        """The stamped UUID's record, written before the seal's (research.md R11)."""
        comprobante = sealed.comprobante
        await self._set(
            'uuid:' + stamp.timbre.UUID,
            {
                'issuer_rfc': comprobante.Emisor.Rfc,
                'recipient_rfc': comprobante.Receptor.Rfc,
                'total': str(comprobante.Total),
                'stamped_at': stamp.timbre.FechaTimbrado.isoformat(),
                'state': _SatState.VALID.value,
                'cancellability': None,
                'cancellation': _CancellationStatus.NONE.value,
            },
        )

    def _cancellability(self, record: dict[str, Any]) -> _Cancellability:
        if record.get('cancellability') is not None:
            return _Cancellability(record['cancellability'])
        stamped_at = record.get('stamped_at')
        if stamped_at is None:
            return _Cancellability.WITH_ACCEPTANCE
        if self._clock() - datetime.fromisoformat(stamped_at) < _WITHOUT_ACCEPTANCE:
            return _Cancellability.WITHOUT_ACCEPTANCE
        return _Cancellability.WITH_ACCEPTANCE

    @staticmethod
    def _matches(record: dict[str, Any], issuer: str, recipient: str, total: Decimal) -> bool:
        """Whether the RFCs and total match; a UUID stamped elsewhere is not checked."""
        if record.get('issuer_rfc') is None:
            return True
        return (
            record['issuer_rfc'] == issuer
            and record['recipient_rfc'] == recipient
            and Decimal(record['total']) == total
        )

    @_locked
    async def request_cancellation(self, request: CancellationRequest) -> CancellationAnswer:
        key = 'uuid:' + request.uuid.upper()
        record = await self._get(key)
        if not self._matches(record, request.issuer_rfc, request.recipient_rfc, request.total):
            reject('205', 'the RFCs or the total do not match the UUID')
        outcome = record.pop('next_cancellation', None)
        code = record.pop('code', None) or _DEFAULT_CODE
        message = record.pop('message', None) or _DEFAULT_MESSAGE
        record.setdefault('state', _SatState.VALID.value)
        record.setdefault('cancellation', _CancellationStatus.NONE.value)
        answer = self._answer(record, outcome)
        await self._set(key, record)
        if outcome == CancellationOutcome.REJECTED:
            raise PacRejected(code, message)
        if outcome == CancellationOutcome.UNAVAILABLE:
            raise PacUnavailable()
        if outcome == CancellationOutcome.TIMEOUT:
            raise PacTimeout()
        assert answer is not None
        return answer

    def _answer(self, record: dict[str, Any], outcome: str | None) -> CancellationAnswer | None:
        """Apply a request to the record (data-model.md section 5); ``None`` for an error."""
        settled = (
            record['state'] == _SatState.CANCELLED
            or record['cancellation'] == _CancellationStatus.PENDING
            or record.get('cancellability') == _Cancellability.NOT_CANCELLABLE
        )
        if outcome in (CancellationOutcome.REJECTED, CancellationOutcome.UNAVAILABLE):
            return None
        if outcome == CancellationOutcome.TIMEOUT:
            if not settled:
                self._pending(record)
            return None
        if record['state'] == _SatState.CANCELLED:
            return CancellationAnswer.ACCEPTED
        if record['cancellation'] == _CancellationStatus.PENDING:
            return CancellationAnswer.PENDING
        if record.get('cancellability') == _Cancellability.NOT_CANCELLABLE:
            return CancellationAnswer.NOT_CANCELLABLE
        if outcome == CancellationOutcome.NOT_CANCELLABLE:
            record['cancellability'] = _Cancellability.NOT_CANCELLABLE.value
            return CancellationAnswer.NOT_CANCELLABLE
        accept = outcome == CancellationOutcome.ACCEPTED or (
            outcome is None and self._cancellability(record) == _Cancellability.WITHOUT_ACCEPTANCE
        )
        if accept:
            record['state'] = _SatState.CANCELLED.value
            record['cancellation'] = _CancellationStatus.ACCEPTED.value
            return CancellationAnswer.ACCEPTED
        self._pending(record)
        return CancellationAnswer.PENDING

    @staticmethod
    def _pending(record: dict[str, Any]) -> None:
        record['cancellation'] = _CancellationStatus.PENDING.value
        record['cancellability'] = _Cancellability.WITH_ACCEPTANCE.value

    @_locked
    async def configure_cancellation(
        self,
        uuid: str,
        outcome: CancellationOutcome,
        *,
        code: str | None = None,
        message: str | None = None,
    ) -> None:
        """The outcome of the next ``request_cancellation`` of this UUID only."""
        key = 'uuid:' + uuid.upper()
        record = await self._get(key)
        record.update(
            next_cancellation=CancellationOutcome(outcome).value, code=code, message=message
        )
        await self._set(key, record)

    @_locked
    async def answer_as_receiver(self, uuid: str, answer: ReceiverAnswer) -> None:
        """Act as the recipient: accept, reject or let expire the pending cancellation."""
        key = 'uuid:' + uuid.upper()
        record = await self._get(key)
        if record.get('cancellation') != _CancellationStatus.PENDING:
            reject('SIM01', 'no cancellation is pending for this UUID')
        answer = ReceiverAnswer(answer)
        if answer == ReceiverAnswer.REJECT:
            record['cancellation'] = _CancellationStatus.REJECTED.value
        else:
            record['state'] = _SatState.CANCELLED.value
            record['cancellation'] = (
                _CancellationStatus.ACCEPTED
                if answer == ReceiverAnswer.ACCEPT
                else _CancellationStatus.EXPIRED
            ).value
        await self._set(key, record)

    def _stamped_xml(self, sealed: Sealed) -> bytes:
        tfd = tfd11.TimbreFiscalDigital(
            UUID=str(uuid.uuid4()).upper(),
            FechaTimbrado=self._clock().replace(microsecond=0),
            RfcProvCertif=SIMULATED_PAC_RFC,
            SelloCFD=sealed.seal,
            NoCertificadoSAT=_SAT_CERTIFICATE,
            SelloSAT=base64.b64encode(secrets.token_bytes(256)).decode('ascii'),
        )
        element, violations = serialize(tfd, {'xsi': XSI})
        if violations:
            raise AssertionError(violations)
        element.set(f'{{{XSI}}}schemaLocation', f'{tfd11.NAMESPACE} {tfd11.SCHEMA_LOCATION}')
        root = sealed.root
        complemento = root.find(f'{{{CFDI40}}}Complemento')
        if complemento is None:
            complemento = etree.Element(f'{{{CFDI40}}}Complemento')
            addenda = root.find(f'{{{CFDI40}}}Addenda')
            if addenda is None:
                root.append(complemento)
            else:
                addenda.addprevious(complemento)
        complemento.append(element)
        return b'<?xml version="1.0" encoding="UTF-8"?>\n' + etree.tostring(root, encoding='UTF-8')


def _conforms(pac: SimulatedPac, store: InMemoryStore) -> tuple[PacClient, SimulatorStore]:
    """Checked by ``mypy src``: the simulator and its store implement their protocols."""
    return pac, store
