"""A small SOAP 1.1 client over the standard library, shared by the PAC clients.

``_post`` is the raw HTTPS exchange and the one seam offline tests replace; ``call`` builds an
RPC envelope, posts it and returns the answer's fields. Failures to connect are
``PacUnavailable``; anything after the connection is open is ``PacTimeout``; a SOAP Fault is
``PacRejected('SOAP-FAULT')``. Every error is raised ``from None`` and quotes nothing it received.
"""

from __future__ import annotations

import http.client
import json
import re
import ssl
from typing import TYPE_CHECKING
from urllib.parse import urlsplit
from xml.sax.saxutils import escape

from lxml import etree

from mictlanix.cfdi.pac._errors import PacRejected, PacTimeout, PacUnavailable

if TYPE_CHECKING:
    from mictlanix.cfdi.pac.multifacturas import MultifacturasSettings

SOAP_ENV = 'http://schemas.xmlsoap.org/soap/envelope/'
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


def _parse(raw: bytes) -> etree._Element | None:
    parser = etree.XMLParser(no_network=True, resolve_entities=False, load_dtd=False)
    try:
        return etree.fromstring(raw, parser)
    except (etree.XMLSyntaxError, ValueError):
        return None


def _body_child(root: etree._Element | None) -> etree._Element | None:
    if root is None or root.tag != f'{{{SOAP_ENV}}}Envelope':
        return None
    body = root.find(f'{{{SOAP_ENV}}}Body')
    if body is None or len(body) == 0:
        return None
    return body[0]


def _is_fault(raw: bytes) -> bool:
    child = _body_child(_parse(raw))
    return child is not None and etree.QName(child).localname == 'Fault'


def fields(raw: bytes) -> dict[str, str]:
    """The leaf elements of an answer's body as strings.

    Raises ``PacRejected('SOAP-FAULT')`` for a Fault and ``PacTimeout`` for anything that is not
    a SOAP envelope with a body.
    """
    child = _body_child(_parse(raw))
    if child is None:
        raise PacTimeout() from None
    if etree.QName(child).localname == 'Fault':
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


def _post(url: str, action: str, body: bytes, settings: MultifacturasSettings) -> bytes:
    """Post a SOAP request over verified TLS and return the answer's body."""
    parts = urlsplit(url)
    path = parts.path + (f'?{parts.query}' if parts.query else '')
    try:
        port = parts.port
    except ValueError:
        raise PacUnavailable() from None
    connection = http.client.HTTPSConnection(
        parts.hostname or '',
        port,
        timeout=settings.connect_timeout,
        context=ssl.create_default_context(),
    )
    try:
        try:
            connection.connect()
        except (OSError, http.client.HTTPException, UnicodeError):
            raise PacUnavailable() from None
        try:
            if connection.sock is not None:
                connection.sock.settimeout(settings.read_timeout)
            connection.request(
                'POST',
                path,
                body,
                {'Content-Type': 'text/xml; charset=utf-8', 'SOAPAction': f'"{action}"'},
            )
            response = connection.getresponse()
            status, raw = response.status, response.read()
        except (OSError, http.client.HTTPException):
            raise PacTimeout() from None
    finally:
        connection.close()
    if status != 200 and not _is_fault(raw):
        raise PacTimeout() from None
    return raw


def call(
    url: str, operation: str, params: Params, settings: MultifacturasSettings
) -> dict[str, str]:
    """Call an RPC operation of the PAC and return the answer's fields."""
    action = f'{RPC_NAMESPACE}#{operation}'
    return fields(_post(url, action, envelope(operation, params), settings))
