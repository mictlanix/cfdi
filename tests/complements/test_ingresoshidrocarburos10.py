"""Ingresos de Hidrocarburos 1.0 (document level), built, validated and sealed."""

from collections.abc import Callable
from datetime import date
from decimal import Decimal as D

from mictlanix.cfdi import Comprobante, ingresoshidrocarburos10

MakeInvoice = Callable[..., Comprobante]
Check = Callable[[Comprobante], str]
UUID = '5FB2822E-396D-4725-8521-CDC4BDD20CCF'


def complement() -> ingresoshidrocarburos10.IngresosHidrocarburos:
    return ingresoshidrocarburos10.IngresosHidrocarburos(
        NumeroContrato='CNH-R01-L01-A1/2015',
        ContraprestacionPagadaOperador=D('100.00'),
        Porcentaje=D('100.000'),
        DocumentoRelacionado=[
            ingresoshidrocarburos10.DocumentoRelacionado(
                FolioFiscalVinculado=UUID, FechaFolioFiscalVinculado=date(2026, 1, 1), Mes='01'
            )
        ],
    )


def test_a_document_carrying_it(make_invoice: MakeInvoice, builds_validates_seals: Check) -> None:
    cadena = builds_validates_seals(make_invoice(totals=False, Complemento=[complement()]))
    assert '|1.0|CNH-R01-L01-A1/2015|100.00|' in cadena
