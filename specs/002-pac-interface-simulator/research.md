# Research: Generic PAC Client Interface and a Simulated PAC

All Technical Context items are resolved; there were no NEEDS CLARIFICATION markers left after
the spec's clarification (a UUID the simulator never stamped is a valid document stamped
elsewhere). Prior art: mbe-api's `app/services/pac/provider.py` and `simulated.py`, which define
the same interface inside the application and which this library's simulator is meant to
replace. Where this design differs from mbe-api, the reason is given.

## R1. Where the code lives

- **Decision**: subpackage `mictlanix.cfdi.pac` with private `_interface.py` and `_errors.py` and
  one public module per client: `simulated.py` now, `multifacturas.py` in #3. Everything public is
  exported from `mictlanix.cfdi.pac`; `mictlanix.cfdi`'s exports do not change.
- **Rationale**: the constitution (V, VI) requires PAC clients to be exported from
  `mictlanix.cfdi.pac`, each in its own module, behind one interface. Since v1.0.2 the
  constitution says the same for the PAC interface's protocol, values, enums and errors (the
  user's decision of 2026-11-18, made a principle by that amendment).
- **Alternatives considered**: exporting the interface from `mictlanix.cfdi` and the clients from
  `mictlanix.cfdi.pac` (the literal reading of v1.0.1's principle V; splits one concern across
  two namespaces).

## R2. The interface is a Protocol

- **Decision**: `class PacClient(Protocol)` with four `async def` methods: `stamp`, `find_stamp`,
  `request_cancellation`, `query_status`.
- **Rationale**: structural typing lets a caller's own fake satisfy the interface without
  inheriting; mypy checks conformance through a private function in `simulated.py` that
  returns a `SimulatedPac` as a `PacClient` and an `InMemoryStore` as a `SimulatorStore`, so
  `mypy src` verifies it (the tests are not type-checked). Same shape as mbe-api's
  `PacProvider`.
- **Alternatives considered**: an abstract base class (forces inheritance for no gain).

## R3. XML is bytes

- **Decision**: `stamp` and `find_stamp` take the sealed XML as `bytes`; `Stamp.xml` is `bytes`.
- **Rationale**: `seal` returns `bytes` and `read`/`tfd_original_string` take `bytes`, so a caller
  pipes the library's output straight in and the stamp straight back. Encoding stays explicit.
