# Data Model: CFDI 4.0 Standard, Current Complements and Document Sealing

**Date**: 2026-11-17 | **Plan**: [plan.md](plan.md) | **Research**: [research.md](research.md)

The SAT's XSDs define the document models; this file does not repeat their attributes. It
records how an XSD becomes a model, where the models deviate from the XSD and why, the values
the library derives, and the types that are not generated.

## 1. Generated models

All generated classes are `@dataclass(frozen=True, kw_only=True)`. Field order is XSD order,
which is also the order the mapper writes.

### 1.1 Mapping rules

| XSD construct | Model |
|---------------|-------|
| Element with attributes or mixed children | One class, named after the element |
| Attribute | Field with the attribute's exact name |
| Child element, `maxOccurs` 1 | Field with the element's exact name, typed as its class |
| Child element, repeating | `list[Class]` field with the element's exact name |
| Wrapper element (no attributes, one repeating child) | Flattened: a `list[Child]` field named after the wrapper |
| Child element with text content only | Field typed by the element's simple type |
| `use="optional"` or `minOccurs="0"` | `T \| None = None`, or an empty list |
| `fixed` attribute | Class constant, not a constructor argument |
| `xs:decimal` and derived types | `Decimal` |
| `xs:dateTime`, `xs:date`, `xs:time` | `datetime`, `date`, `time`, all naive (no time zone), written in the SAT's format without an offset |
| Integer types | `int` |
| `xs:boolean` | `bool` |
| Every other simple type, including every catalog type | `str` |
| Strict `xs:any` (`Complemento`, `ComplementoConcepto`, `Addenda`) | See 1.4 |

Field metadata carries what the mapper needs: XML kind (attribute, element, text), namespace,
wrapper name and, for decimals, nothing else: a `Decimal` is written exactly as given, so
`Decimal('100.00')` becomes `100.00`.

Element names are kept exactly, including the SAT's lowercase ones (`detallista`,
`obrasarteantiguedades`, `instEducativas`, `certificadodedestruccion`).

### 1.2 CFDI 4.0 (`mictlanix.cfdi.cfdi40`, namespace `http://www.sat.gob.mx/cfd/4`)

Classes, from `cfdv40.xsd`. Names in the second column are fixed by the generator's clash table
because the SAT reuses the element name.

| Node (path under `Comprobante`) | Class |
|---------------------------------|-------|
| `Comprobante` | `Comprobante` |
| `InformacionGlobal` | `InformacionGlobal` |
| `CfdiRelacionados` (repeats; has `TipoRelacion`) | `CfdiRelacionados` |
| `CfdiRelacionados/CfdiRelacionado` | `CfdiRelacionado` |
| `Emisor` | `Emisor` |
| `Receptor` | `Receptor` |
| `Conceptos/Concepto` | `Concepto` (field `Comprobante.Conceptos: list[Concepto]`) |
| `Concepto/Impuestos` | `ConceptoImpuestos` |
| `Concepto/Impuestos/Traslados/Traslado` | `ConceptoTraslado` |
| `Concepto/Impuestos/Retenciones/Retencion` | `ConceptoRetencion` |
| `Concepto/ACuentaTerceros` | `ACuentaTerceros` |
| `Concepto/InformacionAduanera` | `InformacionAduanera` |
| `Concepto/CuentaPredial` | `CuentaPredial` |
| `Concepto/Parte` | `Parte` |
| `Concepto/Parte/InformacionAduanera` | `ParteInformacionAduanera` |
| `Impuestos` | `Impuestos` |
| `Impuestos/Traslados/Traslado` | `Traslado` |
| `Impuestos/Retenciones/Retencion` | `Retencion` |

`Version` is the constant `'4.0'`.

**Library-written fields** (generated as optional although the XSD requires them):

| Field | Written by |
|-------|-----------|
| `Comprobante.SubTotal`, `Comprobante.Total` | `compute` |
| `Comprobante.Descuento`, `Comprobante.Impuestos` (optional in the XSD) | `compute` |
| `Comprobante.Sello`, `Comprobante.NoCertificado`, `Comprobante.Certificado` | `seal` |

