# Research: CFDI 4.0 Standard, Current Complements and Document Sealing

**Date**: 2026-11-17 | **Plan**: [plan.md](plan.md)

Findings marked **Verified** were checked on 2026-11-17 against the files served by
`http://www.sat.gob.mx/sitio_internet/` with lxml 6.1.3, cryptography 50.0.2 and mypy 2.4.1 on
Python 3.12. Everything else is a design decision or is marked as not verified.

## R1. XML processing: lxml

- **Decision**: lxml is the single XML engine: parsing, XSD validation (`etree.XMLSchema`) and
  XSLT (`etree.XSLT`).
- **Rationale**: it is the only maintained Python library that does XSD validation and XSLT in
  one package. **Verified**: `cadenaoriginal_4_0.xslt` and `cadenaoriginal_TFD_1_1.xslt` declare
  `version="2.0"` but compile and run under libxslt (XSLT 1.0); a sample income document produced
  the expected pipe-separated original string.
- **Alternatives considered**: `xmlschema` plus `saxonche` (two dependencies, Saxon is a large
  binary, no gain since the SAT's stylesheets use only XSLT 1.0 features); the standard library
  (`xml.etree` has neither XSD nor XSLT).

## R2. SAT artifacts are vendored unmodified and resolved offline

- **Decision**: ship the SAT's XSDs and XSLTs byte-identical under `src/mictlanix/cfdi/sat/`, in a tree
  that mirrors their SAT URL path. A custom lxml resolver maps every
  `http://www.sat.gob.mx/sitio_internet/...` URL to the packaged file, and parsers are created
  with `no_network=True`. A `manifest.json` records, per file: SAT URL, SHA-256, the SAT's
  publication date and the retrieval date.
- **Rationale**: the SAT's files reference each other by absolute URL. **Verified**:
  `cadenaoriginal_4_0.xslt` pulls 33 other stylesheets through `xsl:include`, and the XSDs import
  `catCFDI.xsd`, `tdCFDI.xsd` and per-complement catalog XSDs by URL. A resolver keeps the files
  untouched (principle I: updating them is a deliberate change, visible as a hash change) and
  keeps every operation offline (FR-026). With the resolver, the main stylesheet compiled in
  0.04 s and `cfdv40.xsd` with its catalogs in 0.3 to 0.5 s, with no network access.
- **Publication date**: the SAT server's `Last-Modified` header is used as the publication date
  (**Verified** present, e.g. `cfdv40.xsd` 2024-06-04, `catCFDI.xsd` 2024-12-13,
  `cadenaoriginal_4_0.xslt` 2026-04-17, `Pagos20.xsd` 2023-01-07).
- **Retired stylesheets**: the SAT's own `cadenaoriginal_4_0.xslt` still includes
  `CartaPorte20.xslt`, `CartaPorte30.xslt` and `ComercioExterior11.xslt`. They are vendored
  because the unmodified main stylesheet needs them to compile; their XSDs and models are not
  shipped, so those versions cannot be emitted (FR-023).
- **Size**: `catCFDI.xsd` is 6.0 MB, `catCartaPorte.xsd` 2.5 MB, `catComExt.xsd` 1.0 MB; the rest
  are small. Roughly 10 MB uncompressed in the wheel. Accepted: they are the source of truth.
- **Alternatives considered**: rewriting the includes to relative paths (modifies SAT files);
  downloading at runtime (breaks offline use and reproducibility).

## R3. Validation needs a composite schema

- **Finding (Verified)**: `cfdv40.xsd` declares `Complemento`, `ComplementoConcepto` and `Addenda`
  with a strict `xs:any`. A complement element is rejected ("No matching global element
  declaration available, but demanded by the strict wildcard") unless its XSD is loaded in the
  same schema set.
- **Decision**: validation builds, in memory, a small wrapper schema that imports `cfdv40.xsd`
  plus the XSD of each complement namespace present in the document, and caches the compiled
  schema per set of namespaces for the life of the process.
- **Addenda**: its content is not SAT-defined, so it cannot satisfy a strict wildcard. The
  document is validated without its `Addenda` node, which is also not part of the original
  string.
- **Alternatives considered**: one schema importing every complement XSD (loads 9 MB of catalogs for every
  caller, including those who only issue invoices).

## R4. Typed models: generated dataclasses with exact SAT names, and our own XML mapper

- **Decision** (confirmed with the project owner on 2026-11-17): models are frozen, keyword-only
  dataclasses whose fields and classes carry the SAT's exact names (`Comprobante.SubTotal`,
  `Receptor.UsoCFDI`, class `Emisor`). They are generated from the vendored XSDs by a dev-only
  script, `tools/generate_models.py`, and checked into the package. One generic mapper,
  `mictlanix/cfdi/_xml.py`, converts any model to and from XML using the dataclass field metadata.
- **Rationale**: 31 schemas are too many to hand-write and keep in step with the SAT; generating
  from the vendored XSD makes the SAT the source of the models as well as of validation. Exact
  names match Anexo 20, the XML and the validation errors one to one (FR-029).
- **Naming (Verified)**: a field named like its own class (`Emisor: Emisor`,
  `Impuestos: Impuestos | None = None`) passes `mypy --strict` and resolves correctly at runtime
  with `from __future__ import annotations` on Python 3.12, so no workaround is needed.
- **Generator rules**:
  - Type mapping: `xs:decimal` and types derived from it become `Decimal`; `xs:dateTime` becomes
    `datetime`, `xs:date` becomes `date`, `xs:time` becomes `time`; integer types become `int`;
    `xs:boolean` becomes `bool`; everything else, including every catalog type, becomes `str`.
  - Catalog keys are `str`, validated by the XSD. Generating enums was rejected: **Verified**,
    `catCFDI.xsd` alone yields 151,000 lines of enum members (`c_ClaveProdServ` has about 52,000
    values, `c_CodigoPostal` about 96,000).
  - An element that only wraps a repeated child and has no attributes (`Conceptos`, `Traslados`,
    `Retenciones`) is flattened into a list field (`Conceptos: list[Concepto]`); the mapper writes
    and reads the wrapper. Every other node maps one to one.
  - A class is named after its element. Where the SAT reuses an element name for different
    content in one schema (for example `Impuestos` and `Traslado` at document and concept level),
    the generator takes the class name from an explicit table in the script, built from SAT
    parent names (`ConceptoImpuestos`, `ConceptoTraslado`), and fails if a clash has no entry.
  - Attributes with a `fixed` value (`Version`) are constants, not constructor arguments.
  - Attributes the library writes (see R6 and R7) are generated as optional even though the XSD
    requires them; the list lives in the generator script.
- **Staleness guard**: a test regenerates every model module in memory and fails if it differs
  from the committed file.
- **Alternatives considered**: xsdata 26.10 was prototyped. With its defaults it builds,
  validates and round-trips a CFDI, but it names fields in snake_case (`sub_total`), which changes
  the SAT's names; keeping SAT field names forces either nested classes, which break (the field
  shadows its nested class), or flattened class names such as
  `Comprobante_Conceptos_Concepto_Impuestos_Traslados_Traslado`. It would also be a third runtime
  dependency. Hand-writing all models was rejected for volume and drift.

