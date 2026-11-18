"""PFIC 1.0 (document level), built, validated and sealed."""

from collections.abc import Callable

from mictlanix.cfdi import Comprobante, pfic10

MakeInvoice = Callable[..., Comprobante]
Check = Callable[[Comprobante], str]


def complement() -> pfic10.PFintegranteCoordinado:
    return pfic10.PFintegranteCoordinado(ClaveVehicular='1234567', Placa='ABC1234')


def test_a_document_carrying_it(make_invoice: MakeInvoice, builds_validates_seals: Check) -> None:
    cadena = builds_validates_seals(make_invoice(totals=False, Complemento=[complement()]))
    assert '|1.0|1234567|ABC1234|' in cadena
