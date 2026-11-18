# Feature Specification: Generic SAT CFDI Status Client

**Feature Branch**: `004-sat-status-client`

**Created**: 2026-11-18

**Status**: Draft

**Input**: User description: "Generic SAT CFDI status client (mictlanix/cfdi#6, part of mictlanix/mbe-roadmap#160). The SAT's public status service (ConsultaCFDIService) tells anyone the state of a CFDI, whichever PAC stamped it, with no credentials. The library offers it as its own async client, independent of any PAC, so a caller can learn whether a document is valid or cancelled, whether it can be cancelled and with what acceptance, and how a pending cancellation ends."

## User Scenarios & Testing *(mandatory)*

The user of this feature is a developer whose application issues or receives Mexican electronic
invoices. "Caller" below means that application. The SAT's public status service answers for any
CFDI, whichever PAC stamped it, and needs no credentials. Feature 003 (mictlanix/cfdi#3) built a
first version inside the Multifacturas client and took it out before merging; the request and the
answer mapping it verified on 2026-11-18 are recorded in mictlanix/cfdi#6, together with the
design decision this spec follows (a client of its own, outside the PAC interface).

### User Story 1 - Ask the SAT the status of a CFDI (Priority: P1)

A caller creates the status client, with the SAT's endpoint by default and its own timeouts, and
asks for the status of a document by issuer RFC, recipient RFC, UUID and total. It receives, as
immutable typed values, the document's state (valid, cancelled, not found), whether it can be
cancelled (without acceptance, with acceptance, not cancellable) and the status of its
cancellation (none, pending, accepted, rejected, expired). It needs no PAC and no credentials, so
it serves documents the caller issued and documents it received alike.

**Why this priority**: it is the whole feature; without it a caller cannot learn whether a
cancellation finished, nor check a supplier's invoice.

**Independent Test**: offline, replay a recorded or synthetic SAT answer for every row of the
mapping and check the values returned; opt-in, ask the real service about a UUID it does not know
and receive not found.

**Acceptance Scenarios**:

1. **Given** a document the SAT knows with those RFCs and total, **When** the caller asks for its
   status, **Then** it receives the state, cancellability and cancellation status the SAT reports,
   mapped as the mapping table prescribes (FR-005).
2. **Given** a UUID the SAT does not know, or RFCs or a total that do not match it, **When** the
   caller asks, **Then** the state is not found, the document is not cancellable and there is no
   cancellation.
3. **Given** a UUID that is not well formed, **When** the caller asks, **Then** it receives not
   found without any request being sent.
4. **Given** the SAT answers with a value outside the mapping, **When** the caller asks, **Then** a
   rejected error with the code `SAT-ANSWER` is raised; the client never guesses.
5. **Given** the service cannot be reached (name resolution, connection or TLS failure before the
   request is sent), **When** the caller asks, **Then** the unavailable error is raised; given the
   request was sent and no usable answer arrives in time, the timeout error is raised.
6. **Given** the caller passes an endpoint that is not HTTPS or a timeout that is not positive,
   **When** it creates the client, **Then** it is refused.

---

### User Story 2 - Follow a cancellation with the simulator (Priority: P2)

A caller that stamps and cancels with the simulated PAC (spec 002) creates a simulated status
client from that simulated PAC and follows a cancellation the way it would with the real service:
valid and cancellable without acceptance right after stamping, pending once a cancellation needs
the recipient, and then accepted, rejected or expired as the simulated recipient answers. Its
tests and development run offline, with the same values and errors as the real client.

**Why this priority**: callers developed this flow against the simulator before feature 003
removed it from the PAC interface; it depends on the values of User Story 1.

**Independent Test**: stamp with the simulated PAC, cancel, answer as the recipient, and check the
simulated status after each step.

**Acceptance Scenarios**:

1. **Given** a document the simulated PAC stamped less than 24 hours ago, **When** the caller asks,
   **Then** it is valid, cancellable without acceptance, with no cancellation; after 24 hours it is
   cancellable with acceptance.
2. **Given** a cancellation the simulated PAC accepted, **When** the caller asks, **Then** the
   document is cancelled and its cancellation accepted.
3. **Given** a pending cancellation, **When** the simulated recipient accepts, rejects or lets it
   expire, **Then** the status shows cancelled and accepted, valid and rejected, or cancelled and
   expired.
4. **Given** a document the simulated PAC answered as not cancellable, **When** the caller asks,
   **Then** it is not cancellable.
5. **Given** RFCs or a total that do not match a document the simulated PAC stamped, or a UUID
   that is not well formed, **When** the caller asks, **Then** the state is not found; a UUID the
   simulated PAC never stamped is a valid document stamped elsewhere, as spec 002 decided.

### Edge Cases

- The answer is not a SOAP envelope (an HTML error page, a proxy's page, an empty body) or the
  HTTP status is not 200 without a SOAP Fault: the request was sent and no usable answer came, so
  it is a timeout.
- The service answers a SOAP Fault: a rejected error with a fixed code, without the fault's text.
- `EstatusCancelacion` empty while `Estado` is `Cancelado` (a cancellation without acceptance the
  SAT reports without status): the cancellation status is none, as the mapping says; no guessing.
- A total with any number of decimals: the expression carries it as the verification QR does
  (spec 001), which the SAT accepts with any number of trailing zeros.
- A lower-case UUID: sent as given in the expression; the SAT's answer decides.
- Documents stamped in a PAC's test mode never reach the SAT and are always not found.

## Requirements *(mandatory)*

### Functional Requirements

**The client**

- **FR-001**: The library MUST provide an asynchronous SAT status client with one operation that
  takes issuer RFC, recipient RFC, UUID and total and returns the document's SAT status: state,
  cancellability and cancellation status, as one immutable value.
- **FR-002**: The values MUST be the ones that left the PAC interface in feature 003: the status
  value and its three enumerations (state: valid, cancelled, not found; cancellability: without
  acceptance, with acceptance, not cancellable; cancellation status: none, pending, accepted,
  rejected, expired), restored with the same names and string values. Spec 002's cancellation
  status `requested` is not restored: no answer of the SAT and no state of the simulator produces
  it.
- **FR-003**: The client MUST take its endpoint (the SAT's public status service by default) and
  its connect and read timeouts from the caller, refuse an endpoint that is not HTTPS and a timeout
  that is not positive, verify the server's certificate, and read nothing from the environment.
- **FR-004**: The request MUST carry the expression `?re=…&rr=…&tt=…&id=…` built from the
  arguments, with the total formatted as the verification QR formats it (spec 001), XML-escaped.
  A UUID that is not well formed MUST answer not found without a request.

**The answer**

- **FR-005**: The SAT's answer MUST be mapped exactly as follows, and any other value MUST be a
  rejected error with the code `SAT-ANSWER`:

  | SAT field | Value | Maps to |
  |-----------|-------|---------|
  | `CodigoEstatus` starting `N`, or `Estado` `No Encontrado` | — | not found / not cancellable / none |
  | `Estado` | `Vigente` / `Cancelado` | valid / cancelled |
  | `EsCancelable` | `Cancelable sin aceptación` / `Cancelable con aceptación` / `No cancelable` | without acceptance / with acceptance / not cancellable |
  | `EstatusCancelacion` | empty / `En proceso` / `Plazo vencido` / `Cancelado con aceptación` / `Cancelado sin aceptación` / `Solicitud rechazada` | none / pending / expired / accepted / accepted / rejected |

**Errors**

- **FR-006**: The client MUST raise only its own typed errors, in the style of the PAC errors
  (spec 002), all under one SAT error base that derives from the library's base error: an
  unavailable error when the request was not sent (name resolution, connection, TLS, an endpoint
  that cannot be addressed), a timeout error when it was sent and no usable answer arrived, and a
  rejected error with a code and message for an answer it cannot read (`SAT-ANSWER`) or a SOAP
  Fault (`SOAP-FAULT`). No other error type escapes, each is raised without its cause, and no error
  carries the raw answer. *(Clarified with
  the user, 2026-11-18: the SAT client's own errors, exported from `mictlanix.cfdi.sat`, not the
  PAC errors.)*

**The simulator**

- **FR-007**: The library MUST provide a simulated status client, created from a simulated PAC,
  that answers from that simulated PAC's state with the same values and errors as the real client:
  the 24-hour rule for cancellability, pending cancellations, the recipient's answers, not
  cancellable, mismatching RFCs or total and malformed UUIDs as not found, and a UUID the simulated
  PAC never stamped as a valid document stamped elsewhere (spec 002).
- **FR-008**: A simulated status client and its simulated PAC MUST see the same state at all times:
  a status asked after any stamping, cancellation or recipient answer reflects it.

**Placement**

- **FR-009**: The status client protocol, its values and enumerations, its errors, the real
  client, its settings and the simulated client MUST be exported from `mictlanix.cfdi.sat` and only
  from there (constitution principle V, as amended to v1.1.2 to list the errors). Nothing in
  `mictlanix.cfdi.pac` or `mictlanix.cfdi` changes its exports.

**Tests**

- **FR-010**: The offline tests MUST replay a recorded or synthetic SAT answer for every row of the
  mapping, the `SAT-ANSWER` rejection and each transport outcome. Recorded answers MUST be scrubbed
  of real RFCs before they are committed. A live test against the SAT MUST run only when an
  environment variable enables it, and be skipped otherwise.
- **FR-011**: No new dependency; the client MUST reuse the HTTP and SOAP code feature 003 added.

### Key Entities

- **SAT status**: a document's state, cancellability and cancellation status at the SAT.
- **Status client**: anything that answers the status of a UUID given its RFCs and total; a real
  one asks the SAT, a simulated one reads a simulated PAC's state.
- **Status settings**: the endpoint and timeouts of the real client.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Every row of the mapping table, and every value outside it, is covered by an offline
  test that checks the values or the error returned.
- **SC-002**: A caller's code that follows a cancellation against the simulated status client runs
  against the real client after changing only how the client is created.
- **SC-003**: The status of a document the SAT knows is answered in one request.
- **SC-004**: No error, printed value or log contains the raw answer of the service.
- **SC-005**: The test suite runs offline; the live test runs only when its variable is set.
- **SC-006**: Every request uses HTTPS with certificate verification.

## Assumptions

- Prerequisite: a PATCH amendment of constitution principle V (v1.1.1 → v1.1.2) adds errors to the
  SAT status surface ("its values, enums and errors"), committed on its own before planning
  (user's decision, 2026-11-18).
- The request, the expression without `fe`, and the mapping are the ones verified on 2026-11-18 and
  recorded in mictlanix/cfdi#6: the service answers the same with and without `fe`, and spec 001
  verified `tt` with any number of trailing zeros.
- The SAT's status service needs no credentials and is the same for every PAC.
- Documents stamped in a PAC's test mode never reach the SAT, so the recorded answer is not found;
  the other states come from synthetic answers derived from a recorded envelope.
- Default timeouts: 10 seconds to connect and 60 seconds to read, as the Multifacturas client.
- The simulated status client is a separate object created from the simulated PAC rather than the
  simulated PAC itself, because principle V exports every SAT status client from
  `mictlanix.cfdi.sat` and the simulated PAC from `mictlanix.cfdi.pac`. This refines the
  2026-11-18 decision on mictlanix/cfdi#6, which had the simulated PAC implement both interfaces.
- The PAC clients' use of the status client (for example, to tell accepted from pending after a
  SAT 201) is feature 003's concern and out of scope here, as is the bulk download web service
  (mictlanix/cfdi#7).
