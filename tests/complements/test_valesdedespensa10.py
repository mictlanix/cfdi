"""Vales de Despensa 1.0 (document level), built, validated and sealed."""

from collections.abc import Callable
from datetime import datetime
from decimal import Decimal as D

from mictlanix.cfdi import Comprobante, valesdedespensa10

MakeInvoice = Callable[..., Comprobante]
Check = Callable[[Comprobante], str]


def complement() -> valesdedespensa10.ValesDeDespensa:
    return valesdedespensa10.ValesDeDespensa(
        numeroDeCuenta='1234',
        total=D('100.00'),
        Conceptos=[
            valesdedespensa10.Concepto(
                identificador='1',
                fecha=datetime(2026, 11, 10, 8, 0, 0),
                rfc='CACX7605101P8',
                curp='CACX760510MGTSHC04',
                nombre='XOCHILT CASAS CHAVEZ',
                importe=D('100.00'),
            )
        ],
    )


def test_a_document_carrying_it(make_invoice: MakeInvoice, builds_validates_seals: Check) -> None:
    cadena = builds_validates_seals(make_invoice(totals=False, Complemento=[complement()]))
    assert '|1.0|monedero electrónico|' in cadena
