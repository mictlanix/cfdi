"""Turista Pasajero Extranjero 1.0 (document level), built, validated and sealed."""

from collections.abc import Callable
from datetime import datetime

from mictlanix.cfdi import Comprobante, tpe10

MakeInvoice = Callable[..., Comprobante]
Check = Callable[[Comprobante], str]


def complement() -> tpe10.TuristaPasajeroExtranjero:
    return tpe10.TuristaPasajeroExtranjero(
        fechadeTransito=datetime(2026, 11, 17, 9, 0, 0),
        tipoTransito='Arribo',
        datosTransito=tpe10.datosTransito(
            Via='Aérea',
            TipoId='Pasaporte',
            NumeroId='G123456',
            Nacionalidad='Estados Unidos',
            EmpresaTransporte='AEROLINEA',
        ),
    )


def test_a_document_carrying_it(make_invoice: MakeInvoice, builds_validates_seals: Check) -> None:
    cadena = builds_validates_seals(make_invoice(totals=False, Complemento=[complement()]))
    assert '|1.0|2026-11-17T09:00:00|Arribo|' in cadena
    assert '|G123456|' in cadena
