# Mictlanix CFDI Library

Python library for Mexican CFDI 4.0 electronic invoices. It builds documents of every type with
their complements, derives their totals, validates them against the SAT's schemas and Anexo 20
rules, seals them with the issuer's CSD, and reads stamped documents. Talking to a PAC is not
part of this release.

Everything runs offline: the SAT's XSDs, stylesheets and the catalog data the rules use ship
inside the package.

## Installation

```sh
pip install mictlanix-cfdi
```

```python
import mictlanix.cfdi
```

Requires Python 3.12+.

## Sealing an invoice

```python
from datetime import datetime
from decimal import Decimal

from mictlanix.cfdi import (
    CSD,
    Comprobante,
    Concepto,
    ConceptoImpuestos,
    ConceptoTraslado,
    Emisor,
    Receptor,
    seal,
    validate,
)

csd = CSD.load(certificate=cer_bytes, private_key=key_bytes, password=password)

invoice = Comprobante(
    Fecha=datetime(2026, 11, 17, 12, 0, 0),
    TipoDeComprobante='I',
    Moneda='MXN',
    Exportacion='01',
    FormaPago='03',
    MetodoPago='PUE',
    LugarExpedicion='42501',
    Emisor=Emisor(Rfc='EKU9003173C9', Nombre='ESCUELA KEMPER URGATE', RegimenFiscal='601'),
    Receptor=Receptor(
        Rfc='URE180429TM6',
        Nombre='UNIVERSIDAD ROBOTICA ESPAÑOLA',
        DomicilioFiscalReceptor='86991',
        RegimenFiscalReceptor='601',
        UsoCFDI='G03',
    ),
    Conceptos=[
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
                    ),
                ]
            ),
        ),
    ],
)

assert validate(invoice) == []  # every violation names its node, attribute and rule
xml = seal(invoice, csd)  # sealed XML, ready for a PAC
```

`SubTotal`, `Total` and the tax summary are derived by the library. A payment receipt is built
with `payment_comprobante`; a stamped document is read with `read`, and `timbre`, `qr_data` and
`tfd_original_string` give its stamp, QR data and the stamp's original string.

## Supported complements

Each complement is a module of `mictlanix.cfdi`, at the version the SAT accepts today:

| Module | Complement |
|--------|-----------|
| `pagos20` | Pagos 2.0 |
| `tfd11` | TimbreFiscalDigital 1.1 (reading) |
| `nomina12` | Nómina 1.2 |
| `cartaporte31` | Carta Porte 3.1 |
| `comercioexterior20` | Comercio Exterior 2.0 |
| `implocal10` | Impuestos Locales 1.0 |
| `divisas10` | Divisas 1.0 |
| `donat11` | Donatarias 1.1 |
| `leyendasfiscales10` | Leyendas Fiscales 1.0 |
| `ine11` | INE 1.1 |
| `aerolineas10` | Aerolíneas 1.0 |
| `detallista` | Detallista 1.3.1 |
| `tpe10` | Turista Pasajero Extranjero 1.0 |
| `ecc12` | Estado de Cuenta de Combustibles 1.2 |
| `consumodecombustibles11` | Consumo de Combustibles 1.1 |
| `gastoshidrocarburos10` | Gastos de Hidrocarburos 1.0 |
| `ingresoshidrocarburos10` | Ingresos de Hidrocarburos 1.0 |
| `notariospublicos10` | Notarios Públicos 1.0 |
| `arteantiguedades10` | Obras de Arte y Antigüedades 1.0 |
| `pagoenespecie10` | Pago en Especie 1.0 |
| `valesdedespensa10` | Vales de Despensa 1.0 |
| `vehiculousado10` | Vehículo Usado 1.0 |
| `renovacionysustitucionvehiculos10` | Renovación y Sustitución de Vehículos 1.0 |
| `certificadodestruccion10` | Certificado de Destrucción 1.0 |
| `servicioparcialconstruccion10` | Servicios Parciales de Construcción 1.0 |
| `registrofiscal10` | CFDI Registro Fiscal 1.0 |
| `pfic10` | PFIC 1.0 |
| `iedu10` | Instituciones Educativas Privadas 1.0 (concept level) |
| `ventavehiculos11` | Venta de Vehículos 1.1 (concept level) |
| `hidrocarburospetroliferos10` | Hidrocarburos y Petrolíferos 1.0 (concept level) |

Retired versions (Carta Porte 2.0 and 3.0, Comercio Exterior 1.1, Pagos 1.0, Estado de Cuenta de
Combustibles 1.1, Terceros) are never emitted. A stamped document carrying one is still read, with
that complement kept as `RawXml`.

## Updating the SAT's files

The SAT's files are vendored unmodified, each recorded in `src/mictlanix/cfdi/sat/manifest.json`
with its URL, SHA-256 and publication date. Updating them is a deliberate change:

```sh
uv run python tools/fetch_sat.py --refresh     # XSDs and stylesheets
uv run python tools/extract_catalogs.py        # catalog data the rules use
uv run python tools/generate_models.py         # regenerate the models from the XSDs
uv run pytest -q
```

## Development

```sh
uv sync
uv run pytest -q
uv run ruff check
uv run ruff format --check
uv run mypy src
```

## License

[MIT](LICENSE)
