---

description: "Task list for CFDI 4.0 standard, current complements and document sealing"
---

# Tasks: CFDI 4.0 Standard, Current Complements and Document Sealing

**Input**: Design documents from `/specs/001-cfdi40-complements-sealing/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/public-api.md, quickstart.md

**Tests**: mandatory. The constitution (principle II) requires tests to be written before the
code, so every task that adds behavior is preceded by, or begins with, a test that must fail
first. Three guards (no secrets, no network, public API) are written before the code they guard and
pass from the start.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- Exact file paths are in the descriptions

## Conventions for every task

- Package root is `src/mictlanix/cfdi/`; `src/mictlanix/` must never get an `__init__.py`.
- A test-writing task (marked "failing") is done when its new tests fail for the expected reason
  and everything else still passes. Every other task is done when `uv run pytest -q`,
  `uv run ruff check`, `uv run ruff format --check` and `uv run mypy src` all pass.
- SAT names keep their exact spelling. Everything else (functions, comments, docs) is English.
- No test uses the network or the current time; `Fecha` is pinned inside the test CSD's validity.
- Public names are added to `src/mictlanix/cfdi/__init__.py` exactly as listed in
  `contracts/public-api.md`; nothing else is exported.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: the renamed package, its dependencies and repository rules

- [X] T001 Rename the package and distribution (research.md R11): move `src/mtx_cfdi/` to `src/mictlanix/cfdi/` with `git mv` (keep `py.typed`; create no `src/mictlanix/__init__.py`); in `pyproject.toml` set `name = "mictlanix-cfdi"`, add `[tool.uv.build-backend] module-name = "mictlanix.cfdi"`, and add `mypy_path = "src"` and `explicit_package_bases = true` under `[tool.mypy]`; make `src/mictlanix/cfdi/__init__.py` read `version('mictlanix-cfdi')`; update `tests/test_smoke.py` to `import mictlanix.cfdi`; update the install and import lines in `README.md`; run `uv lock`. Verify the four gates pass and that `uv build` produces a wheel containing `mictlanix/cfdi/__init__.py` and `mictlanix/cfdi/py.typed` and no `mictlanix/__init__.py`
- [X] T002 Add dependencies with uv: `uv add lxml cryptography` and `uv add --dev types-lxml`, which update `pyproject.toml` and `uv.lock`
- [X] T003 [P] In `.gitignore`, after the `*.cer`, `*.key`, `*.pfx`, `*.pem` block, add negated patterns `!tests/fixtures/csd/*.cer` and `!tests/fixtures/csd/*.key` so the SAT's public test CSDs can be committed; verify with `git check-ignore` that a `.cer` elsewhere is still ignored
- [X] T004 [P] Write `tests/test_no_secrets.py`: the repository tree (tracked and untracked, ignoring `.venv` and `.git`) contains no `.cer`, `.key`, `.pfx` or `.pem` file outside `tests/fixtures/csd/`, and no file under `src/` imports `logging` or calls `print` (SC-006). It passes now and guards every later task

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: SAT artifacts, models, XML mapping, XSD validation and the original string, which
every story needs

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

### SAT artifacts

- [X] T005 Write `tests/conftest.py` with an autouse fixture that makes any outbound connection raise (patch `socket.socket.connect` and `socket.socket.connect_ex`), so the whole suite always runs with the network disabled, and `tests/test_offline.py`, which asserts that opening a connection inside a test raises (SC-003, FR-026)
- [X] T006 Write `tests/test_sat_artifacts.py` (failing): every file listed in `src/mictlanix/cfdi/sat/manifest.json` exists, matches its `sha256`, and has a `url`, a `published` date and a `retrieved` date; every file under `src/mictlanix/cfdi/sat/sitio_internet/` is listed in the manifest; `cadenaoriginal_4_0.xslt` and `cadenaoriginal_TFD_1_1.xslt` compile and `cfdv40.xsd` compiles through the resolver with a parser created with `no_network=True`; resolving a SAT URL that is not vendored raises instead of fetching
- [X] T007 Write `tools/fetch_sat.py`: an explicit table of SAT URLs (not derived from stylesheet paths, research.md Open items); for each, download to `src/mictlanix/cfdi/sat/sitio_internet/<path after sitio_internet/>` byte-identical, and write `src/mictlanix/cfdi/sat/manifest.json` with `url`, `sha256`, `published` (the `Last-Modified` header as an ISO date) and `retrieved`. The table for this phase: `cfd/4/cfdv40.xsd`, `cfd/catalogos/catCFDI.xsd`, `cfd/tipoDatos/tdCFDI/tdCFDI.xsd`, `cfd/4/cadenaoriginal_4_0/cadenaoriginal_4_0.xslt`, every stylesheet that file includes with `xsl:include` (33 files, including `cfd/2/cadenaoriginal_2_0/utilerias.xslt` and the retired `CartaPorte20.xslt`, `CartaPorte30.xslt`, `ComercioExterior11.xslt`), `cfd/TimbreFiscalDigital/TimbreFiscalDigitalv11.xsd` and `cfd/TimbreFiscalDigital/cadenaoriginal_TFD_1_1.xslt`
- [X] T008 Run `tools/fetch_sat.py` to add the vendored files and `src/mictlanix/cfdi/sat/manifest.json` to the package; confirm `uv build` includes them in the wheel
- [X] T009 Implement `src/mictlanix/cfdi/_sat.py`: an lxml resolver mapping `http://www.sat.gob.mx/sitio_internet/...` to the packaged file (via `importlib.resources`), raising for any other or missing URL; parsers created with `no_network=True`; cached loaders for the two original-string stylesheets and for a compiled schema; make T006 pass

### Errors, mapper and models

- [X] T010 [P] Implement `src/mictlanix/cfdi/_errors.py` with `CfdiError` and its subclasses exactly as in data-model.md section 2, plus the frozen dataclass `Violation(node: str, attribute: str | None, rule: str, message: str)` that `ValidationError` carries (`ValidationError` with `violations: list[Violation]`, `CsdError` with a `reason` enum of `invalid_certificate`, `invalid_key`, `wrong_password`, `key_mismatch`, `CertificateValidityError` with `fecha`, `valid_from`, `valid_to`, `ParseError` with `node` and `attribute` when the problem is a value and not the XML itself, `NotCfdi40Error`, `NotStampedError`), with tests in `tests/test_errors.py` written first; export the seven errors and `Violation` from `src/mictlanix/cfdi/__init__.py`
- [X] T011 Write `tests/test_xml.py` (failing) for the generic mapper, using small hand-written dataclasses in the test: attributes, single and repeating child elements, a flattened wrapper element, text-only child elements, a text value with a character XML 1.0 does not allow (a NUL) and a `datetime` carrying a time zone are each rejected by the mapper with an error naming the field, optional fields omitted when `None`, `Decimal` written exactly as given (`Decimal('100.00')` gives `100.00`), `datetime`, `date`, `time`, `int`, `bool`, namespace prefixes, field order equals XSD order, and round trip (parse of serialize equals the original)
- [X] T012 Implement `src/mictlanix/cfdi/_xml.py`: `RawXml(xml: bytes)`, marker bases `DocumentComplement` and `ConceptComplement`, a registry keyed by (namespace, root element) filled by complement modules, and the mapper driven by dataclass field metadata (XML kind: attribute, element, text; namespace; wrapper name); export `RawXml`, `DocumentComplement` and `ConceptComplement`; make T011 pass
- [X] T013 Write `tests/test_generated_models.py` (failing): for every model module the generator knows, regenerating it in memory from the vendored XSD equals the committed file byte for byte
- [X] T014 Write `tools/generate_models.py` following data-model.md 1.1: frozen keyword-only dataclasses; exact SAT field and class names; type mapping (`xs:decimal` and derived to `Decimal`, `xs:dateTime`/`xs:date`/`xs:time` to `datetime`/`date`/`time`, integers to `int`, `xs:boolean` to `bool`, everything else including every catalog type to `str`); wrapper elements (no attributes, one repeating child) flattened to a list field; `fixed` attributes as class constants; an explicit clash table per schema, failing with a clear message when a reused element name has no entry; a per-schema list of library-written attributes generated as optional; strict `xs:any` fields typed per data-model.md 1.4; output formatted so it passes `ruff format --check`
- [X] T015 Write `tests/test_public_api.py`: every name in `mictlanix.cfdi.__all__` appears in the Exports block of `specs/001-cfdi40-complements-sealing/contracts/public-api.md`, `__all__` has no duplicates, and every name in `__all__` is importable; it passes with the current `__all__` and fails as soon as an unlisted name is exported
- [X] T016 Generate `src/mictlanix/cfdi/cfdi40.py` from `cfdv40.xsd` with the class names of data-model.md 1.2 (`ConceptoImpuestos`, `ConceptoTraslado`, `ConceptoRetencion`, `ParteInformacionAduanera`; `Impuestos`, `Traslado`, `Retencion` for the document level), `Version` constant `'4.0'`, and `SubTotal`, `Total`, `Sello`, `NoCertificado`, `Certificado` optional; export the classes from `src/mictlanix/cfdi/__init__.py`; make T013 pass and confirm `mypy --strict` accepts fields named like their class

### XML, validation and original string

- [X] T017 Write `tests/test_to_xml.py` (failing): `to_xml` of the quickstart scenario 1 invoice (with totals set by hand) gives UTF-8 XML with the `cfdi` prefix and `xsi:schemaLocation`; `read`-independent check by parsing with lxml; a document holding `RawXml` under `Complemento` or `ComplementoConcepto` raises `ValidationError` whose single violation has rule `complement-not-modelled` and the `Complemento` (or `ComplementoConcepto`) node; a `Descripcion` holding a NUL character raises `ValidationError` with rule `xml-invalid-character`, and a time-zone-aware `Fecha` raises it with rule `datetime-not-naive`, each naming the node and attribute; `RawXml` under `Addenda` is written as is, and `RawXml` whose bytes are not one well-formed element raises `ParseError`
- [X] T018 Implement `to_xml` in `src/mictlanix/cfdi/_xml.py` and export it; make T017 pass
- [X] T019 Write `tests/test_validate.py` (failing) for XSD validation, using documents whose totals are set by hand (`compute` does not exist yet): a valid document returns `[]`; `TipoDeComprobante='Z'` gives a violation with `node='/cfdi:Comprobante'`, `attribute='TipoDeComprobante'`, `rule='cvc-enumeration-valid'`; recipient `Rfc='x'` gives `node='/cfdi:Comprobante/cfdi:Receptor'`, `attribute='Rfc'`, `rule='cvc-pattern-valid'`; both violations are returned together (FR-009); an unsealed document is not reported for missing `Sello`, `NoCertificado` or `Certificado`; a document with an `Addenda` validates; a `Descripcion` holding a NUL character and a time-zone-aware `Fecha` are returned as `xml-invalid-character` and `datetime-not-naive` violations, together with any other violation in the document, and nothing is raised; a document holding `RawXml` under `Complemento` returns the `complement-not-modelled` violation and is not checked further
- [X] T020 Implement `src/mictlanix/cfdi/_validate.py`, returning the `Violation` objects defined in `_errors.py`: a composite schema built in memory that imports `cfdv40.xsd` plus the XSD of each complement namespace in the document, cached per set of namespaces (research.md R3); validation without the `Addenda` node; format-valid placeholders for the three seal attributes when absent (research.md R8); libxml2 error type mapped to the XSD constraint name; export `validate`; make T019 pass
- [X] T021 Write `tests/test_original_string.py` (failing): create `tests/fixtures/expected/ingreso.xml` (the quickstart scenario 1 invoice written by hand as XML, with its totals and placeholder seal attributes; its `Fecha` is provisional until the test CSD's validity is known) and `tests/fixtures/expected/ingreso.cadena.txt` (its original string written out by hand: `||`, then each attribute value in the order Anexo 20 defines, separated by `|`, ending in `||`; it starts with `||4.0|`); `original_string` of the XML equals the text file; malformed input raises `ParseError`; XML that is not a CFDI 4.0 `Comprobante` raises `NotCfdi40Error`
- [X] T022 Implement `original_string` in `src/mictlanix/cfdi/_seal.py` using the cached `cadenaoriginal_4_0.xslt` and export it; make T021 pass

**Checkpoint**: a CFDI 4.0 document can be modelled, serialized, validated against the SAT's XSDs
and turned into its original string, all offline

---

## Phase 3: User Story 1 - Invoices, credit notes and payment receipts, sealed and read back (Priority: P1) 🎯 MVP

**Goal**: build income, expense and payment documents (Pagos 2.0) from business data, with
derived totals, validation, sealing with the CSD, and reading of stamped CFDIs with their TFD

**Independent Test**: quickstart.md scenarios 1 to 5 pass with the SAT's public test CSD and no
network

### Derived values (FR-004)

- [X] T023 [US1] First extend `tests/test_sat_artifacts.py` (failing) to require `src/mictlanix/cfdi/sat/catalogs/c_Moneda.json` in the manifest with MXN and USD at 2 decimals and JPY and XXX at 0; then write `tools/extract_catalogs.py` and vendor `src/mictlanix/cfdi/sat/catalogs/c_Moneda.json` (currency key to number of decimals) from the SAT's catalog spreadsheet, the file linked as `documentos/catCFDI_V_4_<date>.xls` on `http://omawww.sat.gob.mx/tramitesyservicios/Paginas/anexo_20.htm` (on 2026-11-17 it was `catCFDI_V_4_20261106.xls`), recording the spreadsheet's URL and publication date in `manifest.json`; add the spreadsheet reader as a dev-only dependency
- [X] T024 [US1] Write `tests/test_compute.py` (failing) for data-model.md 3.1: `SubTotal = r(Σ Concepto.Importe, d)`; `Descuento = r(Σ Concepto.Descuento, d)` only when a concept has a discount; the document's `Impuestos.Traslados` grouped by (`Impuesto`, `TipoFactor`, `TasaOCuota`) with `Base` and `Importe` rounded once after summing; `Exento` groups carry `Base` only and add nothing to `TotalImpuestosTrasladados`; the document's `Impuestos.Retenciones` grouped by `Impuesto`; `Impuestos` absent when no concept carries taxes; `Total = SubTotal − Descuento + TotalImpuestosTrasladados − TotalImpuestosRetenidos`; half-up rounding on a case where per-line rounding and sum-then-round differ; a 0-decimal currency; a value the caller set is kept; the input is not mutated; a `Moneda` that is not in `c_Moneda.json` leaves the derived fields unset and raises nothing (the XSD then reports `Moneda`); a non-finite amount leaves the fields it feeds unset and raises nothing; and, in `tests/test_validate.py`, `validate` of the valid document with no totals set returns `[]` (it fails until `validate` calls `compute`)
- [X] T025 [US1] Implement `compute` for the document in `src/mictlanix/cfdi/_compute.py` (`Decimal`, `ROUND_HALF_UP`, decimals from `c_Moneda.json`) and export it; make `validate` call it first; make T024 pass

### Anexo 20 rules (FR-007, FR-008)

- [X] T026 [US1] Obtain the SAT's CFDI 4.0 validation matrix, the file linked as `documentos/MatrizDeErrores_CFDI_v40_<date>.xls` on `http://omawww.sat.gob.mx/tramitesyservicios/Paginas/anexo_20.htm` (on 2026-11-17 it was `MatrizDeErrores_CFDI_v40_20260325.xls`); if it cannot be obtained, stop and ask. Record its URL and date at the top of, and write, `specs/001-cfdi40-complements-sealing/contracts/validation-rules.md`: one row per rule with its SAT code, the node and attribute it concerns, and a status of `implemented in US1`, `implemented in US2`, or `out of scope` with the reason (needs the SAT's live registries, needs the stamping time, or concerns a node this library does not emit). US1 covers the rules for income, expense and payment documents: `Comprobante` attributes, `InformacionGlobal`, `CfdiRelacionados`, `Emisor`, `Receptor`, `Concepto` and its taxes, `ACuentaTerceros`, and the document `Impuestos` node. The rules behind the spec's edge cases must be in the US1 set: `InformacionGlobal` required for an invoice to the general public, `ACuentaTerceros`, `ObjetoImp` against the presence of tax nodes, `TipoCambio` for a currency other than MXN and XXX, and the fixed values of type P; if the matrix lacks any of them, stop and ask
- [X] T027 [US1] Extend `tools/extract_catalogs.py` to vendor, under `src/mictlanix/cfdi/sat/catalogs/`, only the catalog columns the US1 rules in `validation-rules.md` need (for example valid rates per tax and factor, and the regime and CFDI-use compatibility columns), each recorded in `manifest.json`, after first extending `tests/test_sat_artifacts.py` (failing) to require each new catalog file in the manifest
- [X] T028 [US1] Write `tests/test_rules.py` (failing): for every rule marked `implemented in US1` in `validation-rules.md`, one document that breaks it yields a `Violation` whose `rule` is the SAT code and whose `node` and `attribute` point at the offending value, and the valid quickstart invoice yields none; a document with both an XSD violation and a rule violation reports both (FR-009); a test asserts the set of implemented codes equals the set marked `implemented in US1` in `validation-rules.md`; one test for each library rule, using small hand-written marker subclasses registered for the test: `complement-document-type` (a complement whose table entry allows only type P, on a type I document, is a violation) and `complement-level` (a `ConceptComplement` under `Complemento`, or a `DocumentComplement` under `ComplementoConcepto`, is a violation)
- [X] T029 [US1] Implement `src/mictlanix/cfdi/_rules.py`: one small function per SAT code over the computed `Comprobante`, a registry of them, the library rules `complement-document-type` (driven by a table of complement root to allowed `TipoDeComprobante`; an entry is taken from the complement's standard, the "Estándar" document linked on `https://www.sat.gob.mx/portal/public/tramites/complementos-de-factura`, and a complement whose standard does not restrict the document type has no entry) and `complement-level` (driven by the `DocumentComplement` and `ConceptComplement` markers), and a call from `validate` after the XSD check whether or not that check found violations (a rule that needs a value the XSD has already rejected reports nothing); make T028 pass

### Pagos 2.0 and payment documents (FR-025)

- [X] T030 [US1] Add `cfd/Pagos/Pagos20.xsd` and `cfd/catalogos/Pagos/catPagos.xsd` to the table in `tools/fetch_sat.py`, vendor them, and generate `src/mictlanix/cfdi/pagos20.py` (root `Pagos`, a `DocumentComplement`, registered for namespace `http://www.sat.gob.mx/Pagos20`; `Totales` and the derived `ImpuestosP` generated as optional); export the module as `pagos20`; add `Pagos` (allowed only on type P) to the `complement-document-type` table in `src/mictlanix/cfdi/_rules.py`, with a test in `tests/test_rules.py`, written first, that a `pagos20.Pagos` on a type I document is a violation
- [X] T031 [US1] Write the exact attribute-by-attribute derivation table for `Pagos.Totales` and `Pago.ImpuestosP` into data-model.md section 3.2 from `Pagos20.xsd` and the Pagos 2.0 validation matrix (the "Matriz de errores" linked in the Recepción de pagos section, under "Complementos", of `https://www.sat.gob.mx/portal/public/tramites/complementos-de-factura`; if it cannot be obtained, stop and ask), then write `tests/test_compute_pagos.py` (failing) for it: `ImpuestosP` from the related documents' `ImpuestosDR` divided by `EquivalenciaDR`, grouped by (`ImpuestoP`, `TipoFactorP`, `TasaOCuotaP`) and by `ImpuestoP` for withholdings; `MontoTotalPagos = r(Σ Monto × TipoCambioP, 2)`; each `Totales` attribute, absent when nothing contributes; a payment in USD settling an MXN document; a related document whose `EquivalenciaDR` is zero or absent, a payment whose `TipoCambioP` is absent, and a payment whose `MonedaP` is not in `c_Moneda.json`, and a non-finite `Monto`, each leave `ImpuestosP` and `Totales` unset and raise nothing (validation then reports the missing `Totales`)
- [X] T032 [US1] Implement the Pagos 2.0 derivation in `src/mictlanix/cfdi/_compute.py`; make T031 pass
- [X] T033 [US1] Write `tests/test_payment_comprobante.py` (failing) then implement `payment_comprobante` in `src/mictlanix/cfdi/_compute.py` with the signature in contracts/public-api.md: `TipoDeComprobante='P'`, `Moneda='XXX'`, `SubTotal` and `Total` `0`, `Exportacion='01'`, no `FormaPago`, `MetodoPago` or `Impuestos`, the single fixed concept the standard requires for type P, and `Pagos` as its complement; export it

### CSD and sealing (FR-011 to FR-016, FR-027, FR-028)

- [X] T034 [US1] Download the SAT's public test CSDs, the file linked as `documentos/Certificados_de_Prueba.zip` on `http://omawww.sat.gob.mx/tramitesyservicios/Paginas/certificado_sello_digital.htm`, and add one issuer's CSD `.cer` and `.key` (a CSD, not a FIEL) to `tests/fixtures/csd/`, with `tests/fixtures/csd/README.md` recording the source URL, the retrieval date, the certificate's validity period and that the password is the one the SAT publishes with them. Check that the `Fecha` used in quickstart.md scenario 1 and in `tests/fixtures/expected/ingreso.xml` lies inside the certificate's validity; if not, change it in both and in `ingreso.cadena.txt`. Then confirm the open risk in research.md R7: the encrypted key loads with `cryptography`; if it does not, stop and revise R7 before continuing
- [X] T035 [US1] Write `tests/test_csd.py` (failing): `CSD.load` gives `NoCertificado` (20 digits, the serial's bytes as ASCII), `valid_from` and `valid_to`; wrong password raises `CsdError` with `reason == wrong_password`; a valid encrypted PKCS#8 key that does not belong to the certificate (an RSA key generated in the test with `cryptography`) raises `key_mismatch`; garbage certificate bytes raise `invalid_certificate`; garbage key bytes and an unencrypted key each raise `invalid_key`; a certificate whose serial number is not 20 ASCII digits raises `invalid_certificate`; `valid_from` and `valid_to` are naive UTC datetimes; `repr(csd)` shows only `NoCertificado` and the validity dates; for every error, the password and the key bytes are absent from `str(error)` and `repr(error)`
- [X] T036 [US1] Implement `src/mictlanix/cfdi/_csd.py` (`x509.load_der_x509_certificate`, `load_der_private_key`, public-number comparison, password not stored) and export `CSD`; make T035 pass
- [X] T037 [US1] Create the known results: for the quickstart scenario 1 invoice (its original string differs from `ingreso.cadena.txt` only in `NoCertificado`), a credit note and a payment document built with `payment_comprobante`, store the expected original string and the expected seal under `tests/fixtures/expected/`, each original string written out by hand in Anexo 20's order as in the original-string task (never taken from the library's output), and the seal produced independently with the OpenSSL command line (`openssl dgst -sha256 -sign`) from the original string and the test key; record the exact commands in `tests/fixtures/expected/README.md`
- [X] T038 [US1] Write `tests/test_seal.py` (failing): `seal` returns XML valid against the SAT's XSDs with `Sello`, `NoCertificado` and `Certificado` set; the seal equals the committed known result and verifies with the certificate's public key against `original_string(sealed)`; sealing twice gives identical bytes; an invalid document raises `ValidationError` carrying all violations and nothing is signed; no error raised by `seal` contains the password or key bytes in `str` or `repr`; `Fecha` outside the certificate's validity raises `CertificateValidityError` (naive `Fecha` compared with the naive UTC validity, no time-zone conversion); a time-zone-aware `Fecha` raises `ValidationError` with rule `datetime-not-naive`; a malformed `RawXml` under `Addenda` raises `ParseError`; derived totals are present although the caller supplied none (SC-004)
- [X] T039 [US1] Implement `seal` in `src/mictlanix/cfdi/_seal.py` (compute, set `NoCertificado` and `Certificado`, validate, validity check, original string, `PKCS1v15` with `SHA256`, write `Sello`) and export it; make T038 pass

### Reading stamped CFDIs (FR-017 to FR-021)

- [X] T040 [US1] Create `tests/fixtures/stamped/ingreso_timbrado.xml`: the sealed quickstart invoice with a `tfd:TimbreFiscalDigital` added by hand with made-up but format-valid values (reading does not verify seals, so no real stamp is needed and no real data is committed), plus `tests/fixtures/stamped/cartaporte30.xml`, a stamped document (with its own hand-written TFD) carrying a Carta Porte 3.0 element, `tests/fixtures/stamped/ingreso_timbrado.tfd.cadena.txt` with that TFD's original string written out by hand in the order of `cadenaoriginal_TFD_1_1.xslt`, and `tests/fixtures/stamped/README.md` saying all of them are synthetic
- [X] T041 [US1] Confirm the exact format of the verification QR's `tt` (total) parameter in the Anexo 20 standard, the file linked as `documentos/Anexo20_2022.pdf` on `http://omawww.sat.gob.mx/tramitesyservicios/Paginas/anexo_20.htm`, and record it in `specs/001-cfdi40-complements-sealing/research.md` R9, replacing the "Not verified here" note; the `qr_data` test in the next task uses exactly that format. If the text cannot be obtained, stop and ask
- [X] T042 [US1] Write `tests/test_read.py` (failing): `read` returns models equal to the document that was sealed (round trip); `timbre` gives the fixture's `UUID`, `FechaTimbrado`, `SelloSAT`, `NoCertificadoSAT`, `RfcProvCertif`; `tfd_original_string` equals `tests/fixtures/stamped/ingreso_timbrado.tfd.cadena.txt`; `qr_data` gives the verification address with UUID, both RFCs, the total in the format recorded in research.md R9 and the last eight characters of the issuer's seal; `timbre` on an unstamped document raises `NotStampedError`; `qr_data` on a document without a TFD, without `Sello` or without `Total` raises `NotStampedError`; malformed XML raises `ParseError`; a well-formed CFDI 4.0 with a required attribute missing, and one with `SubTotal="abc"`, each raise `ParseError` naming the node and attribute; a minimal CFDI 3.3 document written inline in the test raises `NotCfdi40Error`; the Carta Porte 3.0 fixture reads with that complement as `RawXml`, `timbre` still returns its TFD, and `to_xml` and `seal` refuse it with rule `complement-not-modelled`
- [X] T043 [US1] Generate `src/mictlanix/cfdi/tfd11.py` from the vendored `TimbreFiscalDigitalv11.xsd` (root `TimbreFiscalDigital`, a `DocumentComplement`) and export the module as `tfd11`
- [X] T044 [US1] Implement `src/mictlanix/cfdi/_read.py` (`read`, `timbre`, `tfd_original_string`, `qr_data`, `QrData`) and export them; make T042 pass

### Story acceptance

- [X] T045 [US1] Write `tests/complements/conftest.py` with a fixture for the test CSD and a shared helper `assert_builds_validates_seals(comprobante, csd)` that asserts `validate` returns no violations, seals, checks the sealed XML against the SAT's XSDs (including the XSD of each complement it carries), verifies the seal with the certificate's public key against the original string, and returns the original string, so each document or complement test only supplies its document and the values it expects in the original string
- [X] T046 [US1] Write `tests/complements/test_documents_p1.py`: using the shared helper, one build, validate, seal test each for an income document, an expense document related to an earlier UUID with `TipoRelacion='01'`, and a payment document with Pagos 2.0; each checks validity against the SAT's XSDs, the original string against the committed expectation, and that the Pagos values appear in the original string; plus a global invoice with `InformacionGlobal`; a concept with `ACuentaTerceros`; a concept with `InformacionAduanera`, `CuentaPredial` and a `Parte`; and an income document in USD with `TipoCambio`

**Checkpoint**: User Story 1 is complete: invoices, credit notes and payment receipts can be
sealed and stamped CFDIs read. This is the MVP

---

## Phase 4: User Story 2 - Payroll, transport, foreign trade, local taxes and transfer documents (Priority: P2)

**Goal**: Nómina 1.2, Carta Porte 3.1, Comercio Exterior 2.0, Impuestos Locales 1.0 and transfer
documents, built, validated and sealed like the P1 documents

**Independent Test**: quickstart.md scenario 6 passes for document types N and T and for the four
P2 complements

Every test in this phase and the next uses the shared helper in `tests/complements/conftest.py`.
Where a complement's standard restricts the document type, its test also asserts that the
complement on a disallowed type is reported with rule `complement-document-type`. The generation
tasks add a table entry only when such a test demands it.

- [X] T047 [US2] Add to the table in `tools/fetch_sat.py` and vendor: `cfd/nomina/nomina12.xsd` with `cfd/catalogos/Nomina/catNomina.xsd`; `cfd/CartaPorte/CartaPorte31.xsd` with `cfd/catalogos/CartaPorte/catCartaPorte.xsd` and `cfd/catalogos/ComExt/catComExt.xsd`; `cfd/ComercioExterior20/ComercioExterior20.xsd`; `cfd/implocal/implocal.xsd`
- [X] T048 [P] [US2] Write `tests/complements/test_nomina12.py` (failing): build a type N document with a `nomina12.Nomina` complement (percepciones, deducciones, one employee), validate, seal, and check validity against `nomina12.xsd` and that the complement's values are in the original string; invalid complement data yields a violation naming the complement node
- [X] T049 [P] [US2] Write `tests/complements/test_cartaporte31.py` (failing): a type T document with `cartaporte31.CartaPorte` (one origin, one destination, one merchandise, one autotransporte with a figura), and a type I document with the same complement; validate, seal, XSD and original-string checks
- [X] T050 [P] [US2] Write `tests/complements/test_comercioexterior20.py` (failing): a type I export document (`Exportacion='02'`) with `comercioexterior20.ComercioExterior`; validate, seal, XSD and original-string checks
- [X] T051 [P] [US2] Write `tests/complements/test_implocal10.py` (failing): a type I document with `implocal10.ImpuestosLocales` carrying one `TrasladosLocales` and one `RetencionesLocales`; validate, seal, XSD and original-string checks; `Total` includes `TotaldeTraslados − TotaldeRetenciones`
- [X] T052 [P] [US2] Write `tests/complements/test_traslado.py` (failing): a type T document without complements (`Moneda='XXX'`, concepts with zero amounts and `ObjetoImp='01'`) builds, validates and seals, and its computed `SubTotal` and `Total` are `0` with no `Impuestos` node
- [X] T053 [US2] Generate `src/mictlanix/cfdi/nomina12.py`, `cartaporte31.py`, `comercioexterior20.py` and `implocal10.py` (roots `Nomina`, `CartaPorte`, `ComercioExterior`, `ImpuestosLocales`; all `DocumentComplement`; clash-table entries as the generator demands, built from SAT parent names), register and export them, and add to the `complement-document-type` table in `src/mictlanix/cfdi/_rules.py` exactly the entries the tests above demand
- [X] T054 [US2] Extend `compute` in `src/mictlanix/cfdi/_compute.py` so `Total` adds `TotaldeTraslados − TotaldeRetenciones` of an Impuestos Locales complement (data-model.md 3.1), with the tests added to `tests/test_compute.py` first, including a non-finite local tax amount that leaves `Total` unset and raises nothing
- [X] T055 [US2] For the rules marked `implemented in US2` in `contracts/validation-rules.md` (those specific to type N and type T documents), add their failing tests to `tests/test_rules.py`, widen its set-equality assertion to the codes marked `implemented in US1` or `implemented in US2`, then implement them in `src/mictlanix/cfdi/_rules.py`
- [X] T056 [US2] Make T048 to T052 pass and confirm the P1 tests still pass

**Checkpoint**: User Stories 1 and 2 both work independently

---

## Phase 5: User Story 3 - The remaining complements (Priority: P3)

**Goal**: the other 24 complements the SAT accepts today, 21 at document level and 3 at concept
level, each built, validated and sealed

**Independent Test**: quickstart.md scenario 6 passes for all 29 complements and scenario 7
confirms no retired version can be emitted

- [X] T057 [US3] Add to the table in `tools/fetch_sat.py` and vendor the XSD of each remaining complement, with the catalog XSDs they import (`cfd/catalogos/Combustible/catCombustible.xsd`, `cfd/catalogos/hidrocarburos/catHidrocarburos.xsd`, `cfd/catalogos/HidrocarburosPetro/catHidroYPetro.xsd`): `cfd/divisas/divisas.xsd`, `cfd/donat/donat11.xsd`, `cfd/leyendasFiscales/leyendasFisc.xsd`, `cfd/ine/ine11.xsd`, `cfd/aerolineas/aerolineas.xsd`, `cfd/detallista/detallista.xsd`, `cfd/TuristaPasajeroExtranjero/TuristaPasajeroExtranjero.xsd`, `cfd/EstadoDeCuentaCombustible/ecc12.xsd`, `cfd/consumodecombustibles/consumodeCombustibles11.xsd`, `cfd/GastosHidrocarburos10/GastosHidrocarburos10.xsd`, `cfd/IngresosHidrocarburos10/IngresosHidrocarburos.xsd`, `cfd/notariospublicos/notariospublicos.xsd`, `cfd/arteantiguedades/obrasarteantiguedades.xsd`, `cfd/pagoenespecie/pagoenespecie.xsd`, `cfd/valesdedespensa/valesdedespensa.xsd`, `cfd/vehiculousado/vehiculousado.xsd`, `cfd/renovacionysustitucionvehiculos/renovacionysustitucionvehiculos.xsd`, `cfd/certificadodestruccion/certificadodedestruccion.xsd`, `cfd/servicioparcialconstruccion/servicioparcialconstruccion.xsd`, `cfd/cfdiregistrofiscal/cfdiregistrofiscal.xsd`, `cfd/pfic/pfic.xsd`, `cfd/iedu/iedu.xsd`, `cfd/ventavehiculos/ventavehiculos11.xsd`, and `cfd/hidrocarburospetroliferos.xsd` (this one is not beside its stylesheet)
- [X] T058 [P] [US3] Write `tests/complements/test_divisas10.py` (failing) for `divisas10.Divisas` (document level, root `Divisas`)
- [X] T059 [P] [US3] Write `tests/complements/test_donat11.py` (failing) for `donat11.Donatarias` (document level)
- [X] T060 [P] [US3] Write `tests/complements/test_leyendasfiscales10.py` (failing) for `leyendasfiscales10.LeyendasFiscales` (document level)
- [X] T061 [P] [US3] Write `tests/complements/test_ine11.py` (failing) for `ine11.INE` (document level)
- [X] T062 [P] [US3] Write `tests/complements/test_aerolineas10.py` (failing) for `aerolineas10.Aerolineas` (document level)
- [X] T063 [P] [US3] Write `tests/complements/test_detallista.py` (failing) for `detallista.detallista` (document level; lowercase root; its values are text-only child elements)
- [X] T064 [P] [US3] Write `tests/complements/test_tpe10.py` (failing) for `tpe10.TuristaPasajeroExtranjero` (document level)
- [X] T065 [P] [US3] Write `tests/complements/test_ecc12.py` (failing) for `ecc12.EstadoDeCuentaCombustible` (document level)
- [X] T066 [P] [US3] Write `tests/complements/test_consumodecombustibles11.py` (failing) for `consumodecombustibles11.ConsumoDeCombustibles` (document level)
- [X] T067 [P] [US3] Write `tests/complements/test_gastoshidrocarburos10.py` (failing) for `gastoshidrocarburos10.GastosHidrocarburos` (document level)
- [X] T068 [P] [US3] Write `tests/complements/test_ingresoshidrocarburos10.py` (failing) for `ingresoshidrocarburos10.IngresosHidrocarburos` (document level)
- [X] T069 [P] [US3] Write `tests/complements/test_notariospublicos10.py` (failing) for `notariospublicos10.NotariosPublicos` (document level)
- [X] T070 [P] [US3] Write `tests/complements/test_arteantiguedades10.py` (failing) for `arteantiguedades10.obrasarteantiguedades` (document level; lowercase root)
- [X] T071 [P] [US3] Write `tests/complements/test_pagoenespecie10.py` (failing) for `pagoenespecie10.PagoEnEspecie` (document level)
- [X] T072 [P] [US3] Write `tests/complements/test_valesdedespensa10.py` (failing) for `valesdedespensa10.ValesDeDespensa` (document level)
- [X] T073 [P] [US3] Write `tests/complements/test_vehiculousado10.py` (failing) for `vehiculousado10.VehiculoUsado` (document level)
- [X] T074 [P] [US3] Write `tests/complements/test_renovacionysustitucionvehiculos10.py` (failing) for `renovacionysustitucionvehiculos10.renovacionysustitucionvehiculos` (document level; lowercase root)
- [X] T075 [P] [US3] Write `tests/complements/test_certificadodestruccion10.py` (failing) for `certificadodestruccion10.certificadodedestruccion` (document level; lowercase root)
- [X] T076 [P] [US3] Write `tests/complements/test_servicioparcialconstruccion10.py` (failing) for `servicioparcialconstruccion10.parcialesconstruccion` (document level; lowercase root)
- [X] T077 [P] [US3] Write `tests/complements/test_registrofiscal10.py` (failing) for `registrofiscal10.CFDIRegistroFiscal` (document level)
- [X] T078 [P] [US3] Write `tests/complements/test_pfic10.py` (failing) for `pfic10.PFintegranteCoordinado` (document level)
- [X] T079 [P] [US3] Write `tests/complements/test_iedu10.py` (failing) for `iedu10.instEducativas` attached to a concept through `ComplementoConcepto` (concept level; lowercase root)
- [X] T080 [P] [US3] Write `tests/complements/test_ventavehiculos11.py` (failing) for `ventavehiculos11.VentaVehiculos` attached to a concept (concept level)
- [X] T081 [P] [US3] Write `tests/complements/test_hidrocarburospetroliferos10.py` (failing) for `hidrocarburospetroliferos10.HidroYPetro` attached to a concept (concept level)
- [X] T082 [US3] Write `tests/test_retired.py` (failing until the modules exist): `mictlanix.cfdi` has no attribute or submodule for Carta Porte 2.0 or 3.0, Comercio Exterior 1.1, Pagos 1.0, Estado de Cuenta de Combustibles 1.1 or Terceros; no XSD for them is vendored; `tests/test_generated_models.py` covers exactly the 31 model modules of data-model.md (SC-001, SC-008)
- [X] T083 [US3] Write `tests/complements/test_multiple.py` (failing): a document carrying two document-level complements at once (`leyendasfiscales10.LeyendasFiscales` and `registrofiscal10.CFDIRegistroFiscal`) builds, validates and seals; and a document with `iedu10.instEducativas` placed under `Complemento` is reported by `validate` with rule `complement-level` and refused by `seal` (FR-024)
- [X] T084 [US3] Generate the 24 modules named in data-model.md 1.3 under `src/mictlanix/cfdi/` (21 `DocumentComplement`, and `iedu10`, `ventavehiculos11`, `hidrocarburospetroliferos10` as `ConceptComplement`), adding clash-table entries as the generator demands; register and export each; add to the `complement-document-type` table in `src/mictlanix/cfdi/_rules.py` exactly the entries the tests above demand; make T058 to T081 and the two tests above pass

**Checkpoint**: all five document types and all 29 complements are covered

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: what spans all stories

- [X] T085 [P] Update `README.md`: install (`pip install mictlanix-cfdi`), import (`import mictlanix.cfdi`), a short sealing example taken from quickstart.md scenario 1, the list of supported complements and versions, and how SAT artifacts are updated (`tools/fetch_sat.py`, `tools/generate_models.py`)
- [X] T086 [P] Update `CHANGELOG.md` under Unreleased: the import package `mictlanix.cfdi` and distribution `mictlanix-cfdi`; CFDI 4.0 documents, sealing, reading; the supported complement versions; and the complement versions that are deliberately not emitted
- [X] T087 Check the wheel: `uv build`, then confirm it contains `mictlanix/cfdi/sat/manifest.json` and the vendored XSDs and XSLTs, contains no `tools/` or `tests/`, and has no `mictlanix/__init__.py`
- [X] T088 Run every scenario in quickstart.md against the finished library and fix any gap; confirm the phases were executed in the order FR-031 sets (US1, then US2, then US3); tighten `tests/test_public_api.py` so that `mictlanix.cfdi.__all__` equals the Exports block of `contracts/public-api.md` exactly; confirm the four gates pass

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies; T001 first, then T002; T003 and T004 can run alongside either
- **Foundational (Phase 2)**: depends on Setup; blocks every user story
- **User Story 1 (Phase 3)**: depends on Foundational
- **User Story 2 (Phase 4)**: depends on Foundational and on US1's `compute`, `_rules.py`, `seal` and the shared test helper (T025, T029, T039, T045), which its tests call
- **User Story 3 (Phase 5)**: depends on Foundational and on US1's `seal`, rules and the shared test helper (T039, T029, T045), and on US2: T082 counts all 31 model modules, and T084 edits the same rule table and exports as T053
- **Polish (Phase 6)**: depends on the stories it covers

### Within Phase 2

- T005 → T006 → T007 → T008 → T009 (artifacts before the resolver's test can pass)
- T010 in parallel with the above
- T011 → T012 → T013 → T014 → T015 → T016
- T017 → T018; T019 → T020; T021 → T022 (each pair needs T016 and T009; T018, T020 and T022 need T010)

### Within User Story 1

- Derived values: T023 → T024 → T025
- Rules: T026 → T027 → T028 → T029 (T027 needs T023, whose script and test it extends; T029 needs T025)
- Pagos: T030 → T031 → T032 → T033 (T030 needs T029)
- Sealing: T034 → T035 → T036 → T037 → T038 → T039 (T037 needs T025 and T033; T038 needs T029)
- Reading: T040 → T041 → T042 → T043 → T044 (T040 needs T039)
- T045, then T046, last

The chains for derived values and CSD (up to T036) touch different source files.
T023, T027 and T030 all update `manifest.json`, so run them one after the other. The
Pagos chain starts after the rules chain (T030 adds to `_rules.py`). The others can proceed in
parallel until they meet at `seal`.

### Parallel Opportunities

- T003 and T004 alongside T001 and T002
- T010 alongside T006 to T009
- In US1: T023 to T025 and T034 to T036 can run side by side, apart from each adding its exports
  to `src/mictlanix/cfdi/__init__.py`
- In US2: T048 to T052 (five test files)
- In US3: T058 to T081 (24 test files)
- In Polish: T085 and T086

---

## Parallel Example: User Story 3

```text
After T057, write all complement tests together, each using the shared helper in `tests/complements/conftest.py`:
Task: "tests/complements/test_divisas10.py for divisas10.Divisas"
Task: "tests/complements/test_donat11.py for donat11.Donatarias"
Task: "tests/complements/test_iedu10.py for iedu10.instEducativas on a concept"
...then T084 generates the 24 modules and makes them pass.
```

---

## Implementation Strategy

### MVP First (User Story 1 only)

1. Phase 1: Setup
2. Phase 2: Foundational
3. Phase 3: User Story 1
4. **Stop and validate** with quickstart.md scenarios 1 to 5: this is a releasable library for
   invoices, credit notes and payment receipts

### Incremental Delivery (FR-031)

1. Setup and Foundational: models, XML, XSD validation, original string
2. User Story 1: the MVP
3. User Story 2: payroll, transport, foreign trade, local taxes, transfers
4. User Story 3: the remaining 24 complements
5. Polish

Each step leaves all four gates green and the library releasable.

---

## Notes

- **Rule scope**: the SAT codes are not listed here because they must come from the SAT's matrix
  itself; T026 produces that list as a reviewable contract before any rule is written.
- **Complement rule matrices**: the spec requires XSD validation for complements (FR-022), so
  the complements' own validation matrices are not implemented in this feature, except the
  Pagos 2.0 derivations (FR-025) and the two library rules that a complement sits on a document
  type and at a level the SAT allows.
- **Stamped fixtures are synthetic**: reading does not verify seals, so no real stamped CFDI is
  needed or committed.
- **Documents updated during implementation**: T026 (`contracts/validation-rules.md`), T031
  (data-model.md section 3.2) and T041 (research.md R9) write under `specs/` because they depend
  on SAT documents read at that point, and T034 changes the `Fecha` in quickstart.md if the test
  CSD's validity requires it; those edits belong to the code commit.
- **Risk to clear early**: T034 confirms the SAT's test keys load under `cryptography`.
- Do not commit per task. The project keeps one commit for the documents (made automatically
  before implementation starts) and one for the code, made when the work is ready with every
  gate passing.

## Phase 7: Convergence

- [X] T089 Obtain the published standard (the "Estándar" document on `https://www.sat.gob.mx/portal/public/tramites/complementos-de-factura`) of each of the 24 User Story 3 complements, and for each standard that restricts the document type, first add to its test in `tests/complements/` an assertion that the complement on a disallowed type is reported with rule `complement-document-type`, then add exactly that entry to `ALLOWED_DOCUMENT_TYPES` in `src/mictlanix/cfdi/_rules.py`; record the source and the allowed types of each in `specs/001-cfdi40-complements-sealing/contracts/validation-rules.md`; if a standard cannot be obtained, leave that complement without an entry and say so there, per spec Edge Cases (a complement on a document type the SAT does not allow is rejected at validation) (partial)

## Phase 8: Convergence

- [X] T090 Make the CSD validity naive Mexico City time (fixed UTC-6), superseding the "naive UTC" wording of T035 and T038: in `tests/test_csd.py` assert the test CSD's `valid_from == datetime(2023, 5, 18, 5, 43, 51)` and `valid_to == datetime(2027, 5, 18, 5, 43, 51)` and the same values in its `repr`; in `tests/test_seal.py` assert that a `Fecha` one second past `valid_to` in Mexico City time raises `CertificateValidityError` and that a `Fecha` exactly at either end seals; convert in `src/mictlanix/cfdi/_csd.py`; keep `contracts/public-api.md`, `research.md` and `data-model.md` saying the same, per FR-014 and mictlanix/mbe-api#106 (contradicts)

## Phase 9: The vendored SAT files move to their own folder (mictlanix/cfdi#10, 2026-11-18)

Feature 004 made `src/mictlanix/cfdi/sat/` the `mictlanix.cfdi.sat` package, so the vendored files
move out of it. The paths `src/mictlanix/cfdi/sat/…` in T006–T008, T023, T027 and T087 now read
`src/mictlanix/cfdi/_sat_files/…`; nothing else about those tasks changes.

- [X] T091 Move `sitio_internet/`, `catalogs/` and `manifest.json` from `src/mictlanix/cfdi/sat/` to `src/mictlanix/cfdi/_sat_files/` with `git mv` (byte-identical, constitution I), and point `src/mictlanix/cfdi/_sat.py`, `src/mictlanix/cfdi/_catalogs.py`, `tools/fetch_sat.py`, `tools/extract_catalogs.py`, `tests/test_sat_artifacts.py`, `tests/test_retired.py`, `README.md`, `research.md` R2 and `data-model.md` §5 at the new path; the full suite, ruff, mypy and `uv build` pass and the wheel ships the files under `mictlanix/cfdi/_sat_files/`
