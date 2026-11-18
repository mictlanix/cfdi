"""INE 1.1 (document level), built, validated and sealed."""

from collections.abc import Callable

from mictlanix.cfdi import Comprobante, ine11

MakeInvoice = Callable[..., Comprobante]
Check = Callable[[Comprobante], str]


def complement() -> ine11.INE:
    return ine11.INE(
        TipoProceso='Ordinario', TipoComite='Ejecutivo Nacional', IdContabilidad=123456
    )


def test_a_document_carrying_it(make_invoice: MakeInvoice, builds_validates_seals: Check) -> None:
    cadena = builds_validates_seals(make_invoice(totals=False, Complemento=[complement()]))
    assert '|1.1|Ordinario|Ejecutivo Nacional|123456|' in cadena
