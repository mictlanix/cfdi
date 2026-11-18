import socket
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from mictlanix.cfdi import (
    CSD,
    Comprobante,
    Concepto,
    ConceptoImpuestos,
    ConceptoTraslado,
    Emisor,
    Impuestos,
    Receptor,
    Traslado,
)

# Inside the validity period of the SAT's public test CSD in tests/fixtures/csd/.
FECHA = datetime(2026, 11, 17, 12, 0, 0)
FIXTURES = Path(__file__).parent / 'fixtures'


@dataclass(frozen=True)
class CsdFiles:
    """The SAT's public test CSD (see tests/fixtures/csd/README.md)."""

    certificate: bytes
    private_key: bytes
    password: str


@pytest.fixture(scope='session')
def csd_files() -> CsdFiles:
    folder = FIXTURES / 'csd'
    return CsdFiles(
        certificate=(folder / 'eku9003173c9.cer').read_bytes(),
        private_key=(folder / 'eku9003173c9.key').read_bytes(),
        # Published by the SAT for every test taxpayer; see the README.
        password='12345678a',
    )


@pytest.fixture(scope='session')
def csd(csd_files: CsdFiles) -> CSD:
    return CSD.load(csd_files.certificate, csd_files.private_key, csd_files.password)


class NetworkBlockedError(RuntimeError):
    """Raised when a test tries to open a network connection."""


def _blocked(*args: object, **kwargs: object) -> None:
    raise NetworkBlockedError('tests must not use the network')


@pytest.fixture(autouse=True)
def _no_network(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setattr(socket.socket, 'connect', _blocked)
    monkeypatch.setattr(socket.socket, 'connect_ex', _blocked)
    yield


def invoice(*, totals: bool = True, **changes: Any) -> Comprobante:
    """The invoice of quickstart.md scenario 1; with ``totals``, its derived values set by hand."""
    values: dict[str, Any] = {
        'Fecha': FECHA,
        'TipoDeComprobante': 'I',
        'Moneda': 'MXN',
        'Exportacion': '01',
        'FormaPago': '03',
        'MetodoPago': 'PUE',
        'LugarExpedicion': '42501',
        'Emisor': Emisor(Rfc='EKU9003173C9', Nombre='ESCUELA KEMPER URGATE', RegimenFiscal='601'),
        'Receptor': Receptor(
            Rfc='URE180429TM6',
            Nombre='UNIVERSIDAD ROBOTICA ESPAÑOLA',
            DomicilioFiscalReceptor='86991',
            RegimenFiscalReceptor='601',
            UsoCFDI='G03',
        ),
        'Conceptos': [
            Concepto(
                ClaveProdServ='01010101',
                Cantidad=Decimal('1'),
                ClaveUnidad='ACT',
                Descripcion='Venta',
                ValorUnitario=Decimal('100.00'),
                Importe=Decimal('100.00'),
                ObjetoImp='02',
                Impuestos=ConceptoImpuestos(
                    Traslados=[
                        ConceptoTraslado(
                            Base=Decimal('100.00'),
                            Impuesto='002',
                            TipoFactor='Tasa',
                            TasaOCuota=Decimal('0.160000'),
                            Importe=Decimal('16.00'),
                        )
                    ]
                ),
            )
        ],
    }
    if totals:
        values['SubTotal'] = Decimal('100.00')
        values['Total'] = Decimal('116.00')
        values['Impuestos'] = Impuestos(
            TotalImpuestosTrasladados=Decimal('16.00'),
            Traslados=[
                Traslado(
                    Base=Decimal('100.00'),
                    Impuesto='002',
                    TipoFactor='Tasa',
                    TasaOCuota=Decimal('0.160000'),
                    Importe=Decimal('16.00'),
                )
            ],
        )
    values.update(changes)
    return Comprobante(**values)


@pytest.fixture
def make_invoice() -> Callable[..., Comprobante]:
    return invoice
