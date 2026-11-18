"""Facturación México (Multifacturas): the ``PacClient`` interface over the PAC's SOAP services."""

from __future__ import annotations

import asyncio
import base64
import binascii
from dataclasses import dataclass

from mictlanix.cfdi._errors import CfdiError
from mictlanix.cfdi.pac import _soap
from mictlanix.cfdi.pac._errors import PacTimeout
from mictlanix.cfdi.pac._input import check, reject
from mictlanix.cfdi.pac._interface import (
    CancellationAnswer,
    CancellationRequest,
    PacClient,
    Stamp,
    stamp_of,
)


@dataclass(frozen=True, kw_only=True)
class MultifacturasSettings:
    """How to reach the PAC: credentials, production or test mode, endpoint and timeouts.

    Everything comes from the caller; nothing is read from the environment. ``repr`` never shows
    the password. Raises ``ValueError`` for a ``base_url`` that is not HTTPS or a timeout that
    is not positive.
    """

    user: str
    password: str
    production: bool
    base_url: str = 'https://ws.multifacturas.com'
    connect_timeout: float = 10.0
    read_timeout: float = 60.0

    def __post_init__(self) -> None:
        if not self.base_url.startswith('https://'):
            raise ValueError('base_url must be an https:// URL')
        for name in ('connect_timeout', 'read_timeout'):
            if not getattr(self, name) > 0:
                raise ValueError(f'{name} must be positive')

    def __repr__(self) -> str:
        return (
            f'MultifacturasSettings(user={self.user!r}, password=<hidden>, '
            f'production={self.production!r}, base_url={self.base_url!r}, '
            f'connect_timeout={self.connect_timeout!r}, read_timeout={self.read_timeout!r})'
        )


class MultifacturasPac:
    """The PAC interface for Facturación México (Multifacturas).

    ``find_stamp`` returns ``None``: the PAC cannot look a stamp up by sealed document, and it
    answers a resubmission of the same sealed document with the existing stamp, so a timeout is
    resolved by stamping again (constitution principle IV).
    """

    def __init__(self, settings: MultifacturasSettings) -> None:
        self._settings = settings

    def __repr__(self) -> str:
        return f'MultifacturasPac({self._settings!r})'

    @property
    def _pac_url(self) -> str:
        return f'{self._settings.base_url}/pac/index.php'

    @property
    def _production(self) -> str:
        return 'SI' if self._settings.production else 'NO'

    async def stamp(self, sealed_xml: bytes) -> Stamp:
        return await asyncio.to_thread(self._stamp, sealed_xml)

    async def find_stamp(self, sealed_xml: bytes) -> Stamp | None:
        check(sealed_xml)
        return None

    def _stamp(self, sealed_xml: bytes) -> Stamp:
        seal = check(sealed_xml).seal
        settings = self._settings
        params: _soap.Params = {
            'rfc': settings.user,
            'clave': settings.password,
            'xml': base64.b64encode(sealed_xml).decode('ascii'),
            'produccion': self._production,
        }
        fields = _soap.call(self._pac_url, 'timbrar33b64', params, settings)
        numero = fields.get('codigo_mf_numero', '')
        if numero == '0':
            return _stamp_from(fields.get('cfdi', ''), seal)
        code, message = _soap.error_of(numero, fields.get('codigo_mf_texto', ''))
        if code != '307':
            reject(code, message)
        if fields.get('cfdi'):
            return _stamp_from(fields['cfdi'], seal)
        if fields.get('uuid'):
            document = self._retrieve(fields['uuid'])
            if document is not None:
                return _stamp_from(document, seal)
        raise PacTimeout() from None

    async def request_cancellation(self, request: CancellationRequest) -> CancellationAnswer:
        return await asyncio.to_thread(self._cancel, request)

    def _cancel(self, request: CancellationRequest) -> CancellationAnswer:
        settings, csd = self._settings, request.csd
        datos = {
            'usuario': settings.user,
            'pass': settings.password,
            'accion': 'cancelar',
            'produccion': self._production,
            'uuid': request.uuid.upper(),
            'rfc': request.issuer_rfc,
            'password': csd.password,
            'motivo': request.reason,
            'folioSustitucion': request.substitute_uuid or '',
            'b64Cer': base64.b64encode(csd.certificate).decode('ascii'),
            'b64Key': base64.b64encode(csd.private_key).decode('ascii'),
        }
        url = f'{settings.base_url}/cancelacion2022/index.php'
        fields = _soap.call(url, 'cancelarCfdi', {'datos': datos}, settings)
        numero = fields.get('codigo_mf_numero', '')
        if numero != '0':
            reject(*_soap.error_of(numero, fields.get('codigo_mf_texto', '')))
        sat = fields.get('codigo_respuesta_sat', '')
        if sat not in ('201', '202'):
            texto = (
                fields.get('codigo_respuesta_sat_texto', '') or 'the SAT did not take the request'
            )
            reject(*_soap.error_of(sat or 'SAT-ANSWER', texto))
        # 202: the SAT had already cancelled it; 201: the SAT took the request.
        return CancellationAnswer.ACCEPTED if sat == '202' else CancellationAnswer.PENDING

    async def balance(self) -> int:
        """The PAC account's remaining stamps (this client only, not part of ``PacClient``)."""
        return await asyncio.to_thread(self._balance)

    def _balance(self) -> int:
        settings = self._settings
        params: _soap.Params = {'rfc': settings.user, 'clave': settings.password}
        fields = _soap.call(self._pac_url, 'saldo', params, settings)
        numero = fields.get('codigo_mf_numero', '')
        if numero != '0':
            reject(*_soap.error_of(numero, fields.get('codigo_mf_texto', '')))
        try:
            return int(fields.get('saldo', ''))
        except ValueError:
            reject('MF-ANSWER', 'the PAC answered without a usable balance')

    def _retrieve(self, uuid: str) -> str | None:
        """The stamped document of a UUID, Base64, when the PAC returns one."""
        settings = self._settings
        params: _soap.Params = {'rfc': settings.user, 'pwd': settings.password, 'uuid': uuid}
        answer = _soap.call(self._pac_url, 'acuseSAT', params, settings)
        document = answer.get('acuseSATResult') or answer.get('return') or ''
        return document if _decode(document).lstrip().startswith(b'<') else None


def _decode(value: str) -> bytes:
    try:
        return base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError):
        return b''


def _stamp_from(document: str, seal: str) -> Stamp:
    """The stamp in a Base64 stamped document, checked to carry the submitted seal."""
    try:
        stamp = stamp_of(_decode(document))
    except CfdiError:
        reject('MF-ANSWER', 'the PAC answered without a usable stamp')
    if stamp.timbre.SelloCFD != seal:
        reject('MF-ANSWER', 'the PAC answered with the stamp of another document')
    return stamp


def _conforms(pac: MultifacturasPac) -> PacClient:
    """Checked by ``mypy src``: the Multifacturas client implements the interface."""
    return pac
