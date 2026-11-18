"""The SOAP 1.1 transport over the standard library, shared by the PAC and SAT clients.

``_post`` is the raw HTTPS exchange and the one seam offline tests replace; ``answer`` reads the
first child of an answer's body. Failures are three private exceptions, each raised ``from None``
with no message, that every client maps to its own errors: ``Unreachable`` (the request was not
sent), ``NoAnswer`` (it was sent and no usable answer came) and ``Fault`` (a SOAP Fault).
"""

from __future__ import annotations

import http.client
import ssl
from typing import Protocol
from urllib.parse import urlsplit

from lxml import etree

SOAP_ENV = 'http://schemas.xmlsoap.org/soap/envelope/'


class Unreachable(Exception):
    """The request was not sent."""


class NoAnswer(Exception):
    """The request was sent and no usable answer came."""


class Fault(Exception):
    """The service answered a SOAP Fault."""


class Timeouts(Protocol):
    """The seconds to wait for the connection and for the answer."""

    @property
    def connect_timeout(self) -> float: ...

    @property
    def read_timeout(self) -> float: ...


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


def answer(raw: bytes) -> etree._Element:
    """The first child of the answer's body; ``Fault`` for a Fault, ``NoAnswer`` for non-SOAP."""
    child = _body_child(_parse(raw))
    if child is None:
        raise NoAnswer() from None
    if etree.QName(child).localname == 'Fault':
        raise Fault() from None
    return child


def _post(url: str, action: str, body: bytes, timeouts: Timeouts) -> bytes:
    """Post a SOAP request over verified TLS and return the answer's body."""
    parts = urlsplit(url)
    path = parts.path + (f'?{parts.query}' if parts.query else '')
    try:
        port = parts.port
    except ValueError:
        raise Unreachable() from None
    connection = http.client.HTTPSConnection(
        parts.hostname or '',
        port,
        timeout=timeouts.connect_timeout,
        context=ssl.create_default_context(),
    )
    try:
        try:
            connection.connect()
        except (OSError, http.client.HTTPException, UnicodeError):
            raise Unreachable() from None
        try:
            if connection.sock is not None:
                connection.sock.settimeout(timeouts.read_timeout)
            connection.request(
                'POST',
                path,
                body,
                {'Content-Type': 'text/xml; charset=utf-8', 'SOAPAction': f'"{action}"'},
            )
            response = connection.getresponse()
            status, raw = response.status, response.read()
        except (OSError, http.client.HTTPException):
            raise NoAnswer() from None
    finally:
        connection.close()
    if status != 200 and not _is_fault(raw):
        raise NoAnswer() from None
    return raw