## R5. Public surface and complement namespaces

- **Decision**: the CFDI 4.0 node classes and all functions are exported by name from `mictlanix.cfdi`.
  Each complement is a module exported from `mictlanix.cfdi` and used as a namespace
  (`mictlanix.cfdi.pagos20.Pagos`, `mictlanix.cfdi.nomina12.Nomina`). Internal modules start with an
  underscore.
- **Rationale**: the SAT reuses element names across complements (`Emisor`, `Receptor`,
  `Domicilio`, `Traslado` exist in several), so a single flat namespace is impossible without
  renaming SAT names. One module per complement and version keeps the names exact and makes a
  version's retirement a module removal.

## R6. Derived values and rounding

- **Decision**: one function, `compute`, returns a copy of the document with the derived values
  filled in; `seal` calls it. A derived field left as `None` is computed; a value supplied by the
  caller is kept and then checked by validation.
- **Scope**: exactly what the spec names. For the document (FR-004): `SubTotal`, `Descuento`,
  `Total` and the document-level `Impuestos` node. For Pagos 2.0 (FR-025): each payment's
  `ImpuestosP` and the `Totales` node. Line amounts (`Concepto.Importe`, tax `Importe`) and the
  internal totals of other complements are supplied by the caller and checked by their XSD.
- **Rounding**: `Decimal` arithmetic, `ROUND_HALF_UP`, to the number of decimals of the
  document's currency (from the SAT's `c_Moneda` catalog); sums are taken over unrounded line
  values and rounded once. Pagos 2.0 totals are in MXN with 2 decimals. The formulas are in
  [data-model.md](data-model.md).