### 1.3 Complements

One module per complement and version. `Level` is where the SAT allows the complement.

| Module | Complement | SAT namespace suffix | Root element | Level | Story |
|--------|-----------|----------------------|--------------|-------|-------|
| `pagos20` | Pagos 2.0 | `Pagos20` | `Pagos` | Document | P1 |
| `tfd11` | TimbreFiscalDigital 1.1 | `TimbreFiscalDigital` | `TimbreFiscalDigital` | Document | P1 |
| `nomina12` | Nómina 1.2 | `nomina12` | `Nomina` | Document | P2 |
| `cartaporte31` | Carta Porte 3.1 | `CartaPorte31` | `CartaPorte` | Document | P2 |
| `comercioexterior20` | Comercio Exterior 2.0 | `ComercioExterior20` | `ComercioExterior` | Document | P2 |
| `implocal10` | Impuestos Locales 1.0 | `implocal` | `ImpuestosLocales` | Document | P2 |
| `divisas10` | Divisas 1.0 | `divisas` | `Divisas` | Document | P3 |
| `donat11` | Donatarias 1.1 | `donat` | `Donatarias` | Document | P3 |
| `leyendasfiscales10` | Leyendas Fiscales 1.0 | `leyendasFiscales` | `LeyendasFiscales` | Document | P3 |
| `ine11` | INE 1.1 | `ine` | `INE` | Document | P3 |
| `aerolineas10` | Aerolíneas 1.0 | `aerolineas` | `Aerolineas` | Document | P3 |
| `detallista` | Detallista 1.3.1 | `detallista` | `detallista` | Document | P3 |
| `tpe10` | Turista Pasajero Extranjero 1.0 | `TuristaPasajeroExtranjero` | `TuristaPasajeroExtranjero` | Document | P3 |
| `ecc12` | Estado de Cuenta de Combustibles 1.2 | `EstadoDeCuentaCombustible12` | `EstadoDeCuentaCombustible` | Document | P3 |
| `consumodecombustibles11` | Consumo de Combustibles 1.1 | `ConsumoDeCombustibles11` | `ConsumoDeCombustibles` | Document | P3 |
| `gastoshidrocarburos10` | Gastos de Hidrocarburos 1.0 | `GastosHidrocarburos10` | `GastosHidrocarburos` | Document | P3 |
| `ingresoshidrocarburos10` | Ingresos de Hidrocarburos 1.0 | `IngresosHidrocarburos10` | `IngresosHidrocarburos` | Document | P3 |
| `notariospublicos10` | Notarios Públicos 1.0 | `notariospublicos` | `NotariosPublicos` | Document | P3 |
| `arteantiguedades10` | Obras de Arte y Antigüedades 1.0 | `arteantiguedades` | `obrasarteantiguedades` | Document | P3 |
| `pagoenespecie10` | Pago en Especie 1.0 | `pagoenespecie` | `PagoEnEspecie` | Document | P3 |
| `valesdedespensa10` | Vales de Despensa 1.0 | `valesdedespensa` | `ValesDeDespensa` | Document | P3 |
| `vehiculousado10` | Vehículo Usado 1.0 | `vehiculousado` | `VehiculoUsado` | Document | P3 |
| `renovacionysustitucionvehiculos10` | Renovación y Sustitución de Vehículos 1.0 | `renovacionysustitucionvehiculos` | `renovacionysustitucionvehiculos` | Document | P3 |
| `certificadodestruccion10` | Certificado de Destrucción 1.0 | `certificadodestruccion` | `certificadodedestruccion` | Document | P3 |
| `servicioparcialconstruccion10` | Servicios Parciales de Construcción 1.0 | `servicioparcialconstruccion` | `parcialesconstruccion` | Document | P3 |
| `registrofiscal10` | CFDI Registro Fiscal 1.0 | `registrofiscal` | `CFDIRegistroFiscal` | Document | P3 |
| `pfic10` | PFIC 1.0 | `pfic` | `PFintegranteCoordinado` | Document | P3 |
| `iedu10` | Instituciones Educativas Privadas 1.0 | `iedu` | `instEducativas` | Concept | P3 |
| `ventavehiculos11` | Venta de Vehículos 1.1 | `ventavehiculos` | `VentaVehiculos` | Concept | P3 |
| `hidrocarburospetroliferos10` | Hidrocarburos y Petrolíferos 1.0 | `hidrocarburospetroliferos` | `HidroYPetro` | Concept | P3 |

