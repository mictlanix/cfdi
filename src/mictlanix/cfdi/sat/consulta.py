"""The SAT's public status service, ConsultaCFDIService: the ``SatStatusClient`` for any CFDI."""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from decimal import Decimal
from typing import NoReturn
from xml.sax.saxutils import escape

from lxml import etree

from mictlanix.cfdi import _soap
from mictlanix.cfdi._read import _qr_total
from mictlanix.cfdi.sat._errors import SatRejected, SatTimeout, SatUnavailable
from mictlanix.cfdi.sat._interface import (
    NOT_FOUND,
    Cancellability,
    CancellationStatus,
    SatState,
    SatStatus,
    SatStatusClient,
)

SAT_CONSULTA = 'https://consultaqr.facturaelectronica.sat.gob.mx/ConsultaCFDIService.svc'
_ACTION = 'http://tempuri.org/IConsultaCFDIService/Consulta'
_UUID = re.compile(r'[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}')
_STATES = {'Vigente': SatState.VALID, 'Cancelado': SatState.CANCELLED}
_CANCELLABILITY = {
    'Cancelable sin aceptación': Cancellability.WITHOUT_ACCEPTANCE,
    'Cancelable con aceptación': Cancellability.WITH_ACCEPTANCE,
    'No cancelable': Cancellability.NOT_CANCELLABLE,
}
_CANCELLATION = {
    '': CancellationStatus.NONE,
    'En proceso': CancellationStatus.PENDING,
    'Plazo vencido': CancellationStatus.EXPIRED,
    'Cancelado con aceptación': CancellationStatus.ACCEPTED,
    'Cancelado sin aceptación': CancellationStatus.ACCEPTED,
    'Solicitud rechazada': CancellationStatus.REJECTED,
}


@dataclass(frozen=True, kw_only=True)
class SatConsultaSettings:
    """Where the SAT's status service is and how long to wait for it.

    The service takes no credentials, and nothing is read from the environment. Raises
    ``ValueError`` for a URL that is not HTTPS or a timeout that is not positive.
    """

    url: str = SAT_CONSULTA
    connect_timeout: float = 10.0
    read_timeout: float = 60.0

    def __post_init__(self) -> None:
        if not self.url.startswith('https://'):
            raise ValueError('url must be an https:// URL')
        for name in ('connect_timeout', 'read_timeout'):
            if not getattr(self, name) > 0:
                raise ValueError(f'{name} must be positive')


class SatConsultaClient:
    """The SAT's status of any CFDI, from its public status service, whichever PAC stamped it."""

    def __init__(self, settings: SatConsultaSettings | None = None) -> None:
        self._settings = settings or SatConsultaSettings()

    def __repr__(self) -> str:
        return f'SatConsultaClient({self._settings!r})'

    async def query_status(
        self, issuer_rfc: str, recipient_rfc: str, uuid: str, total: Decimal
    ) -> SatStatus:
        if not _UUID.fullmatch(uuid):
            return NOT_FOUND
        expression = f'?re={issuer_rfc}&rr={recipient_rfc}&tt={_qr_total(total)}&id={uuid}'
        return await asyncio.to_thread(self._query, expression)

    def _query(self, expression: str) -> SatStatus:
        body = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            f'<soap:Envelope xmlns:soap="{_soap.SOAP_ENV}" xmlns:tem="http://tempuri.org/">'
            '<soap:Body><tem:Consulta>'
            f'<tem:expresionImpresa>{escape(expression)}</tem:expresionImpresa>'
            '</tem:Consulta></soap:Body></soap:Envelope>'
        ).encode()
        try:
            raw = _soap._post(self._settings.url, _ACTION, body, self._settings)
            result = _soap.answer(raw)
        except _soap.Unreachable:
            raise SatUnavailable() from None
        except _soap.NoAnswer:
            raise SatTimeout() from None
        except _soap.Fault:
            raise SatRejected('SOAP-FAULT', 'the service refused the request') from None
        return _status(result)


def _unexpected() -> NoReturn:
    raise SatRejected('SAT-ANSWER', 'unexpected SAT status') from None


def _status(result: etree._Element) -> SatStatus:
    """The status in a ``ConsultaResponse`` (spec 004 data model §3)."""
    fields = {
        etree.QName(node).localname: (node.text or '').strip()
        for node in result.iter()
        if isinstance(node.tag, str) and len(node) == 0
    }
    if fields.get('CodigoEstatus', '').startswith('N') or fields.get('Estado') == 'No Encontrado':
        return NOT_FOUND
    state = _STATES.get(fields.get('Estado', ''))
    cancellability = _CANCELLABILITY.get(fields.get('EsCancelable', ''))
    cancellation = _CANCELLATION.get(fields.get('EstatusCancelacion', ''))
    if state is None or cancellability is None or cancellation is None:
        _unexpected()
    return SatStatus(state=state, cancellability=cancellability, cancellation=cancellation)


def _conforms(client: SatConsultaClient) -> SatStatusClient:
    """Checked by ``mypy src``: the SAT's client implements the interface."""
    return client
