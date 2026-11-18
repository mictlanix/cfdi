"""The shared SOAP transport: verified TLS, timeouts, and which failure is which."""

import http.client
import socket
import ssl
from dataclasses import dataclass
from typing import Any

import pytest
from lxml import etree

from mictlanix.cfdi import _soap

URL = 'https://ws.example.test/service/index.php'
ENVELOPE = (
    b'<?xml version="1.0"?><s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">'
    b'<s:Body><Answer xmlns="urn:x"><value>1</value></Answer></s:Body></s:Envelope>'
)
FAULT = (
    b'<?xml version="1.0"?><SOAP-ENV:Envelope'
    b' xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/"><SOAP-ENV:Body>'
    b'<SOAP-ENV:Fault><faultcode>SOAP-ENV:Client</faultcode>'
    b'<faultstring>secret detail</faultstring></SOAP-ENV:Fault>'
    b'</SOAP-ENV:Body></SOAP-ENV:Envelope>'
)


@dataclass(frozen=True)
class Timeouts:
    connect_timeout: float = 3.0
    read_timeout: float = 7.0


TIMEOUTS = Timeouts()


class FakeConnection:
    """Stands in for http.client.HTTPSConnection; fails where it is told to."""

    created: list['FakeConnection'] = []

    def __init__(
        self, host: str, port: int | None = None, *, timeout: float, context: ssl.SSLContext
    ) -> None:
        self.host, self.port, self.timeout, self.context = host, port, timeout, context
        self.sock: Any = None
        FakeConnection.created.append(self)

    fail_connect: BaseException | None = None
    fail_after: BaseException | None = None
    status = 200
    body = b''

    def connect(self) -> None:
        if FakeConnection.fail_connect is not None:
            raise FakeConnection.fail_connect
        self.sock = self

    def settimeout(self, value: float) -> None:
        self.read_timeout = value

    def request(self, method: str, path: str, body: bytes, headers: dict[str, str]) -> None:
        self.sent = (method, path, body, headers)
        if FakeConnection.fail_after is not None:
            raise FakeConnection.fail_after

    def getresponse(self) -> 'FakeConnection':
        return self

    def read(self) -> bytes:
        return FakeConnection.body

    def close(self) -> None:
        pass


@pytest.fixture
def connection(monkeypatch: pytest.MonkeyPatch) -> type[FakeConnection]:
    FakeConnection.created = []
    FakeConnection.fail_connect = None
    FakeConnection.fail_after = None
    FakeConnection.status = 200
    FakeConnection.body = ENVELOPE
    monkeypatch.setattr(http.client, 'HTTPSConnection', FakeConnection)
    return FakeConnection


def _raised(kind: type[Exception], call: Any) -> Exception:
    with pytest.raises(kind) as caught:
        call()
    assert caught.value.__cause__ is None
    assert caught.value.__suppress_context__
    assert caught.value.args == ()
    return caught.value


def test_post_sends_over_verified_tls_with_the_timeouts(connection: type[FakeConnection]) -> None:
    raw = _soap._post(URL + '?wsdl', 'urn:x#op', b'<x/>', TIMEOUTS)
    assert raw == ENVELOPE
    sent = connection.created[0]
    assert sent.host == 'ws.example.test'
    assert sent.timeout == 3.0 and sent.read_timeout == 7.0
    assert sent.context.check_hostname and sent.context.verify_mode == ssl.CERT_REQUIRED
    method, path, body, headers = sent.sent
    assert (method, path, body) == ('POST', '/service/index.php?wsdl', b'<x/>')
    assert headers['SOAPAction'] == '"urn:x#op"'
    assert headers['Content-Type'].startswith('text/xml')


@pytest.mark.parametrize(
    'error',
    [
        OSError('refused'),
        socket.gaierror('dns'),
        ssl.SSLError('cert'),
        TimeoutError(),
        UnicodeError('label empty or too long'),
    ],
)
def test_a_failure_to_connect_is_unreachable(
    connection: type[FakeConnection], error: BaseException
) -> None:
    connection.fail_connect = error
    _raised(_soap.Unreachable, lambda: _soap._post(URL, 'a', b'', TIMEOUTS))


def test_an_endpoint_with_a_bad_port_is_unreachable(connection: type[FakeConnection]) -> None:
    url = 'https://ws.example.test:abc/service/index.php'
    _raised(_soap.Unreachable, lambda: _soap._post(url, 'a', b'', TIMEOUTS))
    assert connection.created == []


@pytest.mark.parametrize(
    'error', [TimeoutError(), ConnectionResetError(), http.client.HTTPException('bad')]
)
def test_a_failure_after_connecting_is_no_answer(
    connection: type[FakeConnection], error: BaseException
) -> None:
    connection.fail_after = error
    _raised(_soap.NoAnswer, lambda: _soap._post(URL, 'a', b'', TIMEOUTS))


def test_a_fault_comes_back_whatever_the_status(connection: type[FakeConnection]) -> None:
    connection.body = FAULT
    for status in (500, 200):
        connection.status = status
        assert _soap._post(URL, 'a', b'', TIMEOUTS) == FAULT


def test_another_status_without_a_fault_is_no_answer(connection: type[FakeConnection]) -> None:
    connection.status = 503
    connection.body = b'<html>busy</html>'
    _raised(_soap.NoAnswer, lambda: _soap._post(URL, 'a', b'', TIMEOUTS))


def test_the_answer_is_the_first_child_of_the_body() -> None:
    child = _soap.answer(ENVELOPE)
    assert etree.QName(child).localname == 'Answer'
    assert child.findtext('{urn:x}value') == '1'


def test_a_fault_answer_is_a_fault_without_its_text() -> None:
    error = _raised(_soap.Fault, lambda: _soap.answer(FAULT))
    assert 'secret detail' not in repr(error)


@pytest.mark.parametrize(
    'raw',
    [
        b'<html>oops</html>',
        b'',
        b'not xml at all',
        b'<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"><s:Body/></s:Envelope>',
    ],
)
def test_anything_but_an_envelope_with_a_body_is_no_answer(raw: bytes) -> None:
    _raised(_soap.NoAnswer, lambda: _soap.answer(raw))
