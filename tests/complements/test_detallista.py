"""Detallista 1.3.1 (document level), built, validated and sealed."""

from collections.abc import Callable

from mictlanix.cfdi import Comprobante, detallista

MakeInvoice = Callable[..., Comprobante]
Check = Callable[[Comprobante], str]


def complement() -> detallista.detallista:
    return detallista.detallista(
        documentStatus='ORIGINAL',
        requestForPaymentIdentification=detallista.requestForPaymentIdentification(
            entityType='INVOICE'
        ),
        orderIdentification=detallista.orderIdentification(
            referenceIdentification=[detallista.referenceIdentification(value='PO-1')]
        ),
        AdditionalInformation=[
            detallista.AdditionalInformationReferenceIdentification(type='ATZ', value='X1')
        ],
        buyer=detallista.buyer(gln='0000000000001'),
    )


def test_a_document_carrying_it(make_invoice: MakeInvoice, builds_validates_seals: Check) -> None:
    cadena = builds_validates_seals(make_invoice(totals=False, Complemento=[complement()]))
    # The SAT's stylesheet emits documentStructureVersion, the order reference and the buyer.
    assert '|AMC8.1|PO-1|0000000000001|' in cadena
