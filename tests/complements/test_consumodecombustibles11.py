"""Consumo de Combustibles 1.1 (document level), built, validated and sealed."""

from collections.abc import Callable
from datetime import datetime
from decimal import Decimal as D

from mictlanix.cfdi import Comprobante, consumodecombustibles11

MakeInvoice = Callable[..., Comprobante]
Check = Callable[[Comprobante], str]


def complement() -> consumodecombustibles11.ConsumoDeCombustibles:
    return consumodecombustibles11.ConsumoDeCombustibles(
        numeroDeCuenta='1234',
        subTotal=D('200.00'),
        total=D('232.00'),
        Conceptos=[
            consumodecombustibles11.ConceptoConsumoDeCombustibles(
                identificador='1',
                fecha=datetime(2026, 11, 10, 8, 0, 0),
                rfc='EKU9003173C9',
                claveEstacion='1234',
                tipoCombustible='1',
                cantidad=D('10.000'),
                nombreCombustible='Gasolina',
                folioOperacion='F1',
                valorUnitario=D('20.00'),
                importe=D('200.00'),
                Determinados=[
                    consumodecombustibles11.Determinado(
                        impuesto='IVA', tasaOCuota=D('0.160000'), importe=D('32.00')
                    )
                ],
            )
        ],
    )


def test_a_document_carrying_it(make_invoice: MakeInvoice, builds_validates_seals: Check) -> None:
    cadena = builds_validates_seals(make_invoice(totals=False, Complemento=[complement()]))
    assert '|1.1|monedero electrónico|1234|' in cadena