- **Payment documents**: a factory, `payment_comprobante`, builds the fixed shape the standard
  imposes on type P (currency `XXX`, zero amounts, the single fixed concept), so the caller
  supplies only parties, date, place and the `Pagos` complement.
- **Alternatives considered**: separate "input" and "document" model sets (doubles the surface);
  always overwriting caller values (hides caller mistakes instead of reporting them).

## R7. Sealing and the CSD: cryptography

- **Decision**: `cryptography` loads the certificate (`x509.load_der_x509_certificate`) and the
  encrypted PKCS#8 key (`load_der_private_key` with the password) and signs with
  `padding.PKCS1v15()` and `hashes.SHA256()`.
  - `NoCertificado`: the certificate serial number's bytes decoded as ASCII (20 digits).
  - `Certificado`: Base64 of the certificate's DER bytes. `Sello`: Base64 of the signature over
    the UTF-8 original string.
  - Key and certificate match when their public numbers are equal.
  - The issue date (`Fecha`) must lie within the certificate's validity period. `Fecha` is naive
    local time and the certificate's validity is UTC, so the validity is converted to Mexico
    City time (fixed UTC-6 since Mexico abolished daylight saving time in October 2022, so
    exact for every certificate still valid) and kept naive. This matches how mbe stores
    certificate validity (checked against 17 real certificates, mictlanix/mbe-api#106).
    Converting by the exact zone of `LugarExpedicion` would need the `c_CodigoPostal` catalog,
    which this feature does not model, so for other zones the check can differ from the PAC's
    by one or two hours at either end of the period.
- **Rationale**: the de facto standard, audited, and the only dependency needed for X.509 plus
  encrypted PKCS#8.
- **Secrets**: `CSD` keeps the key object private, defines `__repr__` to show only
  `NoCertificado` and the validity dates, and no error includes the password or key bytes
  (FR-027).
- **Known results**: RSA PKCS#1 v1.5 signatures are deterministic. The expected seal for each
  fixture is produced once, independently, with the OpenSSL command line and committed; tests
  compare against it and also verify the seal with the certificate's public key.
- **Verified (2026-11-18, tasks.md T034)**: the SAT's public test CSD for `EKU9003173C9` loads
  with `cryptography` 50.0.2: the encrypted PKCS#8 key opens with the published password, it
  matches the certificate, and the serial's bytes decode to `NoCertificado`
  `30001000000500003416`.
- **Alternatives considered**: `pyOpenSSL` (deprecated for this use); calling the `openssl`
  binary (a system dependency).

## R8. Validation errors

- **Decision**: validation returns a list of `Violation(node, attribute, rule, message)`.
  - XSD violations: `node` is the element's XPath as reported by libxml2
    (`/cfdi:Comprobante/cfdi:Receptor`), `rule` is the XSD constraint (for example
    `cvc-pattern-valid`). **Verified**: lxml reports the path, the constraint type and the
    attribute for each error, and reports all errors, not only the first (FR-009).
  - Anexo 20 rule violations: `rule` is the SAT's validation code (`CFDI40xxx`, or the
    complement's own code series), `node` and `attribute` point at the offending value.
- **Rule scope**: the rules of the Anexo 20 validation matrix that can be decided from the
  document and the vendored catalog data. Complements are validated by their XSD (FR-022); their
  own validation matrices are not implemented in this feature, apart from the Pagos 2.0
  derivations (FR-025). The Anexo 20 rules run whether or not the XSD check found violations.
  Two library rules cover the spec's edge case on complement placement:
  `complement-document-type` rejects a complement on a document type the SAT does not allow for
  it, and `complement-level` rejects a concept-level complement under `Complemento` or a
  document-level one under `ComplementoConcepto` (the XSD's wildcard accepts both, so the XSD
  alone cannot catch it). Rules that need the SAT's
  live registries or the stamping time are out (spec Assumptions). Each rule is one small function
  with its SAT code; the list of implemented codes is kept in the package and tested.
- **Catalog data for rules**: several rules need catalog columns that are not in the XSDs
  (decimals per currency, valid rates per tax, regime and CFDI-use compatibility). These come from
  the SAT's catalog spreadsheet (linked as `catCFDI_V_4_<date>.xls` on the SAT's Anexo 20 page,
  `http://omawww.sat.gob.mx/tramitesyservicios/Paginas/anexo_20.htm`, which also links the
  validation matrix `MatrizDeErrores_CFDI_v40_<date>.xls` and the Anexo 20 standard), extracted by a dev-only script into small data
  files vendored with the spreadsheet's publication date. Only the columns a rule uses are
  extracted.
