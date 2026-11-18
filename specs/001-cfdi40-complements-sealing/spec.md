# Feature Specification: CFDI 4.0 Standard, Current Complements and Document Sealing

**Feature Branch**: `001-cfdi40-complements-sealing`

**Created**: 2026-11-17

**Status**: Draft

**Input**: User description: "CFDI 4.0 standard, all current complements and document sealing (mictlanix/cfdi#1). The library builds CFDI 4.0 documents, validates them against the SAT, computes their original string and seals them with the issuer's CSD, so a caller only has to hand the sealed XML to a PAC. It also reads stamped CFDIs. The SAT is the source of truth: Anexo 20, its XSDs, catalogs and XSLTs, at the versions the SAT accepts today."

## User Scenarios & Testing *(mandatory)*

The user of this feature is a developer whose application issues Mexican electronic invoices and
calls the library. "Caller" below means that application.

### User Story 1 - Invoices, credit notes and payment receipts, sealed and read back (Priority: P1)

A caller describes an income document (invoice), an expense document (credit note) or a payment
document carrying Pagos 2.0 using business data only: issuer, recipient, concepts with their
taxes, related CFDIs and, for payments, the payments and the documents they settle. The library
derives the totals and tax summaries, validates the document against the SAT's rules, computes
its original string and seals it with the issuer's CSD. The caller receives sealed XML that is
ready to hand to a PAC. Once a document has been stamped, the caller gives the stamped XML back
to the library and reads the document and its TimbreFiscalDigital, including the data for the
SAT verification QR.

**Why this priority**: invoices, payment receipts and credit notes are what a business must stamp
first; without them nothing else in the library is usable.

**Independent Test**: using only the SAT's public test CSDs and no network, build one income, one
expense and one payment document, validate and seal each, and confirm each is valid against the
SAT's XSDs and that its seal verifies against the original string produced by the SAT's XSLT;
then read a stamped sample and confirm the TFD fields and QR data.

**Acceptance Scenarios**:

1. **Given** an income document described with issuer, recipient and concepts with transferred
   and withheld taxes, **When** the caller builds it, **Then** the subtotal, discount, total and
   document-level tax summaries are derived by the library with the SAT's rounding rules.
2. **Given** a built income, expense or payment document, **When** the caller validates it,
   **Then** it is checked against `cfdv40.xsd`, `catCFDI.xsd`, `tdCFDI.xsd` and the catalog rules
   of Anexo 20, and it passes.
3. **Given** a document that breaks a SAT rule, **When** the caller validates it, **Then** every
   error names the node and the rule that was broken, and no sealed document is produced.
4. **Given** a valid document and the issuer's CSD (certificate, encrypted private key and
   password), **When** the caller seals it, **Then** the document carries `Sello`,
   `NoCertificado` and `Certificado`, and the seal verifies against the original string computed
   with `cadenaoriginal_4_0.xslt`.
5. **Given** a payment document, **When** the caller builds it with one or more payments and the
   documents they settle, **Then** it carries a valid Pagos 2.0 complement, including the payment
   totals the standard derives, and that complement is part of the original string.
6. **Given** a CSD whose private key does not match its certificate, a wrong password, or a
   certificate that is not valid on the document's issue date, **When** the caller loads the CSD
   or seals, **Then** the operation fails with a specific error and reveals no key material or
   password.
7. **Given** a stamped CFDI, **When** the caller reads it, **Then** the caller gets the document,
   its TimbreFiscalDigital 1.1 (UUID, stamp date, SAT seal, SAT certificate number, provider
   RFC), the TFD's original string computed with `cadenaoriginal_TFD_1_1.xslt`, and the data for
   the SAT verification QR.

---

### User Story 2 - Payroll, transport, foreign trade, local taxes and transfer documents (Priority: P2)

A caller issues payroll receipts (document type N with Nómina 1.2), documents carrying Carta
Porte 3.1, Comercio Exterior 2.0 or Impuestos Locales 1.0, and transfer documents (type T). Each
is built from typed data, validated, and sealed the same way as the P1 documents.

**Why this priority**: these are the next most common obligations (payroll, goods transport,
exports and local taxes) and each one blocks a whole business process for the callers that need
it, but none is needed to start stamping invoices.

**Independent Test**: with the P1 capabilities in place, build, validate and seal one payroll
document with Nómina 1.2, one transfer document, and one document for each of Carta Porte 3.1,
Comercio Exterior 2.0 and Impuestos Locales 1.0, each checked against the SAT's XSD and XSLT.

