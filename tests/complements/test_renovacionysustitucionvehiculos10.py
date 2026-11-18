"""Renovación y Sustitución de Vehículos 1.0 (document level), built, validated and sealed."""

from collections.abc import Callable
from decimal import Decimal as D

from mictlanix.cfdi import Comprobante, renovacionysustitucionvehiculos10

MakeInvoice = Callable[..., Comprobante]
Check = Callable[[Comprobante], str]


def complement() -> renovacionysustitucionvehiculos10.renovacionysustitucionvehiculos:
    return renovacionysustitucionvehiculos10.renovacionysustitucionvehiculos(
        TipoDeDecreto='01',
        DecretoRenovVehicular=renovacionysustitucionvehiculos10.DecretoRenovVehicular(
            VehEnaj='01',
            VehiculosUsadosEnajenadoPermAlFab=[
                renovacionysustitucionvehiculos10.VehiculosUsadosEnajenadoPermAlFab(
                    PrecioVehUsado=D('50000.00'),
                    TipoVeh='01',
                    Marca='MARCA',
                    Foliofiscal='5FB2822E-396D-4725-8521-CDC4BDD20CCF',
                    TipooClase='SEDAN',
                    Año=2010,
                    NumSerie='1HGCM82633A004352',
                    NIV='1HGCM82633A004352',
                    NumPlacas='ABC1234',
                    NumMotor='M1',
                    NumFolTarjCir='T1',
                )
            ],
            VehiculoNuvoSemEnajenadoFabAlPerm=renovacionysustitucionvehiculos10.RenovVehiculoNuvoSemEnajenadoFabAlPerm(
                Año=2026, Modelo='MODELO', NumPlacas='XYZ1234'
            ),
        ),
    )


def test_a_document_carrying_it(make_invoice: MakeInvoice, builds_validates_seals: Check) -> None:
    cadena = builds_validates_seals(make_invoice(totals=False, Complemento=[complement()]))
    assert '|1.0|01|' in cadena
