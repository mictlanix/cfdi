from collections.abc import Callable
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest
from lxml import etree

from mictlanix.cfdi import Comprobante, ParseError, RawXml, ValidationError, to_xml

CFDI = 'http://www.sat.gob.mx/cfd/4'
XSI = 'http://www.w3.org/2001/XMLSchema-instance'
Q = f'{{{CFDI}}}'

MakeInvoice = Callable[..., Comprobante]


def test_writes_utf8_xml_with_the_cfdi_prefix_and_schema_location(
    make_invoice: MakeInvoice,
) -> None:
    xml = to_xml(make_invoice())
    assert xml.startswith(b'<?xml version="1.0" encoding="UTF-8"?>')
    root = etree.fromstring(xml)
    assert root.tag == Q + 'Comprobante'
    assert root.prefix == 'cfdi'
    assert root.get('Version') == '4.0'
    assert root.get(f'{{{XSI}}}schemaLocation') == (
        f'{CFDI} http://www.sat.gob.mx/sitio_internet/cfd/4/cfdv40.xsd'
    )
    assert root.get('SubTotal') == '100.00'
    assert root.find(f'{Q}Receptor').get('Nombre') == 'UNIVERSIDAD ROBOTICA ESPAÑOLA'  # type: ignore[union-attr]
    assert 'ESPAÑOLA'.encode() in xml


def test_children_are_in_xsd_order(make_invoice: MakeInvoice) -> None:
    root = etree.fromstring(to_xml(make_invoice()))
    assert [etree.QName(element).localname for element in root] == [
        'Emisor',
        'Receptor',
        'Conceptos',
        'Impuestos',
    ]


def test_raw_xml_under_complemento_is_refused(make_invoice: MakeInvoice) -> None:
    retired = RawXml(
        b'<cartaporte30:CartaPorte xmlns:cartaporte30="http://www.sat.gob.mx/CartaPorte30"/>'
    )
    with pytest.raises(ValidationError) as caught:
        to_xml(make_invoice(Complemento=[retired]))
    assert [(v.node, v.attribute, v.rule) for v in caught.value.violations] == [
        ('/cfdi:Comprobante/cfdi:Complemento', None, 'complement-not-modelled')
    ]


def test_raw_xml_under_complemento_concepto_is_refused(make_invoice: MakeInvoice) -> None:
    invoice = make_invoice()
    concepto = replace(
        invoice.Conceptos[0], ComplementoConcepto=[RawXml(b'<x:Y xmlns:x="urn:x"/>')]
    )
    with pytest.raises(ValidationError) as caught:
        to_xml(replace(invoice, Conceptos=[concepto]))
    assert [(v.node, v.rule) for v in caught.value.violations] == [
        (
            '/cfdi:Comprobante/cfdi:Conceptos/cfdi:Concepto/cfdi:ComplementoConcepto',
            'complement-not-modelled',
        )
    ]


def test_raw_xml_under_addenda_is_written_as_is(make_invoice: MakeInvoice) -> None:
    addenda = RawXml(b'<x:Proveedor xmlns:x="urn:x" Numero="7"><x:Nota>hola</x:Nota></x:Proveedor>')
    root = etree.fromstring(to_xml(make_invoice(Addenda=[addenda])))
    proveedor = root.find(f'{Q}Addenda/{{urn:x}}Proveedor')
    assert proveedor is not None
    assert proveedor.get('Numero') == '7'
    assert proveedor.findtext('{urn:x}Nota') == 'hola'


def test_raw_xml_that_is_not_one_element_is_a_parse_error(make_invoice: MakeInvoice) -> None:
    with pytest.raises(ParseError):
        to_xml(make_invoice(Addenda=[RawXml(b'<a/><b/>')]))
    with pytest.raises(ParseError):
        to_xml(make_invoice(Addenda=[RawXml(b'<a>')]))


def test_a_character_xml_cannot_carry_is_reported(make_invoice: MakeInvoice) -> None:
    invoice = make_invoice()
    concepto = replace(invoice.Conceptos[0], Descripcion='Venta\x00')
    with pytest.raises(ValidationError) as caught:
        to_xml(replace(invoice, Conceptos=[concepto]))
    assert [(v.node, v.attribute, v.rule) for v in caught.value.violations] == [
        ('/cfdi:Comprobante/cfdi:Conceptos/cfdi:Concepto', 'Descripcion', 'xml-invalid-character')
    ]


def test_a_fecha_with_a_time_zone_is_reported(make_invoice: MakeInvoice) -> None:
    aware = datetime(2026, 11, 17, 12, 0, 0, tzinfo=timezone(timedelta(hours=-6)))
    with pytest.raises(ValidationError) as caught:
        to_xml(make_invoice(Fecha=aware))
    assert [(v.node, v.attribute, v.rule) for v in caught.value.violations] == [
        ('/cfdi:Comprobante', 'Fecha', 'datetime-not-naive')
    ]
