# Quickstart: validating the feature end to end

**Date**: 2026-11-17 | **Plan**: [plan.md](plan.md) | **API**: [contracts/public-api.md](contracts/public-api.md)

These scenarios prove the feature works. They are the acceptance checks for the three user
stories; each maps to tests that are written before the code.

## Prerequisites

- uv, with Python 3.12 (the repository's `.python-version`).
- No network, no real certificates: the SAT's public test CSD is in `tests/fixtures/csd/`.

```sh
uv sync
```

## Gates (must all pass before any merge)

```sh
uv run pytest -q
uv run ruff check
uv run ruff format --check
uv run mypy src
```

Expected: all four succeed. `pytest` passes with the network disabled.

## Scenario 1 (P1): seal an invoice from business data

```python
from datetime import datetime
from decimal import Decimal

from mictlanix.cfdi import (
    CSD, Comprobante, Concepto, ConceptoImpuestos, ConceptoTraslado, Emisor, Receptor,
    original_string, read, seal, validate,
)

csd = CSD.load(certificate=cer_bytes, private_key=key_bytes, password=password)

invoice = Comprobante(
    Fecha=datetime(2026, 11, 17, 12, 0, 0),   # inside the test CSD's validity period
    TipoDeComprobante='I',
    Moneda='MXN',
    Exportacion='01',
    FormaPago='03',
    MetodoPago='PUE',
    LugarExpedicion='42501',
    Emisor=Emisor(Rfc='EKU9003173C9', Nombre='ESCUELA KEMPER URGATE', RegimenFiscal='601'),
    Receptor=Receptor(
        Rfc='URE180429TM6', Nombre='UNIVERSIDAD ROBOTICA ESPAÑOLA',
        DomicilioFiscalReceptor='86991', RegimenFiscalReceptor='601', UsoCFDI='G03',
    ),
    Conceptos=[
        Concepto(
            ClaveProdServ='01010101', Cantidad=Decimal('1'), ClaveUnidad='ACT',
            Descripcion='Venta', ValorUnitario=Decimal('100.00'), Importe=Decimal('100.00'),
            ObjetoImp='02',
            Impuestos=ConceptoImpuestos(Traslados=[
                ConceptoTraslado(
                    Base=Decimal('100.00'), Impuesto='002', TipoFactor='Tasa',
                    TasaOCuota=Decimal('0.160000'), Importe=Decimal('16.00'),
                ),
            ]),
        ),
    ],
)

# The recipient is a specific taxpayer, not the general public: an invoice to
# XAXX010101000 would also need InformacionGlobal.
assert validate(invoice) == []
sealed = seal(invoice, csd)
```

Expected:

- `read(sealed)` has `SubTotal == Decimal('100.00')`, `Total == Decimal('116.00')` and a
  document-level `Impuestos` with one `Traslado` of `16.00`: none were supplied by the caller.
- `sealed` is valid against the SAT's XSDs.
- `read(sealed).Sello` verifies, with the certificate's public key, against
  `original_string(sealed)`, and equals the committed known result for this fixture.
- `repr(csd)` shows the certificate number and validity dates and nothing else.

## Scenario 2 (P1): validation names the node and the rule

Change the invoice so `TipoDeComprobante='Z'` and the recipient's `Rfc='x'`.

Expected: `validate` returns one violation per problem, including
`node='/cfdi:Comprobante'`, `attribute='TipoDeComprobante'`, `rule='cvc-enumeration-valid'` and
`node='/cfdi:Comprobante/cfdi:Receptor'`, `attribute='Rfc'`, `rule='cvc-pattern-valid'`. `seal`
raises `ValidationError` carrying the same violations and returns nothing.

## Scenario 3 (P1): credit note and payment receipt

- Build a type E document related to an earlier UUID (`CfdiRelacionados` with `TipoRelacion`
  `01`), then validate and seal it as in scenario 1.
- Build a payment document with `payment_comprobante(...)` and a `pagos20.Pagos` holding one
  `Pago` that settles one `DoctoRelacionado` with IVA at 16%.

Expected: both seal. The payment document has currency `XXX`, zero `SubTotal` and `Total`, the
single fixed concept, and a `Pagos` complement whose `Totales` and `ImpuestosP` were computed;
the complement's values appear in `original_string(sealed)`.

## Scenario 4 (P1): CSD failures are specific and leak nothing

Expected, each asserted on the exception class and its typed fields, and each with the password
and key bytes absent from `str(error)` and `repr(error)`:

| Input | Result |
|-------|--------|
| Wrong password | `CsdError`, `reason == wrong_password` |
| Key from a different certificate | `CsdError`, `reason == key_mismatch` |
| Bytes that are not a certificate | `CsdError`, `reason == invalid_certificate` |
| `Fecha` after the certificate expires | `CertificateValidityError` from `seal` |

## Scenario 5 (P1): read a stamped CFDI

With the stamped sample in `tests/fixtures/stamped/`:

Expected: `timbre(read(xml))` gives the sample's `UUID`, `FechaTimbrado`, `SelloSAT`,
`NoCertificadoSAT` and `RfcProvCertif`; `tfd_original_string(xml)` equals the sample's known TFD
original string; `qr_data(read(xml))` gives the verification address with the sample's UUID,
both RFCs, total and the last eight characters of the issuer's seal. Reading the sealed but
unstamped document from scenario 1 and calling `timbre` raises `NotStampedError`.

## Scenario 6 (P2, P3): every document type and complement

Tests under `tests/complements/` cover every document type (I, E, P, N, T) and every complement
in [data-model.md](data-model.md) section 1.3 except `tfd11`, which is covered by the reading
tests. Pagos 2.0 and types I, E and P are in `test_documents_p1.py`; each other complement has
its own file. Each test builds a document, validates it, seals it and checks that the sealed XML
is valid against the SAT's XSDs and that the complement's values are in the original string.

```sh
uv run pytest -q tests/complements
```

Expected: one passing case per complement delivered so far; 29 complements and 5 document types
when the feature is complete.

## Scenario 7: retired versions cannot be emitted

Expected: `mictlanix.cfdi` exposes no module for Carta Porte 2.0 or 3.0, Comercio Exterior 1.1, Pagos
1.0, Estado de Cuenta de Combustibles 1.1 or Terceros. Reading a stamped sample that carries
Carta Porte 3.0 succeeds and returns it as `RawXml`; passing that document to `to_xml` or `seal`
raises `ValidationError`.

## Scenario 8: the SAT artifacts are what the SAT published

```sh
uv run pytest -q tests/test_sat_artifacts.py tests/test_generated_models.py
```

Expected: every vendored file matches the SHA-256 in `manifest.json` and has a publication date;
regenerating the models from the vendored XSDs produces exactly the committed modules.
