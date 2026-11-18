"""CFDI Registro Fiscal 1.0 (document level), built, validated and sealed."""

from collections.abc import Callable

from mictlanix.cfdi import Comprobante, registrofiscal10

MakeInvoice = Callable[..., Comprobante]
Check = Callable[[Comprobante], str]


def complement() -> registrofiscal10.CFDIRegistroFiscal:
    return registrofiscal10.CFDIRegistroFiscal(Folio='0000000000000001')


def test_a_document_carrying_it(make_invoice: MakeInvoice, builds_validates_seals: Check) -> None:
    cadena = builds_validates_seals(make_invoice(totals=False, Complemento=[complement()]))
    assert '|1.0|0000000000000001|' in cadena
