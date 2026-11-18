import base64
from collections.abc import Callable
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.serialization import Encoding
from lxml import etree

from mictlanix.cfdi import (
    CSD,
    CertificateValidityError,
    CfdiError,
    Comprobante,
    ParseError,
    RawXml,
    ValidationError,
    _sat,
    original_string,
    seal,
)
from tests.conftest import CsdFiles

EXPECTED = Path(__file__).parent / 'fixtures' / 'expected'
CFDV40 = _sat.SAT_BASE + 'cfd/4/cfdv40.xsd'
MakeInvoice = Callable[..., Comprobante]


def _verify(xml: bytes, csd_files: CsdFiles) -> etree._Element:
    root = etree.fromstring(xml)
    certificate = x509.load_der_x509_certificate(base64.b64decode(root.get('Certificado', '')))
    assert certificate.public_bytes(Encoding.DER) == csd_files.certificate
    public = certificate.public_key()
    assert isinstance(public, rsa.RSAPublicKey)
    public.verify(
        base64.b64decode(root.get('Sello', '')),
        original_string(xml).encode('utf-8'),
        padding.PKCS1v15(),
        hashes.SHA256(),
    )
    return root


def test_a_sealed_invoice_is_valid_and_its_seal_verifies(
    make_invoice: MakeInvoice, csd: CSD, csd_files: CsdFiles
) -> None:
    sealed = seal(make_invoice(totals=False), csd)
    root = _verify(sealed, csd_files)
    assert root.get('NoCertificado') == '30001000000500003416'
    assert _sat.schema((CFDV40,)).validate(root), _sat.schema((CFDV40,)).error_log


def test_the_seal_equals_the_known_result(make_invoice: MakeInvoice, csd: CSD) -> None:
    sealed = seal(make_invoice(totals=False), csd)
    expected_string = (EXPECTED / 'ingreso.sellado.cadena.txt').read_text(encoding='utf-8')
    expected_seal = (EXPECTED / 'ingreso.sello.txt').read_text(encoding='ascii')
    assert original_string(sealed) == expected_string
    assert etree.fromstring(sealed).get('Sello') == expected_seal


def test_sealing_is_deterministic(make_invoice: MakeInvoice, csd: CSD) -> None:
    invoice = make_invoice(totals=False)
    assert seal(invoice, csd) == seal(invoice, csd)


def test_derived_values_are_filled_although_the_caller_supplied_none(
    make_invoice: MakeInvoice, csd: CSD
) -> None:
    invoice = make_invoice(totals=False)
    assert invoice.SubTotal is None and invoice.Total is None and invoice.Impuestos is None
    root = etree.fromstring(seal(invoice, csd))
    assert (root.get('SubTotal'), root.get('Total')) == ('100.00', '116.00')
    impuestos = root.find('{http://www.sat.gob.mx/cfd/4}Impuestos')
    assert impuestos is not None and impuestos.get('TotalImpuestosTrasladados') == '16.00'


def test_an_invalid_document_is_not_sealed(
    make_invoice: MakeInvoice, csd: CSD, monkeypatch: pytest.MonkeyPatch
) -> None:
    signed: list[bytes] = []
    monkeypatch.setattr(CSD, 'sign', lambda self, data: signed.append(data) or b'')
    invoice = make_invoice(totals=False, TipoDeComprobante='Z', MetodoPago='PPD')
    with pytest.raises(ValidationError) as caught:
        seal(invoice, csd)
    rules = {v.rule for v in caught.value.violations}
    assert {'cvc-enumeration-valid', 'CFDI40105'} <= rules
    assert signed == []


def test_a_fecha_outside_the_certificate_validity(make_invoice: MakeInvoice, csd: CSD) -> None:
    # The certificate expires at 2027-05-18T11:43:51Z, 05:43:51 in Mexico City.
    with pytest.raises(CertificateValidityError) as caught:
        seal(make_invoice(totals=False, Fecha=datetime(2027, 5, 18, 5, 43, 52)), csd)
    assert caught.value.valid_to == datetime(2027, 5, 18, 5, 43, 51)
    with pytest.raises(CertificateValidityError):
        seal(make_invoice(totals=False, Fecha=datetime(2023, 5, 18, 5, 43, 50)), csd)


def test_the_validity_ends_are_compared_in_mexico_city_time(
    make_invoice: MakeInvoice, csd: CSD
) -> None:
    seal(make_invoice(totals=False, Fecha=datetime(2023, 5, 18, 5, 43, 51)), csd)
    seal(make_invoice(totals=False, Fecha=datetime(2027, 5, 18, 5, 43, 51)), csd)


def test_a_fecha_with_a_time_zone_is_a_violation(make_invoice: MakeInvoice, csd: CSD) -> None:
    aware = datetime(2026, 11, 17, 12, 0, 0, tzinfo=timezone(timedelta(hours=-6)))
    with pytest.raises(ValidationError) as caught:
        seal(make_invoice(totals=False, Fecha=aware), csd)
    assert any(v.rule == 'datetime-not-naive' for v in caught.value.violations)


def test_a_malformed_addenda_is_a_parse_error(make_invoice: MakeInvoice, csd: CSD) -> None:
    with pytest.raises(ParseError):
        seal(make_invoice(totals=False, Addenda=[RawXml(b'<a><b></a>')]), csd)


def test_no_error_from_seal_carries_the_password_or_key(
    make_invoice: MakeInvoice, csd: CSD, csd_files: CsdFiles
) -> None:
    failing = [
        make_invoice(totals=False, TipoDeComprobante='Z'),
        make_invoice(totals=False, Fecha=datetime(2030, 1, 1)),
        replace(make_invoice(totals=False), Addenda=[RawXml(b'<a>')]),
    ]
    key_text = base64.b64encode(csd_files.private_key).decode()
    for invoice in failing:
        with pytest.raises(CfdiError) as caught:
            seal(invoice, csd)
        for text in (str(caught.value), repr(caught.value)):
            assert csd_files.password not in text
            assert key_text not in text and csd_files.private_key.hex() not in text
