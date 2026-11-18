"""Several complements on one document, and complements at the wrong level (FR-024)."""

from collections.abc import Callable

import pytest

from mictlanix.cfdi import (
    CSD,
    Comprobante,
    ValidationError,
    leyendasfiscales10,
    registrofiscal10,
    seal,
    validate,
)
from tests.complements.test_iedu10 import complement as iedu

MakeInvoice = Callable[..., Comprobante]
Check = Callable[[Comprobante], str]


def test_two_document_complements_at_once(
    make_invoice: MakeInvoice, builds_validates_seals: Check
) -> None:
    complemento = [
        leyendasfiscales10.LeyendasFiscales(
            Leyenda=[leyendasfiscales10.Leyenda(textoLeyenda='Leyenda de prueba')]
        ),
        registrofiscal10.CFDIRegistroFiscal(Folio='0000000000000001'),
    ]
    cadena = builds_validates_seals(make_invoice(totals=False, Complemento=complemento))
    assert '|1.0|Leyenda de prueba|' in cadena and '|1.0|0000000000000001|' in cadena


def test_a_concept_complement_under_complemento_is_refused(
    make_invoice: MakeInvoice, csd: CSD
) -> None:
    document = make_invoice(totals=False, Complemento=[iedu()])
    found = [v.node for v in validate(document) if v.rule == 'complement-level']
    assert found == ['/cfdi:Comprobante/cfdi:Complemento/iedu:instEducativas']
    with pytest.raises(ValidationError):
        seal(document, csd)