- **Values that cannot be written**: a text value with a character XML 1.0 does not allow, and a
  `datetime` or `time` carrying a time zone, are reported with the library rules
  `xml-invalid-character` and `datetime-not-naive`, so that `validate` never raises and callers
  never see an untyped error from the XML layer.
- **Unsealed documents**: `Sello`, `NoCertificado` and `Certificado` are required by the XSD but
  written by sealing. When validating a document that has not been sealed, they are filled with
  format-valid placeholders for the XSD check only.

## R9. Reading stamped CFDIs

- **Decision**: `read` parses XML into the same models. Complement elements whose namespace has
  a model become typed objects; any other element under `Complemento`, `ComplementoConcepto` or
  `Addenda` becomes `RawXml`, which keeps the element's bytes. The TFD is a complement model
  generated from `TimbreFiscalDigitalv11.xsd`.
- **Emission guard**: serializing a document that has `RawXml` under `Complemento` or
  `ComplementoConcepto` is refused with the library rule `complement-not-modelled` (`to_xml` and
  `seal` raise `ValidationError`; `validate` returns that one violation), which is how the
  retired complements can be read but never emitted. `RawXml` under `Addenda` is written as is.
- **QR data**: the verification address
  `https://verificacfdi.facturaelectronica.sat.gob.mx/default.aspx` followed, in this order, by
  `?id=` (UUID), `&re=` (issuer RFC), `&rr=` (recipient RFC), `&tt=` (total) and `&fe=` (last
  eight characters of the issuer's seal), values written as they are (the standard's example
  does not escape `/`, `+` or `=` in `fe`).
- **`tt` format (confirmed 2026-11-18, tasks.md T041)**: the Anexo 20 standard
  (`documentos/Anexo20_2022.pdf`, section on the printed representation's QR code) says the total
  takes at most 25 characters (18 integer digits, the point, 6 decimals) and that "non-significant
  zeros must be omitted", and gives the `&tt=` segment a minimum of 7 characters, so the point and
  one decimal always remain. Its example, `tt=0000014300.000000`, still shows the zero-padded
  format of CFDI 3.3 and contradicts the text. The library follows the text: no leading zeros,
  trailing decimal zeros removed down to one decimal. 116.00 gives `tt=116.0`, 116.50 gives
  `tt=116.5`, 0 gives `tt=0.0`, 1234.123456 gives `tt=1234.123456`.

## R10. Dependencies and tooling

- **Runtime**: `lxml` (XML, XSD, XSLT) and `cryptography` (CSD and signing). Nothing else.
- **Dev**: `types-lxml` so that `mypy --strict` can check code that uses lxml. The catalog
  extraction script needs a spreadsheet reader as a dev-only dependency, chosen in that task.
- **Test fixtures**: the SAT's public test CSDs (`Certificados_de_Prueba.zip`, linked on
  `http://omawww.sat.gob.mx/tramitesyservicios/Paginas/certificado_sello_digital.htm`) are `.cer` and `.key` files, which `.gitignore`
  excludes. A negated pattern for `tests/fixtures/csd/` is needed so they can be committed
  (FR-028). Their validity period is fixed, so tests pin `Fecha` to a date inside it and never
  use the current time.

