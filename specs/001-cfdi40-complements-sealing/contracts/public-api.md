# Contract: Public API of `mictlanix.cfdi`

**Date**: 2026-11-17 | **Plan**: [../plan.md](../plan.md) | **Models**: [../data-model.md](../data-model.md)

This is the interface the library exposes to callers. Everything here is importable from
`mictlanix.cfdi`, fully typed, and covered by semantic versioning. Anything not listed here, and every
module whose name starts with an underscore, is internal.

`mictlanix` is a namespace package; `mictlanix.cfdi` is this library. `mictlanix.cfdi.pac` is
reserved for the PAC clients (mictlanix/cfdi#2, #3) and is not part of this contract.

All functions are synchronous and pure: no network, no file access other than reading the
library's own packaged SAT files, no global state other than caches of compiled SAT schemas and
stylesheets. Inputs and outputs that are XML are `bytes`.

## Exports

```python
# CFDI 4.0 nodes (generated; see data-model.md 1.2)
Comprobante, InformacionGlobal, CfdiRelacionados, CfdiRelacionado, Emisor, Receptor,
Concepto, ConceptoImpuestos, ConceptoTraslado, ConceptoRetencion, ACuentaTerceros,
InformacionAduanera, CuentaPredial, Parte, ParteInformacionAduanera,
Impuestos, Traslado, Retencion

# Complement namespaces (one module each; see data-model.md 1.3)
pagos20, tfd11                                               # P1
nomina12, cartaporte31, comercioexterior20, implocal10       # P2
divisas10, donat11, leyendasfiscales10, ine11, aerolineas10, detallista, tpe10, ecc12,
consumodecombustibles11, gastoshidrocarburos10, ingresoshidrocarburos10, notariospublicos10,
arteantiguedades10, pagoenespecie10, valesdedespensa10, vehiculousado10,
renovacionysustitucionvehiculos10, certificadodestruccion10, servicioparcialconstruccion10,
registrofiscal10, pfic10, iedu10, ventavehiculos11, hidrocarburospetroliferos10       # P3

# Supporting types
RawXml, DocumentComplement, ConceptComplement, CSD, Violation, QrData

# Functions
payment_comprobante, compute, validate, to_xml, original_string, seal,
read, timbre, tfd_original_string, qr_data

# Errors
CfdiError, ValidationError, CsdError, CertificateValidityError,
ParseError, NotCfdi40Error, NotStampedError

__version__
```

## Functions

### Building

```python
def payment_comprobante(
    *,
    Emisor: Emisor,
    Receptor: Receptor,
    Fecha: datetime,
    LugarExpedicion: str,
    Pagos: pagos20.Pagos,
    Serie: str | None = None,
    Folio: str | None = None,
    CfdiRelacionados: list[CfdiRelacionados] | None = None,
) -> Comprobante
```

Returns a type P `Comprobante` with the fixed values the standard imposes (currency `XXX`, zero
amounts, the single fixed concept, `Exportacion` `01`) and `Pagos` as its complement. Every
other document type is built by constructing `Comprobante` directly.

```python
def compute(comprobante: Comprobante) -> Comprobante
```

Returns a copy with the derived values filled in (data-model.md section 3). A derived field that
is `None` is computed; one the caller set is kept. Never raises for a well-typed document: if
`Moneda` is not a currency in the SAT's catalog, the derived fields are left unset and validation
reports `Moneda`; if a Pagos 2.0 input cannot be used (`EquivalenciaDR` zero or absent,
`TipoCambioP` absent, or a `MonedaP` that is not in the catalog), `ImpuestosP` and `Totales` are
left unset and validation reports the missing `Totales`, which is the node the XSD requires and
not the attribute that caused it. The general rule: any value that makes the arithmetic
impossible (a non-finite or unroundable amount, on the document, Pagos 2.0 or Impuestos Locales)
leaves the fields it feeds unset.

### Validation

```python
def validate(comprobante: Comprobante) -> list[Violation]
```

Computes derived values, then checks the document against `cfdv40.xsd`, `catCFDI.xsd`,
`tdCFDI.xsd`, the XSD of each complement it carries, and the implemented Anexo 20 rules. Returns
every violation found; an empty list means valid. Does not raise for an invalid document.

- XSD violations: `rule` is the XSD constraint name, such as `cvc-pattern-valid`.
- Anexo 20 violations: `rule` is the SAT's code (`CFDI40` followed by digits).
- Complement placement: `rule` is `complement-document-type` or `complement-level`.
- Values that cannot be written: a text value holding a character XML 1.0 does not allow has
  `rule` `xml-invalid-character`, and a `datetime` or `time` carrying a time zone has `rule`
  `datetime-not-naive` (the SAT's formats have no offset). Each names the node and attribute.
  The rest of the document is still checked, with that value left out.
- A document holding `RawXml` under `Complemento` or `ComplementoConcepto` cannot be serialized,
  so `validate` returns one violation with `rule` `complement-not-modelled` and checks nothing
  else.
- The Anexo 20 rules run whether or not the XSD check found violations; a rule that needs a
  value the XSD has already rejected reports nothing.
- The document does not need to be sealed.

### XML and original string

```python
def to_xml(comprobante: Comprobante) -> bytes
```

Serializes the document as CFDI 4.0 XML (UTF-8, with the SAT's namespace prefixes and
`xsi:schemaLocation`). Does not compute or validate. Raises `ValidationError`, with one violation
whose `rule` is `complement-not-modelled`, if the document holds a `RawXml` under `Complemento`
or `ComplementoConcepto`, or with `xml-invalid-character` or `datetime-not-naive` violations if
a value cannot be written. Raises `ParseError` if a `RawXml` under `Addenda` is not one
well-formed element.

```python
def original_string(xml: bytes) -> str
```

The original string of a CFDI 4.0 document, produced by the SAT's `cadenaoriginal_4_0.xslt`.
Raises `ParseError` or `NotCfdi40Error`.

### Sealing

```python
class CSD:
    @classmethod
    def load(cls, certificate: bytes, private_key: bytes, password: str) -> CSD
    NoCertificado: str
    valid_from: datetime
    valid_to: datetime
```

`certificate` is the `.cer` content (DER) and `private_key` the `.key` content (encrypted
PKCS#8, DER). Raises `CsdError` with a `reason`, and nothing else: a key that is not encrypted
is `invalid_key`, and a certificate whose serial number is not 20 ASCII digits is
`invalid_certificate`. The password is not stored. `valid_from` and `valid_to` are naive
datetimes in Mexico City time (a fixed UTC-6 since October 2022), converted from the UTC the
certificate records, the same convention mbe uses for stored certificates.

```python
def seal(comprobante: Comprobante, csd: CSD) -> bytes
```

Computes derived values, sets `NoCertificado` and `Certificado`, validates, computes the original
string, signs it with RSA-SHA256 and returns the sealed XML, ready for a PAC.

- Raises `ValidationError` (with all violations) if the document is invalid; nothing is signed.
- Raises `CertificateValidityError` if `Fecha` is outside the certificate's validity period.
- Raises `ParseError` if a `RawXml` under `Addenda` is not one well-formed element.
- `Fecha` is the naive local time of the place of issue, as Anexo 20 defines it, and is compared
  with the certificate's validity period in Mexico City time. For a place of issue in another
  time zone the result can differ from the PAC's by that zone's offset (one or two hours) at
  either end of the period; the PAC has the final word.
- Deterministic: the same document and CSD always give the same bytes.
- A document that already carries a `TimbreFiscalDigital` gets no special treatment: sealing it
  again keeps the old stamp, which no longer matches the new seal. Do not seal a stamped document.

### Reading

```python
def read(xml: bytes) -> Comprobante
```

Parses a CFDI 4.0 document, sealed or stamped, into models. Complements the library models
become typed objects; other elements under `Complemento`, `ComplementoConcepto` and `Addenda`
become `RawXml`. Does not validate and does not verify seals. Raises `NotCfdi40Error`, or
`ParseError` when the input is not well-formed XML or cannot be turned into the models (a
required attribute is missing, or a value cannot be read as its type), naming the node and
attribute in the second case. No other exception escapes.

```python
def timbre(comprobante: Comprobante) -> tfd11.TimbreFiscalDigital
```

The document's TimbreFiscalDigital 1.1 (`UUID`, `FechaTimbrado`, `SelloSAT`,
`NoCertificadoSAT`, `RfcProvCertif`, `SelloCFD`, and `Leyenda` when present). Raises
`NotStampedError`.

```python
def tfd_original_string(xml: bytes) -> str
```

The original string of the document's TFD, produced by the SAT's
`cadenaoriginal_TFD_1_1.xslt`. Raises `ParseError`, `NotCfdi40Error` or `NotStampedError`.

```python
def qr_data(comprobante: Comprobante) -> QrData
```

The data for the SAT verification QR. Raises `NotStampedError` if the document has no
`TimbreFiscalDigital`, no `Sello` or no `Total`.

## Guarantees

- **Typed errors**: callers branch on the exception class, on `CsdError.reason` and on
  `Violation.rule`; no message text needs to be parsed.
- **Secrets**: no exception, `repr` or log output contains key material or a password. The
  library does not log.
- **Offline**: no function opens a network connection.
- **Retired versions**: there is no model for Carta Porte 2.0 or 3.0, Comercio Exterior 1.1,
  Pagos 1.0, Estado de Cuenta de Combustibles 1.1 or Terceros, and `to_xml` and `seal` refuse
  documents that carry them as `RawXml`.
- **Stability**: removing or changing anything in this file is a breaking change, except removing
  a complement version the SAT has retired, which happens in a minor release and is recorded in
  the changelog with the SAT's end date (constitution, principle I).