**Acceptance Scenarios**:

1. **Given** payroll data for an employee, **When** the caller builds a payroll document,
   **Then** it is a type N document carrying a valid Nómina 1.2 complement.
2. **Given** a transfer of goods, **When** the caller builds a transfer document, **Then** it is
   a valid type T document, with or without Carta Porte 3.1.
3. **Given** a document that carries Carta Porte 3.1, Comercio Exterior 2.0 or Impuestos Locales
   1.0, **When** the caller validates and seals it, **Then** the complement is validated against
   its own SAT XSD and is included in the original string that is signed.
4. **Given** complement data that breaks the complement's XSD, **When** the caller validates,
   **Then** the error names the complement node and the rule.

---

### User Story 3 - The remaining complements (Priority: P3)

A caller in a specialised sector (donations, fuel, hydrocarbons, notaries, vehicles, education,
airlines, retail suppliers and others) builds, validates and seals a document carrying any of the
other complements the SAT accepts today, at document level or at concept level.

**Why this priority**: each of these complements serves a narrow sector; together they complete
the standard, but they are not needed by most callers.

**Independent Test**: for each remaining complement, build, validate and seal one document
carrying it, checked against that complement's SAT XSD and against the SAT's XSLT.

**Acceptance Scenarios**:

1. **Given** data for any remaining document-level complement, **When** the caller builds,
   validates and seals a document carrying it, **Then** the complement is valid against its SAT
   XSD and is part of the signed original string.
2. **Given** data for a concept-level complement, **When** the caller attaches it to a concept,
   **Then** it appears in that concept, is valid against its SAT XSD and is part of the signed
   original string.
3. **Given** a caller looking for a retired complement or version, **When** they try to emit it,
   **Then** the library offers no way to do so.

---

### Edge Cases

- Amounts whose per-concept taxes, once rounded, do not add up exactly to the document-level tax
  totals: the library applies the SAT's rounding rules so the document is still valid.
- Currencies with a different number of decimals than MXN, and foreign-currency documents that
  need an exchange rate.
- A payment document must carry the fixed values the standard imposes for type P (no payment
  method or form at document level, currency `XXX`, zero subtotal and total, a single fixed
  concept); the library sets them, the caller does not.
- A global invoice to the general public requires `InformacionGlobal`; a document issued on
  behalf of third parties requires `ACuentaTerceros` on the concept.
- Concepts that are not subject to tax, or subject but not broken down, carry no tax nodes; the
  tax object of each concept decides this.
- A complement attached to a document type, or to a level (document or concept), that the SAT
  does not allow for it is rejected at validation.
- A document carrying several complements at once.
- A CSD certificate that is expired, or not yet valid, on the issue date; a private key that does
  not belong to the certificate; a wrong password; a file that is not a certificate or key at all.
- Reading XML that is malformed, is not a CFDI 4.0, or has not been stamped (no
  TimbreFiscalDigital): each is reported with a specific error.
- Reading a stamped CFDI that carries a complement or version the library does not model: the
  document and its TFD are still read (see Assumptions).

## Requirements *(mandatory)*

### Functional Requirements

**Documents**

- **FR-001**: The library MUST let a caller build CFDI 4.0 documents of every type: income (I),
  expense (E), payment (P), payroll (N) and transfer (T).
- **FR-002**: Documents MUST be able to carry every node of `cfdv40.xsd`, including issuer,
  recipient, concepts, concept taxes (transferred and withheld, by rate and by tax object),
  document-level tax totals, related CFDIs, `ACuentaTerceros` and `InformacionGlobal`.
- **FR-003**: Documents, their parts and every complement MUST be described through typed models,
  so a caller's mistakes in shape or type are caught before any XML exists.
- **FR-004**: The library MUST compute the values the standard derives (subtotal, discount,
  total, and the document-level summaries of transferred and withheld taxes) using the SAT's
  rounding rules; callers MUST NOT have to supply them.
- **FR-005**: The library MUST produce the document as CFDI 4.0 XML.

**Validation**

- **FR-006**: The library MUST validate a document against the SAT's `cfdv40.xsd`, `catCFDI.xsd`
  and `tdCFDI.xsd`.
- **FR-007**: The library MUST validate a document against the catalog rules of Anexo 20 that
  can be decided offline (see Assumptions).
