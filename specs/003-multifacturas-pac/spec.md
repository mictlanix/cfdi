# Feature Specification: Facturación México (Multifacturas) PAC Client

**Feature Branch**: `003-multifacturas-pac`

**Created**: 2026-11-18

**Status**: Draft

**Input**: User description: "Facturación México (Multifacturas) PAC client (mictlanix/cfdi#3). Implement `PacClient` (spec 002) for Facturación México, the PAC the current system uses, so a caller can swap `SimulatedPac` for it with no other change."

## User Scenarios & Testing *(mandatory)*

The user of this feature is a developer whose application issues Mexican electronic invoices and
already stamps and cancels through the library's PAC interface (spec 002) with the simulated PAC.
"Caller" below means that application. Facturación México (Multifacturas) is the PAC the current
system (mbe) uses in production.

### User Story 1 - Stamp through Multifacturas (Priority: P1)

A caller that stamps with the simulated PAC swaps it for the Multifacturas client, configured with
its PAC user and password, whether to use the PAC's production or test mode, the endpoint and the
timeouts, and stamps a sealed document. It receives the stamped document and its
TimbreFiscalDigital exactly as from the simulated PAC. A document the SAT reports as already
stamped (SAT 307) gives back its existing stamp, not an error. The PAC's refusals reach the caller
as PAC-rejected errors with the PAC's own code and message; a PAC that cannot be reached is
unavailable; a call that times out after it was sent is a timeout with unknown outcome.

**Why this priority**: stamping is what the current system needs from the PAC every day; the
interface already exists, so this is the first real use of it.

**Independent Test**: offline, replay recorded and scrubbed PAC responses for a successful stamp,
a duplicate (307), a rejection and a transport failure, and check the stamp, the error kinds and
that nothing secret appears in errors; opt-in, stamp a document with the SAT's test CSD in the
PAC's test mode.

**Acceptance Scenarios**:

1. **Given** a sealed CFDI 4.0 and valid PAC credentials, **When** the caller stamps it, **Then**
   it receives the stamped document and its stamp (UUID in upper case, stamp date, SAT seal, SAT
   certificate number, provider RFC), as the interface defines.
2. **Given** a sealed document the SAT already stamped, **When** the caller stamps it again,
   **Then** it receives that existing stamp and no second stamp is made.
3. **Given** a document the PAC refuses, **When** the caller stamps it, **Then** a PAC-rejected
   error carries the PAC's code and message, and nothing secret or the document's XML appears in
   it.
4. **Given** the PAC cannot be reached (name resolution, connection or TLS failure before the
   request is sent), **When** the caller stamps, **Then** the unavailable error is raised.
5. **Given** the request was sent and no answer arrives within the caller's timeout, **When** the
   caller stamps, **Then** the timeout error is raised, and the caller resolves it as the
   interface prescribes without ever producing a second stamp (FR-006).
6. **Given** the caller passes an endpoint that is not HTTPS, **When** it creates the client,
   **Then** it is refused.

---

### User Story 2 - Cancel through Multifacturas and follow the SAT status (Priority: P2)

A caller requests the cancellation of a stamped document with the issuer and recipient RFCs, the
UUID, the total, the SAT reason, the substitute UUID when the reason requires it, and the issuer's
CSD. The client sends the PAC only what it needs from the CSD and answers accepted, pending or not
cancellable. The caller queries the document's SAT status (state, cancellability, cancellation
status) the same way as with the simulated PAC.

**Why this priority**: cancelling is the second operation every issuer needs; it builds on
stamped documents from P1.

**Independent Test**: offline, replay recorded cancellation answers (accepted, pending, not
cancellable, a refusal) and SAT status answers, and check the mapped answer and status; opt-in,
cancel a document stamped in the PAC's test mode and query its status.

**Acceptance Scenarios**:

1. **Given** a stamped document that can be cancelled without acceptance, **When** the caller
   requests its cancellation, **Then** the answer is accepted.
2. **Given** a document that needs the recipient's acceptance, **When** the caller requests its
   cancellation, **Then** the answer is pending.
3. **Given** a document the SAT will not cancel (for example, it has related documents), **When**
   the caller requests its cancellation, **Then** the answer is not cancellable.
4. **Given** the PAC refuses the request (wrong CSD password, CSD not matching the issuer, UUID
   not found), **When** the caller requests it, **Then** a PAC-rejected error carries the PAC's
   code and message, without the password, key or certificate.
5. **Given** a UUID, its RFCs and total, **When** the caller queries the status, **Then** it
   receives the SAT's state, cancellability and cancellation status mapped to the interface's
   values; a UUID the SAT does not know with those values is not found.

---

### User Story 3 - Check the stamp balance (Priority: P3)

An operator monitoring the account asks the client for the PAC account's remaining stamp
balance.

**Why this priority**: useful for monitoring and alerts, not needed to stamp or cancel.

**Independent Test**: offline, replay a recorded balance answer and check the number; opt-in,
query the test account's balance.

**Acceptance Scenarios**:

1. **Given** valid PAC credentials, **When** the caller asks for the balance, **Then** it
   receives the number of stamps left as an integer.
2. **Given** wrong credentials, **When** the caller asks for the balance, **Then** a PAC-rejected
   error carries the PAC's code and message.

---

### Edge Cases

- The PAC answers with something that is not the expected envelope (HTML error page, empty body,
  malformed XML, an HTTP error status): the request was sent and may have been processed, so it
  is reported as the timeout error, never as another error type, and without quoting the body.
  A SOAP Fault means the service refused the request: a PAC-rejected error with a library code.
- The PAC answers success but the stamped document it returns is missing, not CFDI 4.0, or has no
  TimbreFiscalDigital, or its seal is not the submitted document's: reported as a PAC-rejected
  error with a library code; the caller resolves it like a timeout.
- A duplicate (307) answer that does not carry the existing stamp: the client obtains it from the
  PAC by the UUID the answer gives; if neither is available it is reported as a timeout (outcome
  known to the SAT, stamp not obtainable now), never as a successful new stamp.
- The PAC's test mode: the same endpoint with test mode on; documents stamped there are not valid
  fiscal documents and are not known to the SAT's public consultation service.
- The caller's timeout elapses while connecting: unavailable (nothing was sent); while waiting
  for the answer: timeout.
- Credentials, the CSD, the password and raw PAC payloads never appear in an error, a log or a
  printed representation of the client or its settings.

## Requirements *(mandatory)*

### Functional Requirements

**The client**

- **FR-001**: The library MUST provide a Multifacturas client that implements the PAC interface of
  spec 002 (stamp, find a stamp, request a cancellation, query the status), so a caller can
  replace the simulated PAC with it and change nothing else.
- **FR-002**: The client MUST receive from the caller its PAC user and password, whether to use
  the PAC's production or test mode, the endpoint base and the timeouts; it MUST NOT read the
  environment or any file.
- **FR-003**: The client MUST call the PAC only over HTTPS with certificate verification, and MUST
  refuse an endpoint that is not HTTPS. Its default endpoint is `ws.multifacturas.com`, whose
  certificate verifies; the caller may set another HTTPS endpoint. The `facturacionmexico` hosts,
  whose certificates fail verification, are never the default.
- **FR-004**: The client's settings MUST be immutable, and their printed representation MUST NOT
  show the password.

**Stamping**

- **FR-005**: Stamping MUST send the sealed document to the PAC's stamping operation and return
  the stamp as the interface defines.
- **FR-006**: A document the SAT already stamped (SAT 307, "previously stamped") MUST return its
  existing stamp, obtained from the duplicate answer or, by the UUID it carries, from the PAC's
  retrieval operation; it MUST NOT be reported as an error and MUST NOT produce a second stamp.
- **FR-007**: The PAC offers no way to find a stamp from the sealed document (its retrieval
  operations need the UUID, which a caller does not have after a timeout). Finding a stamp MUST
  therefore return nothing without calling the PAC. The caller then stamps again, which FR-006
  turns into the existing stamp, so a timeout never produces a second stamp, as constitution
  v1.1.0 principle IV admits. *(Clarified with the user, 2026-11-18.)*

**Cancelling and status**

- **FR-008**: Requesting a cancellation MUST use the PAC's current cancellation service (the one
  that takes the SAT reason 01–04 and the substitute UUID) and send it only what it needs from the
  CSD: the certificate and the encrypted private key as the PAC expects them, and the key's
  password; nothing else about the caller.
- **FR-009**: The PAC's cancellation answer MUST be mapped to accepted, pending or not
  cancellable; a refusal MUST be a PAC-rejected error with the PAC's code and message.
- **FR-010**: Querying the status MUST answer from the SAT's public consultation service (the
  source of truth, already used to verify QR data in spec 001), mapped to the interface's state,
  cancellability and cancellation status; an unknown UUID or mismatching RFCs or total is not
  found.

**Balance**

- **FR-011**: The client MUST offer the PAC account's remaining stamp balance as an integer, as
  an operation of this client only (not part of the generic interface).

**Errors**

- **FR-012**: Every PAC error code MUST become a PAC-rejected error with the PAC's code and
  message. The spec's code map (below, completed during planning from the PAC's answers) lists
  every code found and its meaning.
- **FR-013**: A failure before the request is sent (name resolution, connection, TLS) MUST be the
  unavailable error; a timeout or connection loss after it is sent MUST be the timeout error. No
  other error type escapes an operation (spec 002 FR-006).
- **FR-014**: No credential, CSD material, password or raw PAC payload MUST appear in an error, a
  log or a printed representation (spec 002 FR-009).

**Testing**

- **FR-015**: Tests MUST run offline by default, replaying recorded PAC and SAT responses scrubbed
  of credentials, certificates, seals and real RFCs.
- **FR-016**: Tests against the PAC's test mode MUST be opt-in through environment variables
  holding the test credentials, and MUST be skipped when those are absent.