- **Alternatives considered**: `str`, as mbe-api uses (mbe encodes once; the library stays
  consistent with #1).

## R4. The stamp reuses the library's TFD model

- **Decision**: `Stamp(xml: bytes, timbre: tfd11.TimbreFiscalDigital)`. The TFD values (UUID,
  `FechaTimbrado`, `SelloSAT`, `NoCertificadoSAT`, `RfcProvCertif`, plus `SelloCFD`) are the
  generated model's, with SAT names. A stamp is built from stamped XML by one private helper that
  reads it with the library's reader and upper-cases the UUID; the Multifacturas client reuses it.
- **Rationale**: one representation of a TFD in the library; nothing duplicated or renamed.
- **Alternatives considered**: a flat stamp with English field names, as mbe-api has (duplicates
  the TFD model and breaks the SAT-names rule).

## R5. The cancellation CSD is a separate value

- **Decision**: `CsdCredentials(certificate: bytes, private_key: bytes, password: str)`, frozen,
  with a `repr` showing only the certificate's size and `<hidden>` for the key and password. Not
  validated on construction.
- **Rationale**: a real PAC needs the certificate, the encrypted key and its password to sign the
  cancellation, and the sealing `CSD` deliberately keeps neither the password nor the key bytes
  (#1's contract). Field names match `CSD.load`'s parameters, so a caller holding the three values
  builds both from the same variables. Validating would duplicate `CSD.load`; a real PAC rejects
  bad credentials with `PacRejected`.
- **Alternatives considered**: making `CSD` keep the password and raw key (weakens #1's secret
  handling); naming it `Csd` (too close to `CSD`).

## R6. Request validation reuses `ValidationError`

- **Decision**: `CancellationRequest.__post_init__` raises the library's `ValidationError` with
  one `Violation` per problem, `node='CancellationRequest'`, `attribute` naming the field, and the
  rules `cancellation-reason` (not 01–04), `cancellation-substitute-required` (01 without
  `substitute_uuid`), `cancellation-substitute-forbidden` (02–04 with it) and `uuid-format`
  (`uuid` or `substitute_uuid` not a well-formed UUID, any case). The request keeps its values as
  given.
- **Rationale**: the library already has "violations name node, attribute and rule; callers
  branch on rule". No new error type.
- **Alternatives considered**: `ValueError` (callers would parse text); a new exception class
  (one more public type for the same idea).

## R7. Errors

- **Decision**: `PacError(CfdiError)`; `PacRejected(code: str, message: str)` with `str(error)`
  equal to `'{code}: {message}'`; `PacUnavailable` and `PacTimeout` take no arguments and have
  fixed messages. A simulator never chains a caller's data into them.
- **Rationale**: one base for "anything a PAC raised", and still a `CfdiError` so a caller
  catching the library's base catches these too. The constitution's three kinds, nothing more.
- **Alternatives considered**: a separate base outside `CfdiError` (two roots for one library).

## R8. Status vocabulary

- **Decision**: `StrEnum`s `CancellationAnswer` (`accepted`, `pending`, `not_cancellable`),
  `SatState` (`valid`, `cancelled`, `not_found`), `Cancellability` (`without_acceptance`,
  `with_acceptance`, `not_cancellable`) and `CancellationStatus` (`none`, `requested`, `pending`,
  `accepted`, `rejected`, `expired`), with `SatStatus(state, cancellability, cancellation)`. A
  document cancelled at once reports cancellation `accepted`, as mbe-api does; `expired` is the
  SAT's "plazo vencido" and leaves the document cancelled; `requested` is never produced by the
  simulator.
- **Rationale**: the values mbe-api already stores, so it can switch without a migration;
  `StrEnum` members compare equal to those strings.
- **Alternatives considered**: `Literal` strings (no single place to list the values).

## R9. The simulator's store

- **Decision**: `SimulatorStore(Protocol)` with `async get(key: str) -> str | None` and
  `async set(key: str, value: str) -> None`; `InMemoryStore` implements it with a dict. The
  simulator owns the keys and the JSON values: `seal:<sha256 hex of the seal>` for a sealed document
  (its next stamp outcome and its stamped XML) and `uuid:<UUID upper case>` for a stamped UUID
  (RFCs, total, stamp date, state, cancellability, cancellation status, next cancellation outcome).
  Exceptions from the store become `PacUnavailable`.
- **Rationale**: strings are what any shared medium stores (a database column, Redis), so a caller
  shares the simulator across processes with a dozen lines and the record format stays private.
  An `asyncio.Lock` per `SimulatedPac` serializes that instance's operations, so concurrent calls
  through one instance never stamp a document twice. Separate instances, in one process or
  several, do not lock each other: two of them stamping the same new document at the same instant
  could both stamp it. Development and tests do not need more (documented in the contract);
  a caller sharing one simulator within a process shares the instance.
- **Alternatives considered**: public record dataclasses (more API, ties callers to the format);
  a transactional store protocol (complexity no test needs).

## R10. Identity and configuration

- **Decision**: a sealed document is identified by its `Sello`. `configure_stamp(sealed_xml,
  outcome, *, code=None, message=None)` sets the next stamp's outcome for that document;
  `configure_cancellation(uuid, outcome, *, code=None, message=None)` sets the next cancellation's
  outcome for that UUID; each applies once and is then cleared, as mbe-api's `set_next` does. A
  rejection without code or message uses `CFDI40999` / `Rechazo simulado`.
- **Rationale**: the seal is unique per sealed document and present before stamping; mbe-api keys
  by issuer, series and folio, which are optional in CFDI 4.0 and application-specific.
- **Alternatives considered**: keying by the XML's hash (whitespace changes would make two
  identities for one document).

## R11. Simulated stamping

- **Decision**: `stamp`, `find_stamp` and `configure_stamp` check their input in this order, each
  failure raising `PacRejected` `from None` (so no parser message, which can quote the input,
  travels in `__context__`):
  1. not `bytes`, not well-formed, or not a CFDI 4.0 `Comprobante` → `301`;
  2. no `Sello`, or a blank one → `302`;
  3. the library's `read` cannot turn it into models (`ParseError`, `NotCfdi40Error`), or it has
     no `Total` → `301` (a document edited after sealing until unreadable is rejected even if its
     seal was stamped before);
  4. the lookup by seal decides whether this PAC knows the document;
  5. a document this PAC has no record of that already carries a TFD → `307` (`find_stamp`
     returns `None` for it instead).
  Invalid input leaves any configured outcome for the next call. For valid input, `stamp` then
  applies the configured outcome, if any (data-model.md section 5); with none, or `STAMPED`, it
  returns the earlier stamp of a known document or makes a new one. A new stamp gets `uuid4()`
  upper case, `FechaTimbrado` from the clock without microseconds, `RfcProvCertif='SIM010101SI0'`,
  `SelloCFD` = the document's `Sello`, `NoCertificadoSAT='00001000000000000000'` and `SelloSAT` =
  Base64 of 256 random bytes. The TFD element is produced by the library's serializer from a
  `tfd11.TimbreFiscalDigital` and appended to `cfdi:Complemento`, which is created right before
  `cfdi:Addenda` (or last) when absent; the rest of the caller's document keeps its nodes and its
  original string (lxml re-serializes the declaration and quoting). The `uuid:` record is written
  before the `seal:` record, so a store failure between the two leaves only a record no caller
  was ever given (the stamp was not returned), and stamping again makes a fresh stamp.
- **Rationale**: XSD validity by construction, and the TFD original string under the SAT's XSLT
  follows from the values (spec FR-012, SC-002). Same constants as mbe-api except the provider RFC:
  mbe-api's `SIM010101SIM` fails the TFD schema's `t_RFC_PM` pattern (the last character must be
  a digit or `A`), so the library uses `SIM010101SI0` (user decision, 2026-11-18); mbe-api changes
  its constant when it adopts the library.
- **Alternatives considered**: rebuilding the whole document from models (would rewrite the
  caller's XML and its addenda for no reason).

## R12. Clock and cancellation rules

- **Decision**: `SimulatedPac(store=None, *, clock=None)`; `clock` returns naive Mexico City time
  and defaults to the current time at the fixed UTC-6 offset #1 already uses (moved to a shared
  private module). Without a configured outcome, a cancellation is accepted when the stamp is
  under 24 hours old by the clock, otherwise pending; a UUID the simulator never stamped is valid,
  with acceptance, and its RFCs and total are not checked. A cancellation that times out is left
  pending. Once a cancellation goes pending (by age, configured or after a timeout) the
  cancellability is `with_acceptance` regardless of the stamp's age. Without a configured
  outcome the answer follows that cancellability (without acceptance → accepted, with
  acceptance → pending, not cancellable → not cancellable), so the 24-hour rule only decides it
  until a cancellation has gone pending. A repeated request for a document already pending or
  cancelled answers its current state without changes; on such a document a configured
  accepted, pending or not-cancellable outcome is used up without effect, while a configured
  rejected, unavailable or timeout outcome raises its error and changes nothing (data-model.md
  section 5).
  RFCs compare exactly; totals compare as decimals (`116.0 == 116.00`, as the SAT's service does).
  Acting as the receiver with nothing pending raises `PacRejected('SIM01', ...)`.
- **Rationale**: deterministic tests (spec assumption), mbe-api's rules, and the SAT behaviour
  observed live while verifying the QR's `tt` (numeric comparison of the total).
- **Alternatives considered**: a real SAT rule set (amounts, document types, relations): out of
  scope; a real PAC reports what the SAT decides.
