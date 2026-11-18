"""Venta de Vehículos 1.1 (concept level), built, validated and sealed."""

from collections.abc import Callable
from dataclasses import replace

from mictlanix.cfdi import Comprobante, ventavehiculos11

MakeInvoice = Callable[..., Comprobante]
Check = Callable[[Comprobante], str]


def complement() -> ventavehiculos11.VentaVehiculos:
    return ventavehiculos11.VentaVehiculos(ClaveVehicular='1234567', Niv='1HGCM82633A004352')


def test_a_concept_carrying_it(make_invoice: MakeInvoice, builds_validates_seals: Check) -> None:
    invoice = make_invoice(totals=False)
    concepto = replace(invoice.Conceptos[0], ComplementoConcepto=[complement()])
    cadena = builds_validates_seals(replace(invoice, Conceptos=[concepto]))
    assert '|1.1|1234567|1HGCM82633A004352|' in cadena
