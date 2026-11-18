"""The PAC's SOAP: RPC envelopes, answers, error text, and the PAC errors of each failure."""

from pathlib import Path
from typing import Any

import pytest
from lxml import etree

from mictlanix.cfdi import _soap as transport
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


def _raised(call: Any) -> PacError:
    with pytest.raises(PacError) as caught:
        call()
    assert caught.value.__cause__ is None
    assert caught.value.__suppress_context__
    assert 'PASSWORD' not in str(caught.value) and 'PASSWORD' not in repr(caught.value)
    return caught.value


@pytest.fixture
def post(monkeypatch: pytest.MonkeyPatch) -> list[bytes | Exception]:
    """Replaces the shared transport's ``_post`` with a queue of answers or exceptions."""
    answers: list[bytes | Exception] = []

    def fake(url: str, action: str, body: bytes, timeouts: Any) -> bytes:
        answer = answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer

    monkeypatch.setattr(transport, '_post', fake)
    return answers


@pytest.mark.parametrize(
    ('error', 'expected'),
    [(transport.Unreachable(), PacUnavailable), (transport.NoAnswer(), PacTimeout)],
)
def test_call_maps_the_transport_failures(
    post: list[bytes | Exception], error: Exception, expected: type[PacError]
) -> None:
    post.append(error)
    assert isinstance(_raised(lambda: _soap.call(URL, 'saldo', {}, SETTINGS)), expected)


def test_a_fault_is_rejected(post: list[bytes | Exception]) -> None:
    post.append(FAULT)
    error = _raised(lambda: _soap.call(URL, 'saldo', {}, SETTINGS))
    assert isinstance(error, PacRejected) and error.code == 'SOAP-FAULT'
    assert error.message == 'the service refused the request'
    assert 'secret detail' not in str(error)


def test_a_body_that_is_not_an_envelope_is_a_timeout(post: list[bytes | Exception]) -> None:
    for body in (b'<html>oops</html>', b'', b'not xml at all'):
        post.append(body)
        assert isinstance(_raised(lambda: _soap.call(URL, 'saldo', {}, SETTINGS)), PacTimeout)


def test_call_builds_posts_and_parses(monkeypatch: pytest.MonkeyPatch) -> None:
    sent: list[tuple[str, str, bytes, Any]] = []

    def fake(url: str, action: str, body: bytes, timeouts: Any) -> bytes:
        sent.append((url, action, body, timeouts))
        return _fixture('saldo.xml')

    monkeypatch.setattr(transport, '_post', fake)
    fields = _soap.call(URL, 'saldo', {'rfc': 'USER', 'clave': 'PASSWORD'}, SETTINGS)
    assert fields['saldo'] == '20'
    url, action, body, timeouts = sent[0]
    assert (url, action, timeouts) == (URL, 'urn:wservicewsdl#saldo', SETTINGS)
    assert b'<rfc xsi:type="xsd:string">USER</rfc>' in body