Namespaces are `http://www.sat.gob.mx/` followed by the suffix. The module name is that
suffix in lowercase without a version, followed by the version digits (`tpe`, `ecc` and `tfd` are
short forms); `detallista` has no version in its namespace or schema. `tfd11` exists so that stamped
documents can be read; the library never creates a stamp.
The XSD for `hidrocarburospetroliferos10` is at `cfd/hidrocarburospetroliferos.xsd`, not beside
its stylesheet (research, Open items).

Not modelled, never emitted: Carta Porte 2.0 and 3.0, Comercio Exterior 1.1, Pagos 1.0, Estado
de Cuenta de Combustibles 1.1, Terceros.

### 1.4 Complement and addenda fields

- A complement's root class inherits from a marker base, `DocumentComplement` or
  `ConceptComplement`, according to its level.
- `Comprobante.Complemento: list[DocumentComplement | RawXml]`
- `Concepto.ComplementoConcepto: list[ConceptComplement | RawXml]`
- `Comprobante.Addenda: list[RawXml]`

The level is therefore enforced by the type checker, and for untyped callers by the `complement-level` validation rule. The mapper finds the class for an element
through a registry keyed by namespace and root element, filled from the generated modules.

## 2. Types that are not generated

| Type | Fields | Notes |
|------|--------|-------|
| `RawXml` | `xml: bytes` | One XML element kept as bytes. Allowed in `Addenda` when emitting. Under `Complemento` or `ComplementoConcepto` it appears only when reading an element the library does not model, and such a document cannot be serialized. |
| `CSD` | `NoCertificado: str`, `valid_from: datetime`, `valid_to: datetime` | Created by `CSD.load(certificate, private_key, password)`. Holds the certificate and the private key privately. `repr` shows only the three public fields. Not a dataclass. `valid_from` and `valid_to` are naive UTC. |
| `Violation` | `node: str`, `attribute: str \| None`, `rule: str`, `message: str` | One broken rule. `node` is an XPath with the SAT's prefixes. `rule` is an XSD constraint name, a SAT validation code, or one of the library rules `complement-document-type`, `complement-level`, `complement-not-modelled`, `xml-invalid-character` and `datetime-not-naive`. `message` is for people; callers branch on `rule`. |
| `QrData` | `url: str`, `UUID: str`, `RfcEmisor: str`, `RfcReceptor: str`, `Total: Decimal`, `SelloUltimos8: str` | The data of the SAT verification QR; `url` is the full verification address. |

Errors (all subclasses of `CfdiError`):

| Error | Raised when | Carries |
|-------|-------------|---------|
| `ValidationError` | `seal` or `to_xml` is given a document that breaks a rule | `violations: list[Violation]` |
| `CsdError` | The certificate or key cannot be read, the password is wrong, or key and certificate do not match | `reason` (an enum: `invalid_certificate`, `invalid_key`, `wrong_password`, `key_mismatch`) |
| `CertificateValidityError` | `Fecha` is outside the certificate's validity period | `fecha`, `valid_from`, `valid_to` |
| `ParseError` | Input is not well-formed XML; or, when reading, a CFDI 4.0 document that cannot be turned into the models (a required attribute is missing, or a value cannot be read as its type); or a `RawXml` whose bytes are not one well-formed element | position, or `node` and `attribute` |
| `NotCfdi40Error` | Input is XML but not a CFDI 4.0 `Comprobante` | the root element and version found |
| `NotStampedError` | A TFD is requested from a document that has none | nothing |

No error carries key material or a password.