### PAC code map

Codes the client distinguishes, completed during planning from the PAC's recorded answers, its
published examples and the SAT's cancellation codes (data-model.md §8). Any other code becomes a
PAC-rejected error with that code and message.

| Code | Meaning | Client behaviour |
|------|---------|------------------|
| `0` | Success (`codigo_mf_numero`) | Stamp, cancellation answer or balance returned |
| `301` | XML structure incorrect (SAT validation, recorded) | PAC-rejected |
| `CFDI40102` | Seal does not verify (SAT validation, recorded) | PAC-rejected |
| `307` | CFDI previously stamped (SAT) | Existing stamp returned (FR-006) |
| `CACFDI33` | Cancellation fields problem, e.g. key not matching the certificate (recorded) | PAC-rejected |
| `CSF101` | The document cannot be cancelled (PAC examples) | PAC-rejected |
| `40150` | Cancellation reason not valid (PAC examples) | PAC-rejected |
| `201` | SAT received the cancellation request | The SAT's status decides the answer |
| `202` | SAT: cancellation previously requested | The SAT's status decides the answer |
| `203`, `205` | SAT: issuer does not match; UUID does not exist (205 recorded) | PAC-rejected |
| `MF-ANSWER`, `SAT-ANSWER`, `SOAP-FAULT` | Library: unusable success answer, unexpected SAT status, SOAP Fault | PAC-rejected |

### Key Entities

- **Multifacturas client**: an implementation of the PAC interface for Facturación México, with
  its settings and one extra operation, the stamp balance.
- **Client settings**: PAC user and password, production or test mode, endpoint base, connect
  and read timeouts; immutable; the password is never printed.
- **PAC code map**: the PAC's and the SAT's codes the client recognises and how each maps to the
  interface's answers and errors.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A caller's stamping and cancellation code that runs against the simulated PAC runs
  against the Multifacturas client after changing only how the client is created.
- **SC-002**: In 100% of the offline tests, every recorded PAC answer (success, duplicate,
  each code in the code map, malformed answers, transport failures) maps to the answer or error
  type the spec prescribes.
- **SC-003**: Re-stamping a document after a timeout never yields a second UUID, shown offline by
  the recorded duplicate answer and opt-in in the PAC's test mode.
- **SC-004**: No error, printed value or log produced by the test suite contains the PAC
  password, the CSD's key, password or certificate, or a raw PAC payload.
- **SC-005**: The test suite runs offline; the opt-in tests run only when their environment
  variables are set.
- **SC-006**: Every call the client makes uses HTTPS with certificate verification.

## Assumptions

- The PAC operations, confirmed against its WSDLs (`https://ws.multifacturas.com/pac/index.php?wsdl`
  and `https://ws.multifacturas.com/cancelacion2022/index.php?wsdl`, both of which advertise
  plain-HTTP addresses that the client upgrades) and the current system's client (mictlanix
  dfacture-client `DFactureClient40`, used by mbe `CFDHelpers40`):
  - stamping: `timbrar33b64` (Base64 UTF-8 XML, typed answer with `codigo_mf_numero`,
    `codigo_mf_texto`, `uuid`, `cfdi`), the one the current system uses; `timbrar` and
    `timbrar64` answer untyped arrays;
  - retrieval by UUID: `acuseSAT` (returns the stamped document, as the current system uses it)
    and `factura_recupera_respaldo`; neither looks up by sealed document;
  - cancellation: `cancelarCfdi` of the `cancelacion2022` service, taking the user, password,
    production flag, UUID, issuer RFC, CSD password, reason, substitute UUID and the certificate
    and key in Base64; the older `cancelar` and `cancela_ut8` take no reason and are not used;
  - balance: `saldo`.
- The PAC's test mode is the same endpoint with the production flag off; the PAC publishes demo
  credentials for it, which the opt-in tests and planning use (user's decision, 2026-11-18).
- The current system disables TLS certificate verification and uses the `facturacionmexico` hosts
  over plain HTTP; this client does neither.
- The SAT's public consultation service needs no credentials and is the one spec 001's QR data was
  verified against.
- Not verified, because documents stamped in test mode never reach the SAT: that the SAT answers
  a request to cancel a non-cancellable document by receiving it (201) and then reporting it as
  not cancellable in its status. If the SAT instead refuses the request with its own code, that
  code reaches the caller as a PAC-rejected error carrying it.
- Not verified in test mode (it answers `200` there): that the PAC's retrieval by UUID returns the
  stamped document in production, as the current system relies on; the client's path for a 307
  answer that carries only the UUID depends on it.
- Not verifiable in test mode, which ignores the password: the code the PAC answers for wrong
  credentials. Whatever it is reaches the caller as a PAC-rejected error carrying it (FR-012).
- The PAC's documentation lists few codes publicly; the code map is completed from recorded
  answers during planning.
- Out of scope: other PACs, retentions (`retencion`), tickets, bulk backups and reports, and the
  PAC's acceptance or rejection of cancellations on the recipient's behalf.
