"""Aerolíneas 1.0 (document level), built, validated and sealed."""

from collections.abc import Callable
from decimal import Decimal as D

from mictlanix.cfdi import Comprobante, aerolineas10

MakeInvoice = Callable[..., Comprobante]
Check = Callable[[Comprobante], str]


def complement() -> aerolineas10.Aerolineas:
    return aerolineas10.Aerolineas(TUA=D('100.00'))


def test_a_document_carrying_it(make_invoice: MakeInvoice, builds_validates_seals: Check) -> None:
    cadena = builds_validates_seals(make_invoice(totals=False, Complemento=[complement()]))
    assert '|1.0|100.00|' in cadena
