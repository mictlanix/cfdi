from collections.abc import Callable
from dataclasses import replace
from datetime import datetime, timedelta, timezone

from mictlanix.cfdi import Comprobante, RawXml, Receptor, validate

MakeInvoice = Callable[..., Comprobante]


def _found(violations: list[object]) -> set[tuple[str, str | None, str]]:
    return {(v.node, v.attribute, v.rule) for v in violations}  # type: ignore[attr-defined]


def test_a_valid_document_has_no_violations(make_invoice: MakeInvoice) -> None:
    assert validate(make_invoice()) == []


def test_a_value_outside_its_catalog_names_the_node_attribute_and_rule(
    make_invoice: MakeInvoice,
) -> None:
    violations = validate(make_invoice(TipoDeComprobante='Z'))
    assert ('/cfdi:Comprobante', 'TipoDeComprobante', 'cvc-enumeration-valid') in _found(violations)


def test_every_violation_is_returned_together(make_invoice: MakeInvoice) -> None:
    invoice = make_invoice(TipoDeComprobante='Z')
    invoice = replace(invoice, Receptor=replace(invoice.Receptor, Rfc='x'))
    found = _found(validate(invoice))
    assert ('/cfdi:Comprobante', 'TipoDeComprobante', 'cvc-enumeration-valid') in found
    assert ('/cfdi:Comprobante/cfdi:Receptor', 'Rfc', 'cvc-pattern-valid') in found


def test_xsd_rule_names_follow_the_xml_schema_specification(make_invoice: MakeInvoice) -> None:
    invoice = make_invoice()
    receptor = Receptor(
        Rfc='x',
        Nombre=invoice.Receptor.Nombre,
        DomicilioFiscalReceptor=invoice.Receptor.DomicilioFiscalReceptor,
        RegimenFiscalReceptor=invoice.Receptor.RegimenFiscalReceptor,
        UsoCFDI=invoice.Receptor.UsoCFDI,
    )
    rules = {v.rule for v in validate(replace(invoice, Receptor=receptor))}
    assert 'cvc-minLength-valid' in rules


def test_an_unsealed_document_is_not_reported_for_the_seal_attributes(
    make_invoice: MakeInvoice,
) -> None:
    invoice = make_invoice()
    assert invoice.Sello is None and invoice.NoCertificado is None and invoice.Certificado is None
    assert validate(invoice) == []


def test_a_document_with_an_addenda_validates(make_invoice: MakeInvoice) -> None:
    addenda = RawXml(b'<x:Proveedor xmlns:x="urn:x" Numero="7"/>')
    assert validate(make_invoice(Addenda=[addenda])) == []


def test_values_xml_cannot_carry_are_violations_alongside_the_others(
    make_invoice: MakeInvoice,
) -> None:
    invoice = make_invoice(
        TipoDeComprobante='Z',
        Fecha=datetime(2026, 11, 17, 12, 0, 0, tzinfo=timezone(timedelta(hours=-6))),
    )
    concepto = replace(invoice.Conceptos[0], Descripcion='Venta\x00')
    found = _found(validate(replace(invoice, Conceptos=[concepto])))
    assert ('/cfdi:Comprobante', 'Fecha', 'datetime-not-naive') in found
    assert (
        '/cfdi:Comprobante/cfdi:Conceptos/cfdi:Concepto',
        'Descripcion',
        'xml-invalid-character',
    ) in found
    assert ('/cfdi:Comprobante', 'TipoDeComprobante', 'cvc-enumeration-valid') in found


def test_an_unmodelled_complement_is_reported_and_nothing_else_is_checked(
    make_invoice: MakeInvoice,
) -> None:
    retired = RawXml(b'<c:CartaPorte xmlns:c="http://www.sat.gob.mx/CartaPorte30"/>')
    violations = validate(make_invoice(TipoDeComprobante='Z', Complemento=[retired]))
    assert _found(violations) == {
        ('/cfdi:Comprobante/cfdi:Complemento', None, 'complement-not-modelled')
    }


def test_derived_values_are_computed_before_validating(make_invoice: MakeInvoice) -> None:
    assert validate(make_invoice(totals=False)) == []
