"""Leyendas Fiscales 1.0 (document level), built, validated and sealed."""

from collections.abc import Callable

from mictlanix.cfdi import Comprobante, leyendasfiscales10

MakeInvoice = Callable[..., Comprobante]
Check = Callable[[Comprobante], str]


def complement() -> leyendasfiscales10.LeyendasFiscales:
    return leyendasfiscales10.LeyendasFiscales(
        Leyenda=[leyendasfiscales10.Leyenda(textoLeyenda='Leyenda de prueba')]
    )


def test_a_document_carrying_it(make_invoice: MakeInvoice, builds_validates_seals: Check) -> None:
    cadena = builds_validates_seals(make_invoice(totals=False, Complemento=[complement()]))
    assert '|1.0|Leyenda de prueba|' in cadena