- **FR-008**: Every validation error MUST name the node and the rule that was broken, in a form
  a caller can act on without parsing free text.
- **FR-009**: Validation MUST report all the errors it finds in a document, not only the first.
- **FR-010**: A document that fails validation MUST NOT be sealed.

**Original string and sealing**

- **FR-011**: The library MUST compute a document's original string with the SAT's
  `cadenaoriginal_4_0.xslt`.
- **FR-012**: The library MUST load a CSD from its certificate (.cer, DER) and its encrypted
  private key (.key, PKCS#8) with the key's password, all supplied by the caller.
- **FR-013**: The library MUST refuse a CSD whose private key does not match its certificate.
- **FR-014**: The library MUST refuse to seal a document whose issue date falls outside the
  certificate's validity period.
- **FR-015**: The library MUST sign the original string with RSA-SHA256 and write `Sello`,
  `NoCertificado` and `Certificado` into the document.
- **FR-016**: The sealed document MUST be returned as XML ready to hand to a PAC, with no further
  change needed by the caller.

**Reading stamped CFDIs**

- **FR-017**: The library MUST read a stamped CFDI 4.0 and return the document as typed models.
- **FR-018**: The library MUST read the document's TimbreFiscalDigital 1.1: UUID, stamp date, SAT
  seal, SAT certificate number and provider RFC.
- **FR-019**: The library MUST compute the TFD's original string with the SAT's
  `cadenaoriginal_TFD_1_1.xslt`.
- **FR-020**: The library MUST provide the data for the SAT verification QR of a stamped CFDI.
- **FR-021**: Reading MUST fail with a specific error when the input is not well-formed XML, is
  not a CFDI 4.0, or (when the TFD is requested) carries no TimbreFiscalDigital.

**Complements**

- **FR-022**: For each complement below, at the stated version, the library MUST provide typed
  models, validation against the complement's SAT XSD, and the complement's part of the original
  string.
  - Document level: Pagos 2.0, Nómina 1.2, Carta Porte 3.1, Comercio Exterior 2.0, Impuestos
    Locales 1.0, Divisas 1.0, Donatarias 1.1, Leyendas Fiscales 1.0, INE 1.1, Aerolíneas 1.0,
    Detallista 1.3.1, Turista Pasajero Extranjero 1.0, Estado de Cuenta de Combustibles 1.2,
    Consumo de Combustibles 1.1, Gastos de Hidrocarburos 1.0, Ingresos de Hidrocarburos 1.0,
    Notarios Públicos 1.0, Obras de Arte y Antigüedades 1.0, Pago en Especie 1.0, Vales de
    Despensa 1.0, Vehículo Usado 1.0, Renovación y Sustitución de Vehículos 1.0, Certificado de
    Destrucción 1.0, Servicios Parciales de Construcción 1.0, CFDI Registro Fiscal 1.0, PFIC 1.0.
  - Concept level: Instituciones Educativas Privadas 1.0, Venta de Vehículos 1.1, Hidrocarburos
    y Petrolíferos 1.0.
- **FR-023**: The library MUST NOT emit Carta Porte 2.0 or 3.0, Comercio Exterior 1.1, Pagos 1.0,
  Estado de Cuenta de Combustibles 1.1, or Terceros.
- **FR-024**: A document MUST be able to carry more than one complement where the SAT allows it.
- **FR-025**: For Pagos 2.0, the library MUST compute the payment totals and tax summaries the
  complement derives, with the SAT's rounding rules.

**SAT artifacts, secrets and naming**

- **FR-026**: The SAT's XSDs and XSLTs used by the library MUST be shipped inside the package,
  each with its SAT publication date; no operation in this feature may need network access.
- **FR-027**: Certificates, private keys and passwords MUST come only from the caller and MUST
  NOT appear in errors, logs or the printed representation of a CSD.
- **FR-028**: The repository, tests and fixtures MUST contain only the SAT's public test CSDs; no
  real certificate, key or password.
- **FR-029**: SAT names (fields, catalogs and complements) MUST keep their official Spanish
  spelling throughout the library.
- **FR-030**: Each document type and each complement MUST have at least one automated test that
  builds, validates and seals a document carrying it, checked against the SAT's XSD and XSLT, and
  that runs offline.

**Delivery order**

- **FR-031**: Delivery follows the three user stories in order: P1 (income, expense and payment
  documents with Pagos 2.0, sealing, reading the TFD), P2 (Nómina 1.2, Carta Porte 3.1, Comercio
  Exterior 2.0, Impuestos Locales 1.0 and transfer documents), P3 (the remaining complements).

**Out of scope**

- Talking to a PAC: stamping and cancelling (mictlanix/cfdi#2, mictlanix/cfdi#3).
- CFDI de Retenciones e Información de Pagos, which is a separate standard.
- PDF rendering.

### Key Entities

- **Comprobante (CFDI 4.0 document)**: the fiscal document. Has a type (I, E, P, N, T), an issue
  date, currency, issuer, recipient, concepts, optional related CFDIs, optional
  `InformacionGlobal`, derived totals and tax summaries, zero or more document-level complements
  and, once sealed, `Sello`, `NoCertificado` and `Certificado`.
- **Emisor / Receptor**: who issues and who receives the document, with their RFC, name, tax
  regime and, for the recipient, fiscal postcode and CFDI use.
- **Concepto**: one line of the document: product or service key, quantity, unit, description,
  amounts, tax object, its transferred and withheld taxes, optional `ACuentaTerceros` and
  optional concept-level complements.
- **Impuestos**: taxes at concept level (base, tax, factor type, rate, amount) and their derived
  summary at document level.
- **CfdiRelacionados**: references to earlier CFDIs by UUID, with the type of relation.
- **Complemento**: a SAT extension attached to the document or to a concept, each with its own
  version, XSD and contribution to the original string.
- **CSD (Certificado de Sello Digital)**: the issuer's certificate and private key used to seal;
  exposes the certificate number and validity period, never the key material.
- **Cadena original**: the canonical string the SAT derives from a document (or from a TFD) and
  that is signed.
- **TimbreFiscalDigital 1.1**: the stamp a PAC adds: UUID, stamp date, SAT seal, SAT certificate
  number and provider RFC.
- **Validation error**: one broken rule, identified by the node it concerns and the rule it
  breaks.
- **SAT artifact**: an XSD or XSLT published by the SAT, shipped with its publication date.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All 5 document types and all 29 listed complements (26 at document level, 3 at
  concept level) can be built, validated and sealed, each demonstrated by at least one test
  checked against the SAT's own XSD and XSLT.
- **SC-002**: 100% of sealed test documents carry a seal that verifies against the original
  string produced by the SAT's XSLT, and sealing with the SAT's public test CSDs reproduces the
  known expected results.
- **SC-003**: The complete test suite passes with the network disabled.
- **SC-004**: A caller produces a sealed invoice from business data alone: no derived total, tax
  summary, original string or seal is supplied by the caller.
- **SC-005**: Every validation failure in the test suite identifies the offending node and the
  broken rule; no test needs to inspect free-text messages to tell failures apart.
- **SC-006**: No certificate key material or password appears in any error, log or printed
  representation produced by the test suite, and the repository contains no CSD other than the
  SAT's public test ones.
- **SC-007**: For a stamped sample CFDI, the UUID, stamp date, SAT seal, SAT certificate number,
  provider RFC, TFD original string and QR data read by the library match the sample's known
  values exactly.
- **SC-008**: None of the six retired complements or versions can be emitted through the
  library.

## Assumptions

- "The versions the SAT accepts today" are the complement versions listed in FR-022; the list is
  taken as given and is not re-derived in this feature.
- Validation is offline and structural: the SAT's XSDs plus the Anexo 20 catalog rules that can
  be checked from the document and the shipped SAT artifacts alone. Checks that need the SAT's
  live registries (for example, that an RFC exists or that a recipient's name and postcode match
  the SAT's records) are left to the PAC.
- Reading a stamped CFDI returns typed models for the document and for the complements this
  feature supports. A stamped document carrying a complement or version the library does not
  model (including the retired ones in FR-023) is still read, with its document and TFD
  available; that complement is not returned as a typed model.
- Reading does not verify the issuer's seal or the SAT's seal; it parses and exposes them.
  Verifying a CFDI's status with the SAT is not part of this feature.
- The QR requirement covers the data that goes into the SAT verification QR (the verification
  address with UUID, issuer RFC, recipient RFC, total and the last eight characters of the
  issuer's seal); drawing the QR image is left to the caller.
- Only CFDI 4.0 is built and read; earlier versions (3.3 and before) are rejected on reading.
- The library does not obtain, store or manage CSDs: the caller supplies them for each use.
- Known-good sealing results for the SAT's public test CSDs are produced once, independently of
  the library, and kept as test expectations.
