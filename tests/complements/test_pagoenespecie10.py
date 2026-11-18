"""Pago en Especie 1.0 (document level), built, validated and sealed."""

from collections.abc import Callable

from mictlanix.cfdi import Comprobante, pagoenespecie10

MakeInvoice = Callable[..., Comprobante]
Check = Callable[[Comprobante], str]


def complement() -> pagoenespecie10.PagoEnEspecie:
    return pagoenespecie10.PagoEnEspecie(
        CvePIC='EKU9003173C9-20260101-001',
        FolioSolDon='PE-26-00001',
        PzaArtNombre='Obra',
        PzaArtTecn='Oleo',
        PzaArtAProd='2020',
        PzaArtDim='1x1',
    )


def test_a_document_carrying_it(make_invoice: MakeInvoice, builds_validates_seals: Check) -> None:
    cadena = builds_validates_seals(make_invoice(totals=False, Complemento=[complement()]))
    assert '|1.0|EKU9003173C9-20260101-001|PE-26-00001|' in cadena