## R11. Import package: `mictlanix.cfdi` in a namespace package

- **Decision** (project owner, 2026-11-17): the library is imported as `mictlanix.cfdi`; PAC
  clients (mictlanix/cfdi#2, #3) will live in `mictlanix.cfdi.pac`. `mictlanix` is a PEP 420
  namespace package: `src/mictlanix/` has no `__init__.py`, and `src/mictlanix/cfdi/` is a
  regular package. The distribution is renamed from `mtx-cfdi` to `mictlanix-cfdi` (project
  owner, 2026-11-17), so `pip install mictlanix-cfdi` matches `import mictlanix.cfdi`.
- **Build (Verified)**: with `[tool.uv.build-backend] module-name = "mictlanix.cfdi"`, uv_build
  0.11.14 builds a wheel containing `mictlanix/cfdi/__init__.py` and `py.typed` and no
  `mictlanix/__init__.py`. The check was run with the old distribution name; the explicit
  `module-name` is still needed with the new one, because the default module for
  `mictlanix-cfdi` would be `mictlanix_cfdi`.
- **Name availability**: not checked. Whether `mictlanix-cfdi` is free on PyPI must be confirmed
  before the first publish.
- **Type checking**: mypy needs `mypy_path = "src"` and `explicit_package_bases = true` to map
  files under a namespace package to their real module names. Verified by the rename task
  (tasks.md T001): `uv run mypy src` is green with them.
- **`py.typed`**: goes in `src/mictlanix/cfdi/`, the regular package, as PEP 561 requires for
  namespace packages.
- **`pac`**: `mictlanix.cfdi.pac` is a future subpackage of this same distribution. Nothing is
  created for it now; the layout only keeps the name free. PAC clients need an HTTP dependency
  that this feature does not, so whether they ship in this distribution or as an optional extra
  is a decision for #2.
- **Rename scope**: `src/mtx_cfdi/` to `src/mictlanix/cfdi/`, `pyproject.toml`, the smoke test,
  the README and `uv.lock`. `__version__` reads the `mictlanix-cfdi` distribution metadata.
- **Constitution**: amended to 1.0.1 on 2026-11-17 to name `mictlanix.cfdi` (plan.md,
  Constitution Check, note 2).
- **Alternatives considered**: keeping `mtx_cfdi` (rejected by the project owner); a regular
  `mictlanix` package with an `__init__.py` (would prevent any other distribution from adding
  `mictlanix.*` packages).

## Open items

- **Hidrocarburos y Petrolíferos 1.0 XSD: resolved.** It is not next to its stylesheet. The
  SAT's complement page (`https://www.sat.gob.mx/portal/public/tramites/complementos-de-factura`,
  section "Complementos concepto") links it at
  `http://www.sat.gob.mx/sitio_internet/cfd/hidrocarburospetroliferos.xsd`, with its catalog at
  `cfd/catalogos/HidrocarburosPetro/catHidroYPetro.xsd` and its stylesheet at
  `cfd/HidrocarburosPetro/hidrocarburospetroliferos.xslt`. **Verified**: the XSD (published
  2026-03-19) has namespace `http://www.sat.gob.mx/hidrocarburospetroliferos`, root
  `HidroYPetro`, `Version` fixed to `1.0`, imports only that catalog, and compiles offline with
  the resolver. All 29 complement XSDs are now located at the stated versions.
- **Where to look**: a complement's XSD is not always beside its XSLT. `tools/fetch_sat.py` takes
  its list of URLs from an explicit table, and that table is filled from the SAT's complement
  page, not derived from stylesheet paths.
- **Anexo 20 rule list**: the SAT codes in scope are listed, from the SAT's own matrix, in
  `contracts/validation-rules.md`, which the first rules task (tasks.md T026) produces.