## 3. Derived values

`d` is the number of decimals of `Comprobante.Moneda` in the SAT's `c_Moneda` catalog. `r(x, n)`
rounds half up to `n` decimals. Sums are over unrounded values. If `Moneda` is not in the
catalog, or any value makes the arithmetic impossible (a non-finite or unroundable amount),
the fields it feeds stay unset; the XSD check then reports the value. This holds for the
document, Pagos 2.0 and Impuestos Locales alike.

### 3.1 Document (FR-004)

| Field | Value |
|-------|-------|
| `SubTotal` | `r(Σ Concepto.Importe, d)` |
| `Descuento` | `r(Σ Concepto.Descuento, d)` if any concept has a discount, otherwise absent |
| `Impuestos.Traslados` | The concepts' `Traslado` nodes grouped by (`Impuesto`, `TipoFactor`, `TasaOCuota`): `Base = r(Σ Base, d)`, `Importe = r(Σ Importe, d)`. `Exento` groups carry `Base` only. |
| `Impuestos.Retenciones` | The concepts' `Retencion` nodes grouped by `Impuesto`: `Importe = r(Σ Importe, d)` |
| `Impuestos.TotalImpuestosTrasladados` | Sum of the summary `Traslado` nodes' `Importe`; absent if there is none (only `Exento`, or no transferred taxes) |
| `Impuestos.TotalImpuestosRetenidos` | Sum of the summary `Retencion` nodes' `Importe`; absent if there is none |
| `Impuestos` | Absent when no concept carries taxes |
| `Total` | `SubTotal − Descuento + TotalImpuestosTrasladados − TotalImpuestosRetenidos`, plus `TotaldeTraslados − TotaldeRetenciones` of an Impuestos Locales complement when present |

For type P and for documents built by `payment_comprobante`, `SubTotal` and `Total` are `0` and
there is no `Impuestos` node.

### 3.2 Pagos 2.0 (FR-025)

| Field | Value |
|-------|-------|
| `Pago.ImpuestosP` | The `ImpuestosDR` of the payment's related documents, each amount divided by its `EquivalenciaDR`, grouped by (`ImpuestoP`, `TipoFactorP`, `TasaOCuotaP`) for transferred taxes and by `ImpuestoP` for withheld taxes, rounded to the decimals of `MonedaP` |
| `Totales.MontoTotalPagos` | `r(Σ Pago.Monto × Pago.TipoCambioP, 2)` |
| `Totales.TotalTraslados…` and `Totales.TotalRetenciones…` | Each payment's `ImpuestosP` amounts times `TipoCambioP`, summed per tax and rate into the matching `Totales` attribute, rounded to 2 decimals; an attribute is absent when no payment contributes to it |

If a related document's `EquivalenciaDR` is zero or absent, a payment's `TipoCambioP` is absent,
or a payment's `MonedaP` is not in the `c_Moneda` catalog, nothing is derived for the complement: `ImpuestosP` and `Totales` stay unset
and validation reports the missing `Totales`.

The exact attribute-by-attribute table for `Totales` is written from `Pagos20.xsd` and the Pagos
2.0 validation matrix when that task is implemented; the tests for it come first.

## 4. Document life cycle

```text
built ──compute──▶ computed ──validate──▶ valid ──seal(CSD)──▶ sealed XML ──(PAC, out of scope)──▶ stamped XML ──read──▶ models + TFD
```

- A model is immutable; each step returns a new value.
- `seal` runs `compute` and validation itself and refuses a document with violations (FR-010).
- Sealed and stamped documents are XML bytes; they are not altered after signing.

## 5. Vendored SAT data

| Item | Location | Recorded with |
|------|----------|---------------|
| XSDs and XSLTs, unmodified | `src/mictlanix/cfdi/sat/`, mirroring the SAT URL path | URL, SHA-256, SAT publication date, retrieval date in `manifest.json` |
| Catalog columns used by rules (for example decimals per currency) | `src/mictlanix/cfdi/sat/catalogs/` | Source spreadsheet, its publication date |
