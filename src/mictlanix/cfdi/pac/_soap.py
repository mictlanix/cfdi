"""The PAC's SOAP: RPC/encoded envelopes, their answers and error text, over the shared transport.

``call`` builds an RPC envelope, posts it through ``mictlanix.cfdi._soap`` and returns the answer's
fields. The transport's failures become the PAC errors: ``Unreachable`` is ``PacUnavailable``,
``NoAnswer`` is ``PacTimeout`` and ``Fault`` is ``PacRejected('SOAP-FAULT')``. Every error is
raised ``from None`` and quotes nothing it received.
"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING
from xml.sax.saxutils import escape

from lxml import etree

from mictlanix.cfdi import _soap as transport
from mictlanix.cfdi.pac._errors import PacRejected, PacTimeout, PacUnavailable

if TYPE_CHECKING:
    from mictlanix.cfdi.pac.multifacturas import MultifacturasSettings

SOAP_ENV = transport.SOAP_ENV
RPC_NAMESPACE = 'urn:wservicewsdl'
_QUOTES = {'"': '&quot;', "'": '&apos;'}
_CODE = re.compile(r'([A-Z0-9]+) - (.+)', re.S)

Params = dict[str, 'str | dict[str, str]']


def _string(name: str, value: str) -> str:
    return f'<{name} xsi:type="xsd:string">{escape(value, _QUOTES)}</{name}>'


def envelope(operation: str, params: Params) -> bytes:
    """A SOAP 1.1 RPC/encoded request; a ``dict`` value is sent as a struct of strings."""
    parts: list[str] = []
    for name, value in params.items():
        if isinstance(value, dict):
            inner = ''.join(_string(key, item) for key, item in value.items())
            parts.append(f'<{name} xsi:type="tns:{name}">{inner}</{name}>')
        else:
            parts.append(_string(name, value))
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f'<soap:Envelope xmlns:soap="{SOAP_ENV}"'
        ' xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"'
        ' xmlns:xsd="http://www.w3.org/2001/XMLSchema"'
        f' xmlns:tns="{RPC_NAMESPACE}"'
        ' soap:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">'
        f'<soap:Body><tns:{operation}>{"".join(parts)}</tns:{operation}></soap:Body>'
        '</soap:Envelope>'
    ).encode()


def fields(raw: bytes) -> dict[str, str]:
    """The leaf elements of an answer's body as strings.

    Raises ``PacRejected('SOAP-FAULT')`` for a Fault and ``PacTimeout`` for anything that is not
    a SOAP envelope with a body.
    """
    try:
        child = transport.answer(raw)
    except transport.NoAnswer:
        raise PacTimeout() from None
    except transport.Fault:
        raise PacRejected('SOAP-FAULT', 'the service refused the request') from None
    return {
        etree.QName(node).localname: node.text or ''
        for node in child.iter()
        if isinstance(node.tag, str) and len(node) == 0
    }


def _repair(text: str) -> str:
    """Undo UTF-8 read as Latin-1 (``digestiÃ³n`` → ``digestión``); other text is unchanged."""
    try:
        return text.encode('latin-1').decode('utf-8')
    except UnicodeError:
        return text


def error_of(numero: str, texto: str) -> tuple[str, str]:
    """The code and message of an error answer, never its ``messageDetail`` (data-model §3)."""
    text = texto.strip()
    if text.startswith('ERROR:'):
        text = text[len('ERROR:') :].strip()
    try:
        data = json.loads(text)
    except ValueError:
        data = None
    if isinstance(data, dict) and isinstance(data.get('message'), str):
        text = data['message']
    text = _repair(text).strip()
    match = _CODE.fullmatch(text)
    if match:
        return match[1], match[2].strip()
    return numero, text


def call(
    url: str, operation: str, params: Params, settings: MultifacturasSettings
) -> dict[str, str]:
    """Call an RPC operation of the PAC and return the answer's fields."""
    action = f'{RPC_NAMESPACE}#{operation}'
    try:
        raw = transport._post(url, action, envelope(operation, params), settings)
    except transport.Unreachable:
        raise PacUnavailable() from None
    except transport.NoAnswer:
        raise PacTimeout() from None
    return fields(raw)
