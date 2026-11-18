"""The SOAP transport: envelopes, answers, error text, and which failures are which."""

import http.client
import socket
import ssl
from pathlib import Path
from typing import Any

import pytest
from lxml import etree

from mictlanix.cfdi.pac import (
    MultifacturasSettings,
    PacError,
    PacRejected,
    PacTimeout,
    PacUnavailable,
    _soap,
)

FIXTURES = Path(__file__).resolve().parent.parent / 'fixtures' / 'multifacturas'
SETTINGS = MultifacturasSettings(
    user='USER', password='PASSWORD', production=False, connect_timeout=3.0, read_timeout=7.0
)
URL = 'https://ws.example.test/pac/index.php'
FAULT = (
    b'<?xml version="1.0"?><SOAP-ENV:Envelope'
    b' xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/"><SOAP-ENV:Body>'
    b'<SOAP-ENV:Fault><faultcode>SOAP-ENV:Client</faultcode>'
    b'<faultstring>secret detail PASSWORD</faultstring></SOAP-ENV:Fault>'
    b'</SOAP-ENV:Body></SOAP-ENV:Envelope>'
)


def _fixture(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def test_the_envelope_is_soap_rpc_with_escaped_strings_and_structs() -> None:
    body = _soap.envelope(
        'timbrar33b64', {'rfc': 'A&B<"\'>', 'datos': {'uuid': 'X', 'motivo': '02'}}
    )
    root = etree.fromstring(body)
    assert etree.QName(root).localname == 'Envelope'
    operation = root.find('.//{urn:wservicewsdl}timbrar33b64')
    assert operation is not None
    rfc = operation.find('rfc')
    assert rfc is not None and rfc.text == 'A&B<"\'>'
    assert rfc.get('{http://www.w3.org/2001/XMLSchema-instance}type') == 'xsd:string'
    datos = operation.find('datos')
    assert datos is not None
    assert datos.get('{http://www.w3.org/2001/XMLSchema-instance}type') == 'tns:datos'
    assert [(child.tag, child.text) for child in datos] == [('uuid', 'X'), ('motivo', '02')]


def test_fields_are_the_leaves_of_the_return() -> None:
    fields = _soap.fields(_fixture('saldo.xml'))
    assert fields['codigo_mf_numero'] == '0'
    assert fields['saldo'] == '20'
    assert _soap.fields(_fixture('acuseSAT_200.xml'))['acuseSATResult'] == '200'


def test_error_text_gives_the_code_and_message() -> None:
    fields = _soap.fields(_fixture('timbrar33b64_301.xml'))
    assert _soap.error_of(fields['codigo_mf_numero'], fields['codigo_mf_texto']) == (
        '301',
        'La estructura del comprobante es incorrecta.',
    )


def test_error_text_is_repaired_and_never_carries_the_detail() -> None:
    fields = _soap.fields(_fixture('timbrar33b64_CFDI40102.xml'))
    assert 'Ã' in fields['codigo_mf_texto']
    code, message = _soap.error_of(fields['codigo_mf_numero'], fields['codigo_mf_texto'])
    assert code == 'CFDI40102'
    assert 'digestión' in message and 'Ã' not in message


def test_error_text_in_json_drops_message_detail() -> None:
    fields = _soap.fields(_fixture('cancelarCfdi_CACFDI33.xml'))
    code, message = _soap.error_of(fields['codigo_mf_numero'], fields['codigo_mf_texto'])
    assert (code, message) == ('CACFDI33', 'Problemas con los campos.')
    assert 'llave privada' in fields['codigo_mf_texto']


def test_error_text_without_a_code_uses_the_number() -> None:
    assert _soap.error_of('7', 'Algo salió mal') == ('7', 'Algo salió mal')


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
    FakeConnection.body = _fixture('saldo.xml')
    monkeypatch.setattr(http.client, 'HTTPSConnection', FakeConnection)
    return FakeConnection


def _raised(call: Any) -> PacError:
    with pytest.raises(PacError) as caught:
        call()
    assert caught.value.__cause__ is None
    assert caught.value.__suppress_context__
    assert 'PASSWORD' not in str(caught.value) and 'PASSWORD' not in repr(caught.value)
    return caught.value


def test_post_sends_over_verified_tls_with_the_timeouts(connection: type[FakeConnection]) -> None:
    raw = _soap._post(URL, 'urn:wservicewsdl#saldo', b'<x/>', SETTINGS)
    assert raw == _fixture('saldo.xml')
    sent = connection.created[0]
    assert sent.host == 'ws.example.test'
    assert sent.timeout == 3.0 and sent.read_timeout == 7.0
    assert sent.context.check_hostname and sent.context.verify_mode == ssl.CERT_REQUIRED
    method, path, body, headers = sent.sent
    assert (method, path, body) == ('POST', '/pac/index.php', b'<x/>')
    assert headers['SOAPAction'] == '"urn:wservicewsdl#saldo"'
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
def test_a_failure_to_connect_is_unavailable(
    connection: type[FakeConnection], error: BaseException
) -> None:
    connection.fail_connect = error
    assert isinstance(_raised(lambda: _soap._post(URL, 'a', b'', SETTINGS)), PacUnavailable)


def test_an_endpoint_with_a_bad_port_is_unavailable(connection: type[FakeConnection]) -> None:
    url = 'https://ws.example.test:abc/pac/index.php'
    assert isinstance(_raised(lambda: _soap._post(url, 'a', b'', SETTINGS)), PacUnavailable)
    assert connection.created == []


@pytest.mark.parametrize(
    'error', [TimeoutError(), ConnectionResetError(), http.client.HTTPException('bad')]
)
def test_a_failure_after_connecting_is_a_timeout(
    connection: type[FakeConnection], error: BaseException
) -> None:
    connection.fail_after = error
    assert isinstance(_raised(lambda: _soap._post(URL, 'a', b'', SETTINGS)), PacTimeout)


def test_a_fault_is_rejected_whatever_the_status(connection: type[FakeConnection]) -> None:
    connection.body = FAULT
    for status in (500, 200):
        connection.status = status
        error = _raised(lambda: _soap.call(URL, 'saldo', {}, SETTINGS))
        assert isinstance(error, PacRejected) and error.code == 'SOAP-FAULT'
        assert 'secret detail' not in str(error)


def test_another_status_is_a_timeout(connection: type[FakeConnection]) -> None:
    connection.status = 503
    connection.body = b'<html>busy</html>'
    assert isinstance(_raised(lambda: _soap.call(URL, 'saldo', {}, SETTINGS)), PacTimeout)


def test_a_200_body_that_is_not_an_envelope_is_a_timeout(
    connection: type[FakeConnection],
) -> None:
    for body in (b'<html>oops</html>', b'', b'not xml at all'):
        connection.body = body
        assert isinstance(_raised(lambda: _soap.call(URL, 'saldo', {}, SETTINGS)), PacTimeout)


def test_call_builds_posts_and_parses(connection: type[FakeConnection]) -> None:
    fields = _soap.call(URL, 'saldo', {'rfc': 'USER', 'clave': 'PASSWORD'}, SETTINGS)
    assert fields['saldo'] == '20'
    body = connection.created[0].sent[2]
    assert b'<rfc xsi:type="xsd:string">USER</rfc>' in body
