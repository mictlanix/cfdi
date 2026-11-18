"""Gastos de Hidrocarburos 1.0 (document level), built, validated and sealed."""

from collections.abc import Callable
from decimal import Decimal as D

from mictlanix.cfdi import Comprobante, gastoshidrocarburos10

MakeInvoice = Callable[..., Comprobante]
Check = Callable[[Comprobante], str]
UUID = '5FB2822E-396D-4725-8521-CDC4BDD20CCF'


def complement() -> gastoshidrocarburos10.GastosHidrocarburos:
    return gastoshidrocarburos10.GastosHidrocarburos(
        NumeroContrato='CNH-R01-L01-A1/2015',
        Erogacion=[
            gastoshidrocarburos10.Erogacion(
                TipoErogacion='Costo',
                MontocuErogacion=D('100.00'),
                Porcentaje=D('99.999'),
                DocumentoRelacionado=[
                    gastoshidrocarburos10.DocumentoRelacionado(
                        OrigenErogacion='Nacional',
                        FolioFiscalVinculado=UUID,
                        RFCProveedor='EKU9003173C9',
                        MontoTotalIVA=D('16.00'),
                        MontoRetencionISR=D('0.00'),
                        MontoRetencionIVA=D('0.00'),
                        MontoRetencionOtrosImpuestos=D('0.00'),
                        Mes='01',
                        MontoTotalErogaciones=D('100.00'),
                    )
                ],
            )
        ],
    )


def test_a_document_carrying_it(make_invoice: MakeInvoice, builds_validates_seals: Check) -> None:
    cadena = builds_validates_seals(make_invoice(totals=False, Complemento=[complement()]))
    assert '|1.0|CNH-R01-L01-A1/2015|' in cadena
