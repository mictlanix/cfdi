"""Servicios Parciales de Construcción 1.0 (document level), built, validated and sealed."""

from collections.abc import Callable

from mictlanix.cfdi import Comprobante, servicioparcialconstruccion10

MakeInvoice = Callable[..., Comprobante]
Check = Callable[[Comprobante], str]


def complement() -> servicioparcialconstruccion10.parcialesconstruccion:
    return servicioparcialconstruccion10.parcialesconstruccion(
        NumPerLicoAut='LIC-1',
        Inmueble=servicioparcialconstruccion10.Inmueble(
            Calle='Principal', Municipio='Pachuca', Estado='13', CodigoPostal='42000'
        ),
    )


def test_a_document_carrying_it(make_invoice: MakeInvoice, builds_validates_seals: Check) -> None:
    cadena = builds_validates_seals(make_invoice(totals=False, Complemento=[complement()]))
    assert '|1.0|LIC-1|' in cadena
