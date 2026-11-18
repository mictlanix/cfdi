"""Hidrocarburos y Petrolíferos 1.0 (concept level), built, validated and sealed."""

from collections.abc import Callable
from dataclasses import replace

from mictlanix.cfdi import Comprobante, hidrocarburospetroliferos10

MakeInvoice = Callable[..., Comprobante]
Check = Callable[[Comprobante], str]


def complement() -> hidrocarburospetroliferos10.HidroYPetro:
    return hidrocarburospetroliferos10.HidroYPetro(
        TipoPermiso='PER01',
        NumeroPermiso='PL/123/EXP/ES/2020',
        ClaveHYP='15101505',
        SubProductoHYP='SP16',
    )


def test_a_concept_carrying_it(make_invoice: MakeInvoice, builds_validates_seals: Check) -> None:
    invoice = make_invoice(totals=False)
    concepto = replace(
        invoice.Conceptos[0],
        ComplementoConcepto=[complement()],
        ClaveProdServ='15101505',
        ClaveUnidad='LTR',
    )
    cadena = builds_validates_seals(replace(invoice, Conceptos=[concepto]))
    assert '|1.0|PER01|PL/123/EXP/ES/2020|15101505|SP16|' in cadena


def test_it_is_not_allowed_on_transfer_payment_or_payroll_documents(
    make_invoice: MakeInvoice,
) -> None:
    from mictlanix.cfdi import validate

    invoice = make_invoice(totals=False)
    concepto = replace(
        invoice.Conceptos[0],
        ComplementoConcepto=[complement()],
        ClaveProdServ='15101505',
        ClaveUnidad='LTR',
    )
    node = (
        '/cfdi:Comprobante/cfdi:Conceptos/cfdi:Concepto/cfdi:ComplementoConcepto'
        '/hidrocarburospetroliferos:HidroYPetro'
    )
    for tipo in ('T', 'P', 'N'):
        document = replace(invoice, TipoDeComprobante=tipo, Conceptos=[concepto])
        found = [v.node for v in validate(document) if v.rule == 'complement-document-type']
        assert found == [node], tipo
    expense = replace(invoice, TipoDeComprobante='E', Conceptos=[concepto])
    assert [v for v in validate(expense) if v.rule == 'complement-document-type'] == []
