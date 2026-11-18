"""Instituciones Educativas Privadas 1.0 (concept level), built, validated and sealed."""

from collections.abc import Callable
from dataclasses import replace

from mictlanix.cfdi import Comprobante, iedu10

MakeInvoice = Callable[..., Comprobante]
Check = Callable[[Comprobante], str]


def complement() -> iedu10.instEducativas:
    return iedu10.instEducativas(
        nombreAlumno='ALUMNO', CURP='CACX760510MGTSHC04', nivelEducativo='Primaria', autRVOE='12345'
    )


def test_a_concept_carrying_it(make_invoice: MakeInvoice, builds_validates_seals: Check) -> None:
    invoice = make_invoice(totals=False)
    concepto = replace(invoice.Conceptos[0], ComplementoConcepto=[complement()])
    cadena = builds_validates_seals(replace(invoice, Conceptos=[concepto]))
    assert '|1.0|ALUMNO|CACX760510MGTSHC04|Primaria|12345|' in cadena
