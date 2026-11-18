# Feature Specification: Generic PAC Client Interface and a Simulated PAC

**Feature Branch**: `002-pac-interface-simulator`

**Created**: 2026-11-18

**Status**: Draft

> **Amended by feature 003 (mictlanix/cfdi#3), 2026-11-18:** `query_status` and its values
> (`SatStatus`, `SatState`, `Cancellability`, `CancellationStatus`) were removed from `PacClient`
> and `SimulatedPac`. The SAT's status service does not depend on the PAC; a PAC-independent
> client for it is tracked in mictlanix/cfdi#6. The requirements below that concern the SAT
> status are superseded; the simulator still keeps that state to decide its answers.

**Input**: User description: "Generic PAC client interface and a simulated PAC (mictlanix/cfdi#2). Callers stamp and cancel CFDI 4.0 documents through one interface, whatever the PAC. This spec defines that interface and a simulated PAC that implements it. The first real PAC (Facturación México / Multifacturas) comes next in #3 on the same interface."

## User Scenarios & Testing *(mandatory)*

The user of this feature is a developer whose application issues Mexican electronic invoices.
"Caller" below means that application. A PAC is the authorized provider that stamps a sealed CFDI
(adds the SAT's TimbreFiscalDigital) and relays cancellations to the SAT. The caller writes its
stamping and cancellation logic once, against the interface, and runs it against the simulated
PAC in development and tests and against a real PAC (#3) in production.

### User Story 1 - Stamp a sealed document, safely (Priority: P1)

A caller hands a sealed CFDI 4.0 to the PAC and receives the stamped document together with its
TimbreFiscalDigital 1.1: UUID, stamp date, SAT seal, SAT certificate number and provider RFC.
When the call fails, the caller learns which of three things happened from the error's type
alone: the PAC refused the document (with the PAC's code and message), the PAC could not be
reached (nothing happened, retrying is safe), or the call timed out (the outcome is unknown).
After a timeout the caller asks the PAC whether it already stamped that document, and gets the
stamp back if it did, so a document is never stamped twice.

**Why this priority**: stamping is what makes a CFDI a fiscal document; nothing else in this
feature matters until a caller can stamp and recover from failures without duplicating a stamp.

**Independent Test**: with the simulated PAC and no network, seal a document with the library,
stamp it, and confirm the stamped document carries a TimbreFiscalDigital that is valid against
the SAT's schema and whose original string matches the SAT's stylesheet; then drive the
rejected, unavailable and both timeout paths and confirm each error type, and that looking the
stamp up after a timeout returns the stamp exactly when one was made.

**Acceptance Scenarios**:

1. **Given** a sealed CFDI 4.0, **When** the caller stamps it with the simulated PAC, **Then** it
   receives the stamped document and its stamp: an upper-case UUID, a stamp date in Mexico City
   time, a SAT seal, a SAT certificate number and the provider RFC `SIM010101SI0`, and the stamp
   inside the document carries the document's own seal.
2. **Given** a document the PAC already stamped, **When** the caller stamps the same sealed
   document again, **Then** it receives the same stamp (same UUID, same date, same document) and
   no second stamp exists.
3. **Given** a document configured to be rejected with a code and a message, **When** the caller
   stamps it, **Then** the PAC-rejected error carries exactly that code and message and nothing is
   stamped.
4. **Given** a document configured as unavailable, **When** the caller stamps it, **Then** the
   unavailable error is raised and nothing is stamped.
5. **Given** a document configured to time out after stamping, **When** the caller stamps it,
   **Then** the timeout error is raised, and looking the stamp up returns the stamp that was made.
6. **Given** a document configured to time out without stamping, **When** the caller stamps it,
   **Then** the timeout error is raised, looking the stamp up returns nothing, and stamping again
   succeeds.
7. **Given** a document the PAC never saw, **When** the caller looks its stamp up, **Then** it
   gets nothing back and nothing is stamped.

---

### User Story 2 - Cancel a stamped document and follow its SAT status (Priority: P2)

A caller asks the PAC to cancel a stamped document, giving the issuer and recipient RFCs, the
UUID, the total, the SAT cancellation reason and the issuer's CSD. The answer is one of three:
cancelled at once, pending (the SAT waits for the recipient to accept or reject), or not
cancellable. The caller then queries the document's SAT status, which reports its state (valid,
cancelled, not found), whether it can be cancelled (without acceptance, with acceptance, not
cancellable) and where its cancellation stands (none, requested, pending, accepted, rejected,
expired). With the simulated PAC, the caller can also play the recipient and accept or reject a
pending cancellation, or let its time limit pass.

**Why this priority**: cancelling is the second thing every issuer must do, and pending
cancellations are the part callers most often get wrong; it builds on stamped documents from P1.

**Independent Test**: with the simulated PAC, stamp documents, then drive each cancellation path
(accepted at once, pending then accepted, pending then rejected, pending then expired, not
cancellable, rejected, unavailable, timeout) and confirm the answer and the SAT status after each
step; build cancellation requests with every reason and confirm the substitute-UUID rule.

**Acceptance Scenarios**:

1. **Given** a document stamped less than 24 hours ago, **When** the caller requests its
   cancellation, **Then** the answer is accepted and the SAT status is cancelled, cancellation
   accepted.
2. **Given** a document stamped more than 24 hours ago, **When** the caller requests its
   cancellation, **Then** the answer is pending and the SAT status is valid, cancellable with
   acceptance, cancellation pending.
3. **Given** a pending cancellation, **When** the recipient accepts it, **Then** the SAT status
   becomes cancelled, cancellation accepted; **When** the recipient rejects it instead, **Then**
   it becomes valid, cancellation rejected; **When** its time limit passes instead, **Then** it
   becomes cancelled, cancellation expired.
4. **Given** a document configured as not cancellable, **When** the caller requests its
   cancellation, **Then** the answer is not cancellable, the document stays valid, and its status
   reports it as not cancellable.
5. **Given** a cancellation configured to be rejected, unavailable or to time out, **When** the
   caller requests it, **Then** the matching error type is raised; after a rejection or an
   unavailable PAC nothing changes, and after a timeout the SAT status shows the cancellation
   pending, so the caller resolves it by querying the status.
6. **Given** a cancellation request with reason 01, **When** the caller builds it without a
   substitute UUID, **Then** it is refused; **Given** reason 02, 03 or 04 with a substitute UUID,
   **Then** it is refused; a reason outside 01–04 is refused. Each refusal names the field.
7. **Given** a status query whose RFCs or total do not match the stamped document, **When** the
   caller queries it, **Then** the state is not found, as the SAT answers.

---

### User Story 3 - Share the simulated PAC's state (Priority: P3)

A caller that runs several processes (for example a web server and a background worker) gives
the simulated PAC a state store of its own, so every process sees the same stamps, cancellations
and configured outcomes. Without one, the simulated PAC keeps its state in memory.

**Why this priority**: single-process tests and development work with the in-memory default;
sharing only matters once a caller spreads stamping and cancellation across processes.

**Independent Test**: create two simulated PACs over one store; stamp and configure outcomes
through one and confirm the other sees the stamp, honours the configured outcome, and reports the
same SAT status.

**Acceptance Scenarios**:

1. **Given** two simulated PACs sharing one store, **When** one stamps a document, **Then** the
   other finds the stamp and stamping the same document through it afterwards returns the same
   stamp.
2. **Given** two simulated PACs sharing one store, **When** an outcome is configured through one,
   **Then** the next matching call through the other gets that outcome.
3. **Given** a simulated PAC created without a store, **When** it is used, **Then** it works
   entirely in memory and shares nothing with any other instance.

---

### Edge Cases

- Stamping input that is not well-formed XML, not a CFDI 4.0 document, or not sealed (no seal):
  the simulated PAC rejects it with the PAC-rejected error, its own code and a message, and the
  error never contains the input.
- Stamping a document that already carries a TimbreFiscalDigital: it is the same sealed document,
  so if this PAC has a record of it the existing stamp comes back (unless an outcome configured
  for it applies first); a TFD this PAC has no record of, even one another simulated PAC with a
  separate store made, is rejected.
- A configured outcome applies to the next matching call only; the call after it behaves as the
  document's current status dictates (a document configured not cancellable stays not
  cancellable).
  A configured rejection without a code or message uses the simulator's default ones.
- Requesting the cancellation of a document that is already cancelled, or already pending: the
  answer reflects the current state and nothing changes.
- Acting as the recipient when no cancellation is pending: refused with an error that says so.
- Requesting the cancellation of, or querying, a UUID this simulated PAC never stamped: treated
  as a valid document stamped elsewhere (FR-018), so documents stamped before a caller switched to
  the simulator can still be cancelled.
- Two simulated PACs sharing a store stamp the same new document at the same instant: both may
  stamp it, because separate instances do not lock each other. A caller that needs the guarantee
  within one process shares one instance; across processes the simulator is for development and
  tests, where this does not arise.
- Input that is not bytes, or a document with an empty seal: rejected like other invalid input.
- Input that is a sealed CFDI 4.0 the library cannot read (a value of the wrong type, a missing
  issuer, recipient or total): rejected like other invalid input, never another error.
- Errors, the cancellation request, the CSD and the stamp are printed or logged: none shows the
  password, the key, the certificate's bytes or a raw PAC payload.

## Requirements *(mandatory)*

### Functional Requirements

**The interface**

- **FR-001**: The library MUST define one PAC interface with four operations: stamp a sealed
  document, find the stamp of a sealed document, request a cancellation, and query the SAT status.
  Every operation is asynchronous.
- **FR-002**: Stamping MUST return a stamp holding the stamped document and its
  TimbreFiscalDigital 1.1 values: UUID in upper case, stamp date as naive Mexico City time, SAT
  seal, SAT certificate number and provider RFC.
- **FR-003**: Finding a stamp MUST return the stamp of that sealed document if the PAC already
  stamped it, or nothing, and MUST never stamp; input that is not a sealed CFDI 4.0 is rejected
  with the PAC-rejected error, as stamping rejects it.
- **FR-004**: Requesting a cancellation MUST answer accepted (cancelled at once), pending (the SAT
  waits for the recipient) or not cancellable.
- **FR-005**: Querying the status MUST take the issuer RFC, recipient RFC, UUID and total, and
  answer the state (valid, cancelled, not found), the cancellability (without acceptance, with
  acceptance, not cancellable) and the cancellation status (none, requested, pending, accepted,
  rejected, expired).
- **FR-006**: The interface's errors MUST share one base: PAC rejected (carrying the PAC's code
  and message), PAC unavailable (the request did not reach the PAC; retrying is safe) and PAC
  timeout (the outcome is unknown). An operation MUST NOT let any other error escape, and a
  caller MUST never need to read error text to decide what happened.
- **FR-007**: The stamp, the cancellation request, the SAT status and the CSD MUST be immutable
  typed values.
- **FR-008**: A cancellation request MUST carry the issuer and recipient RFCs, the UUID, the
  total, the SAT reason (01, 02, 03 or 04), the substitute UUID, and the issuer's CSD
  (certificate, encrypted private key and password). It MUST refuse to be created with reason 01
  and no substitute UUID, with reason 02–04 and a substitute UUID, with any other reason, or with
  a UUID or substitute UUID that is not a well-formed UUID, naming the field at fault.
- **FR-009**: Credentials, CSD material and raw PAC payloads MUST NOT appear in any error, log or
  printed representation; the CSD's representation MUST NOT show the key, the password or the
  certificate's content.
- **FR-010**: The interface MUST be the library's own and MUST NOT depend on any caller's code.

**The simulated PAC**

- **FR-011**: The library MUST provide a simulated PAC that implements the interface without any
  network access.
- **FR-012**: The simulated PAC MUST stamp with a fresh UUID, the current Mexico City time and the
  fixed provider RFC `SIM010101SI0`. The TimbreFiscalDigital it writes MUST be valid against the
  SAT's TimbreFiscalDigital 1.1 schema, carry the document's seal, and give the same original
  string under the SAT's `cadenaoriginal_TFD_1_1.xslt` as its values do.
- **FR-013**: The simulated PAC MUST identify a sealed document by its seal: stamping the same
  sealed document again MUST return the same stamp, and finding its stamp MUST return it. Calls
  through one simulated PAC never stamp a document twice, even concurrently; separate simulated
  PACs sharing a store guarantee this only for calls that do not overlap (Edge Cases).
- **FR-014**: The simulated PAC MUST reject, with the PAC-rejected error, input that is not a
  well-formed, sealed CFDI 4.0 document the library can read with an issuer RFC, a recipient RFC
  and a total.
- **FR-015**: For a given sealed document, a caller MUST be able to configure the outcome of the
  next stamp: stamped, rejected (with a given code and message), unavailable, timeout after
  stamping, or timeout without stamping.
- **FR-016**: For a given UUID, a caller MUST be able to configure the outcome of the next
  cancellation request: accepted at once, pending, not cancellable, rejected (with a given code and
  message), unavailable, or timeout (the SAT received it, so it is left pending). Without a
  configured outcome, the answer follows the cancellability its status reports: a document stamped
  less than 24 hours ago is cancelled at once and one 24 hours old or older is left pending, and
  once a cancellation has gone pending the document needs the recipient's acceptance from then on. A
  document answered not cancellable stays not cancellable. On a document already pending, cancelled
  or answered not cancellable, a configured accepted, pending or not-cancellable outcome is used up
  without effect, and a configured error outcome raises without changing anything. A request whose
  RFCs or total do not match (FR-018) is rejected before any configured outcome, which then stays
  for the next request.
- **FR-017**: The simulated PAC MUST let a caller act as the recipient of a pending cancellation:
  accept it (cancelled, accepted), reject it (valid, rejected) or let its time limit pass
  (cancelled, expired), each by an explicit call; the clock never expires a cancellation by
  itself. Doing so when no cancellation is pending MUST be refused.
- **FR-018**: A status query whose issuer RFC, recipient RFC or total does not match the document
  the simulated PAC stamped MUST report the state not found; a cancellation request with the same
  mismatch MUST be rejected. A UUID the simulated PAC never stamped MUST be treated as a valid
  document stamped elsewhere more than 24 hours ago, without checking its RFCs or total.
- **FR-019**: The simulated PAC's state (stamps, cancellations, configured outcomes) MUST live in a
  store the caller can supply, so several instances, in one process or several, can share it;
  without one it MUST keep the state in memory.
- **FR-020**: The simulated PAC MUST NOT verify the document's own seal, the issuer's CSD in a
  cancellation request, or the substitute UUID's existence, and the SAT seal it writes is not
  verifiable; it does not imitate the SAT's validation of the document beyond FR-014.

**Testing**

- **FR-021**: Tests MUST cover every path of the simulated PAC listed in FR-012 to FR-019 and
  the validation of cancellation requests in FR-008, and MUST run offline.

### Key Entities

- **PAC interface**: the four asynchronous operations every PAC client offers; the simulated PAC
  is its first implementation and the Multifacturas client (#3) the second.
- **Stamp**: the stamped document and its TimbreFiscalDigital 1.1 values (UUID, stamp date, SAT
  seal, SAT certificate number, provider RFC).
- **Cancellation request**: issuer and recipient RFCs, UUID, total, reason, substitute UUID and the
  issuer's CSD; valid by construction.
- **Cancellation answer**: accepted, pending or not cancellable.
- **SAT status**: state, cancellability and cancellation status of one UUID.
- **CSD (for the PAC)**: the issuer's certificate, encrypted private key and password exactly as
  the caller holds them, because a PAC needs them to sign the cancellation; never printed. Named
  `CsdCredentials` in the contract, to keep it apart from the CSD the library seals with.
- **Recipient**: the party the document is issued to; the contract calls it the receiver
  (`answer_as_receiver`), as mbe-api does.
- **PAC errors**: one base with three kinds: rejected (code, message), unavailable, timeout.
- **Simulator store**: where the simulated PAC keeps stamps, cancellations and configured
  outcomes; in memory unless the caller supplies its own.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A caller's stamping and cancellation code written against the interface alone (its
  type, values and errors) runs unchanged against the simulated PAC; #3 checks the same for
  Multifacturas.
- **SC-002**: Every stamp the simulated PAC returns is read back by the library's own reader with
  the same UUID, date, seals, certificate number and provider RFC, is valid against the SAT's
  TimbreFiscalDigital 1.1 schema, and its TFD original string matches the SAT's stylesheet, in
  100% of the tests.
- **SC-003**: Each of the 5 stamping outcomes and the 9 cancellation outcomes (accepted, pending
  then accepted, pending then rejected, pending then expired, not cancellable, rejected,
  unavailable, timeout, and the default by age) is reached, by configuration or by the clock, in at
  least one test, and each ends in the expected answer or error type and SAT status.
- **SC-004**: In 100% of the tests that stamp a document twice, stamp it concurrently through one
  simulated PAC, or look a stamp up after a timeout, every call returns the identical stamp (same
  UUID), so no second stamp is ever made.
- **SC-005**: No error, printed value or log line produced in the test suite contains the CSD's
  password, key or certificate bytes, or a document's XML.
- **SC-006**: The whole test suite runs offline.

## Assumptions

- The sealed document handed to the PAC is produced by the library (#1) or is equivalent; this
  feature does not build or seal documents.
- The simulated PAC's SAT seal is random Base64 of a real seal's length and its SAT certificate
  number is a fixed 20-digit value; neither verifies against a SAT certificate, which no simulator
  can have.
- The 24-hour rule for cancelling without acceptance is the simulator's simplification of the
  SAT's rules, as mbe-api's simulator applies it; a real PAC reports what the SAT decides.
- "Requested" is a cancellation status a real PAC can report while the SAT has not yet processed
  a request; the simulated PAC never reports it.
- "Cancelled at once" is reported as cancellation status accepted, as mbe-api does.
- Tests control the simulated PAC's clock so the 24-hour rule and stamp dates are deterministic.
- The CSD a cancellation request carries is separate from the CSD the library uses to seal
  (which keeps neither the password nor the original key bytes); planning names it
  `CsdCredentials` and keeps the two independent (research.md R5).
- Clarified (2026-11-18): the provider RFC is `SIM010101SI0`, not the `SIM010101SIM` of the
  description and of mbe-api's simulator, because the SAT's TimbreFiscalDigital 1.1 schema requires
  `RfcProvCertif` to end in a digit or `A`; the stamp must stay valid against it (FR-012).
- Clarified (2026-11-18): the whole PAC interface (its values, enums and errors) and the PAC
  clients are exported from the library's PAC namespace, not from its root namespace
  (constitution v1.0.2, principle V).
- Clarified: a UUID the simulator never stamped is a valid document stamped elsewhere (FR-018),
  matching mbe-api's simulator.
- Out of scope: real PAC clients (#3), building and sealing CFDIs (#1), retention CFDIs.
