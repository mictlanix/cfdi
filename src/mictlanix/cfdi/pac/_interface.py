"""The generic PAC interface and its values."""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from decimal import Decimal
from enum import StrEnum
from typing import Protocol

from mictlanix.cfdi import tfd11
from mictlanix.cfdi._errors import ValidationError, Violation
from mictlanix.cfdi._read import read, timbre

_UUID = re.compile(r'[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}')
_REASONS = ('01', '02', '03', '04')


class CancellationAnswer(StrEnum):
    """The PAC's answer to a cancellation request."""

    ACCEPTED = 'accepted'
    PENDING = 'pending'
    NOT_CANCELLABLE = 'not_cancellable'


class SatState(StrEnum):
    VALID = 'valid'
    CANCELLED = 'cancelled'
    NOT_FOUND = 'not_found'


class Cancellability(StrEnum):
    WITHOUT_ACCEPTANCE = 'without_acceptance'
    WITH_ACCEPTANCE = 'with_acceptance'
    NOT_CANCELLABLE = 'not_cancellable'


class CancellationStatus(StrEnum):
    NONE = 'none'
    REQUESTED = 'requested'
    PENDING = 'pending'
    ACCEPTED = 'accepted'
    REJECTED = 'rejected'
    EXPIRED = 'expired'


@dataclass(frozen=True, kw_only=True)
class Stamp:
    """A stamped document and its TimbreFiscalDigital 1.1; the UUID is upper case."""

    xml: bytes
    timbre: tfd11.TimbreFiscalDigital

    def __repr__(self) -> str:
        return f'Stamp(xml=<{len(self.xml)} bytes>, timbre={self.timbre!r})'


@dataclass(frozen=True, kw_only=True)
class CsdCredentials:
    """The issuer's certificate (DER), encrypted private key (PKCS#8, DER) and its password.

    A PAC needs all three to sign a cancellation; ``repr`` never shows the key or the password.
    """

    certificate: bytes
    private_key: bytes
    password: str

    def __repr__(self) -> str:
        return (
            f'CsdCredentials(certificate=<{len(self.certificate)} bytes>, '
            'private_key=<hidden>, password=<hidden>)'
        )


@dataclass(frozen=True, kw_only=True)
class CancellationRequest:
    """A cancellation request; it cannot be created invalid. Raises ``ValidationError``."""

    issuer_rfc: str
    recipient_rfc: str
    uuid: str
    total: Decimal
    reason: str
    substitute_uuid: str | None = None
    csd: CsdCredentials

    def __post_init__(self) -> None:
        problems: list[tuple[str, str, str]] = []
        if self.reason not in _REASONS:
            problems.append(('reason', 'cancellation-reason', 'the reason must be 01 to 04'))
        elif self.reason == '01' and self.substitute_uuid is None:
            problems.append(
                (
                    'substitute_uuid',
                    'cancellation-substitute-required',
                    'reason 01 requires the substitute UUID',
                )
            )
        elif self.reason != '01' and self.substitute_uuid is not None:
            problems.append(
                (
                    'substitute_uuid',
                    'cancellation-substitute-forbidden',
                    'only reason 01 carries a substitute UUID',
                )
            )
        if not _UUID.fullmatch(self.uuid):
            problems.append(('uuid', 'uuid-format', 'not a well-formed UUID'))
        if self.substitute_uuid is not None and not _UUID.fullmatch(self.substitute_uuid):
            problems.append(('substitute_uuid', 'uuid-format', 'not a well-formed UUID'))
        if problems:
            raise ValidationError(
                Violation(
                    node='CancellationRequest', attribute=attribute, rule=rule, message=message
                )
                for attribute, rule, message in problems
            )


@dataclass(frozen=True, kw_only=True)
class SatStatus:
    """The SAT's status of one UUID."""

    state: SatState
    cancellability: Cancellability
    cancellation: CancellationStatus


class PacClient(Protocol):
    """The operations every PAC client offers. Each raises only ``PacError`` subclasses."""

    async def stamp(self, sealed_xml: bytes) -> Stamp:
        """Stamp a sealed document; a document already stamped returns its existing stamp."""
        ...

    async def find_stamp(self, sealed_xml: bytes) -> Stamp | None:
        """The stamp of this sealed document, or ``None``. Never stamps."""
        ...

    async def request_cancellation(self, request: CancellationRequest) -> CancellationAnswer:
        """Ask the SAT, through the PAC, to cancel the UUID."""
        ...

    async def query_status(
        self, issuer_rfc: str, recipient_rfc: str, uuid: str, total: Decimal
    ) -> SatStatus:
        """The SAT's current status of the UUID."""
        ...


def stamp_of(xml: bytes) -> Stamp:
    """The stamp of a stamped document, with its UUID in upper case."""
    tfd = timbre(read(xml))
    return Stamp(xml=xml, timbre=replace(tfd, UUID=tfd.UUID.upper()))
