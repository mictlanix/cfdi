"""Obras de Arte y Antigüedades 1.0 (document level), built, validated and sealed."""

from collections.abc import Callable
from datetime import date

from mictlanix.cfdi import Comprobante, arteantiguedades10

MakeInvoice = Callable[..., Comprobante]
Check = Callable[[Comprobante], str]


def complement() -> arteantiguedades10.obrasarteantiguedades:
    return arteantiguedades10.obrasarteantiguedades(
        TipoBien='01',
        TituloAdquirido='01',
        FechaAdquisicion=date(2020, 1, 1),
        CaracterísticasDeObraoPieza='01',
    )


def test_a_document_carrying_it(make_invoice: MakeInvoice, builds_validates_seals: Check) -> None:
    cadena = builds_validates_seals(make_invoice(totals=False, Complemento=[complement()]))
    assert '|1.0|01|01|' in cadena
