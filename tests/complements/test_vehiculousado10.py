"""Vehículo Usado 1.0 (document level), built, validated and sealed."""

from collections.abc import Callable
from decimal import Decimal as D

from mictlanix.cfdi import Comprobante, vehiculousado10

MakeInvoice = Callable[..., Comprobante]
Check = Callable[[Comprobante], str]


def complement() -> vehiculousado10.VehiculoUsado:
    return vehiculousado10.VehiculoUsado(
        montoAdquisicion=D('100000.00'),
        montoEnajenacion=D('80000.00'),
        claveVehicular='1234567',
        marca='MARCA',
        tipo='SEDAN',
        modelo='2020',
        valor=D('80000.00'),
    )


def test_a_document_carrying_it(make_invoice: MakeInvoice, builds_validates_seals: Check) -> None:
    cadena = builds_validates_seals(make_invoice(totals=False, Complemento=[complement()]))
    assert '|1.0|100000.00|80000.00|1234567|' in cadena
