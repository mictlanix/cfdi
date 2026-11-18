from collections.abc import Callable
from dataclasses import replace
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pytest

from mictlanix.cfdi import (
    CSD,
    Comprobante,
    NotCfdi40Error,
    NotStampedError,
    ParseError,
    QrData,
    RawXml,
    ValidationError,
    compute,
    qr_data,
    read,
    seal,
    tfd11,
    tfd_original_string,
    timbre,
    to_xml,
)

STAMPED = Path(__file__).parent / 'fixtures' / 'stamped'
MakeInvoice = Callable[..., Comprobante]
UUID = '7A6D8B24-1C0E-4B8F-9A2D-3E5F6A7B8C9D'


def _stamped() -> bytes:
    return (STAMPED / 'ingreso_timbrado.xml').read_bytes()


def test_reading_a_sealed_document_gives_back_what_was_sealed(
    make_invoice: MakeInvoice, csd: CSD
) -> None:
    invoice = make_invoice(totals=False)
    sealed = seal(invoice, csd)
    document = read(sealed)
    assert document == replace(
        compute(invoice),
        NoCertificado=csd.NoCertificado,
        Certificado=document.Certificado,
        Sello=document.Sello,
    )
    assert document.Sello and document.Certificado
    assert to_xml(document) == sealed


def test_timbre_gives_the_stamp() -> None:
    stamp = timbre(read(_stamped()))
    assert isinstance(stamp, tfd11.TimbreFiscalDigital)
    assert stamp.UUID == UUID
    assert stamp.FechaTimbrado == datetime(2026, 11, 17, 12, 5, 0)
    assert stamp.SelloSAT == 'U0VMTE8gU0FUIERFIFBSVUVCQQ=='
    assert stamp.NoCertificadoSAT == '00001000000500000001'
    assert stamp.RfcProvCertif == 'AAA010101AAA'


def test_the_tfd_original_string() -> None:
    expected = (STAMPED / 'ingreso_timbrado.tfd.cadena.txt').read_text(encoding='utf-8')
    assert tfd_original_string(_stamped()) == expected


def test_qr_data() -> None:
    document = read(_stamped())
    data = qr_data(document)
    assert (
        data
        == QrData(
            url=(
                'https://verificacfdi.facturaelectronica.sat.gob.mx/default.aspx'
                f'?id={UUID}&re=EKU9003173C9&rr=URE180429TM6&tt=116.0&fe={document.Sello[-8:]}'  # type: ignore[index]
            ),
            UUID=UUID,
            RfcEmisor='EKU9003173C9',
            RfcReceptor='URE180429TM6',
            Total=Decimal('116.00'),
            SelloUltimos8=document.Sello[-8:],  # type: ignore[index]
        )
    )


@pytest.mark.parametrize(
    ('total', 'tt'),
    [
        ('116.00', '116.0'),
        ('116.50', '116.5'),
        ('0', '0.0'),
        ('1234.123456', '1234.123456'),
        ('14300', '14300.0'),
    ],
)
def test_the_qr_total_omits_non_significant_zeros(total: str, tt: str) -> None:
    document = replace(read(_stamped()), Total=Decimal(total))
    assert f'&tt={tt}&' in qr_data(document).url


def test_an_unstamped_document_has_no_timbre(make_invoice: MakeInvoice, csd: CSD) -> None:
    document = read(seal(make_invoice(totals=False), csd))
    with pytest.raises(NotStampedError):
        timbre(document)
    with pytest.raises(NotStampedError):
        qr_data(document)
    with pytest.raises(NotStampedError):
        tfd_original_string(seal(make_invoice(totals=False), csd))


def test_qr_data_needs_the_seal_and_the_total() -> None:
    stamped = read(_stamped())
    with pytest.raises(NotStampedError):
        qr_data(replace(stamped, Sello=None))
    with pytest.raises(NotStampedError):
        qr_data(replace(stamped, Total=None))


def test_xml_that_is_not_well_formed() -> None:
    with pytest.raises(ParseError) as caught:
        read(b'<cfdi:Comprobante xmlns:cfdi="http://www.sat.gob.mx/cfd/4"')
    assert caught.value.line is not None


def test_a_required_attribute_missing_is_named() -> None:
    xml = _stamped().replace(b' UsoCFDI="G03"', b'')
    with pytest.raises(ParseError) as caught:
        read(xml)
    assert (caught.value.node, caught.value.attribute) == (
        '/cfdi:Comprobante/cfdi:Receptor',
        'UsoCFDI',
    )


def test_a_value_of_the_wrong_type_is_named() -> None:
    xml = _stamped().replace(b'SubTotal="100.00"', b'SubTotal="abc"')
    with pytest.raises(ParseError) as caught:
        read(xml)
    assert (caught.value.node, caught.value.attribute) == ('/cfdi:Comprobante', 'SubTotal')


def test_a_cfdi_33_is_refused() -> None:
    xml = b'<cfdi:Comprobante xmlns:cfdi="http://www.sat.gob.mx/cfd/3" Version="3.3"/>'
    with pytest.raises(NotCfdi40Error):
        read(xml)


def test_a_retired_complement_is_read_but_never_emitted(csd: CSD) -> None:
    document = read((STAMPED / 'cartaporte30.xml').read_bytes())
    raw = [item for item in document.Complemento if isinstance(item, RawXml)]
    assert len(raw) == 1 and b'CartaPorte30' in raw[0].xml
    assert timbre(document).UUID == '3B1C2D4E-5F60-4718-89AB-CDEF01234567'
    for emit in (lambda: to_xml(document), lambda: seal(document, csd)):
        with pytest.raises(ValidationError) as caught:
            emit()
        assert [v.rule for v in caught.value.violations] == ['complement-not-modelled']
