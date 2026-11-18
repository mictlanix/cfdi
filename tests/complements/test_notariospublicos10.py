"""Notarios Públicos 1.0 (document level), built, validated and sealed."""

from collections.abc import Callable
from datetime import date
from decimal import Decimal as D

from mictlanix.cfdi import Comprobante, notariospublicos10

MakeInvoice = Callable[..., Comprobante]
Check = Callable[[Comprobante], str]


def complement() -> notariospublicos10.NotariosPublicos:
    return notariospublicos10.NotariosPublicos(
        DescInmuebles=[
            notariospublicos10.DescInmueble(
                TipoInmueble='01',
                Calle='Principal',
                Municipio='Pachuca',
                Estado='13',
                Pais='MEX',
                CodigoPostal='42000',
            )
        ],
        DatosOperacion=notariospublicos10.DatosOperacion(
            NumInstrumentoNotarial=1,
            FechaInstNotarial=date(2026, 11, 1),
            MontoOperacion=D('1000000.00'),
            Subtotal=D('100.00'),
            IVA=D('16.00'),
        ),
        DatosNotario=notariospublicos10.DatosNotario(
            CURP='CACX760510MGTSHC04', NumNotaria=1, EntidadFederativa='13'
        ),
        DatosEnajenante=notariospublicos10.DatosEnajenante(
            CoproSocConyugalE='No',
            DatosUnEnajenante=notariospublicos10.DatosUnEnajenante(
                Nombre='JUAN',
                ApellidoPaterno='PEREZ',
                RFC='CACX7605101P8',
                CURP='CACX760510MGTSHC04',
            ),
        ),
        DatosAdquiriente=notariospublicos10.DatosAdquiriente(
            CoproSocConyugalE='No',
            DatosUnAdquiriente=notariospublicos10.DatosUnAdquiriente(
                Nombre='ANA', RFC='URE180429TM6'
            ),
        ),
    )


def test_a_document_carrying_it(make_invoice: MakeInvoice, builds_validates_seals: Check) -> None:
    cadena = builds_validates_seals(make_invoice(totals=False, Complemento=[complement()]))
    assert '|1.0|01|Principal|' in cadena
