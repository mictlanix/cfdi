"""Certificado de Destrucción 1.0 (document level), built, validated and sealed."""

from collections.abc import Callable

from mictlanix.cfdi import Comprobante, certificadodestruccion10

MakeInvoice = Callable[..., Comprobante]
Check = Callable[[Comprobante], str]


def complement() -> certificadodestruccion10.certificadodedestruccion:
    return certificadodestruccion10.certificadodedestruccion(
        Serie='SERIE A',
        NumFolDesVeh='12345678',
        VehiculoDestruido=certificadodestruccion10.VehiculoDestruido(
            Marca='MARCA', TipooClase='SEDAN', Año=2000, NumPlacas='ABC1234', NumFolTarjCir='T1'
        ),
    )


def test_a_document_carrying_it(make_invoice: MakeInvoice, builds_validates_seals: Check) -> None:
    cadena = builds_validates_seals(make_invoice(totals=False, Complemento=[complement()]))
    assert '|1.0|SERIE A|12345678|' in cadena
