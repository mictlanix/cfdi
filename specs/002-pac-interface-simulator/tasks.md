---

description: "Task list for the generic PAC client interface and a simulated PAC"
---

# Tasks: Generic PAC Client Interface and a Simulated PAC

**Input**: Design documents from `/specs/002-pac-interface-simulator/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/public-api.md,
quickstart.md

**Tests**: mandatory. The constitution (principle II) requires tests before code, and the spec
(FR-021) requires tests for every simulator path and for the cancellation-request rules. Every
behaviour is first asserted by a task marked "failing", which is done when its new tests fail for
the expected reason and everything else still passes.

**Organization**: Tasks are grouped by user story to enable independent implementation and
testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- Exact file paths are in the descriptions

## Conventions for every task

- The subpackage root is `src/mictlanix/cfdi/pac/`; tests live in `tests/pac/`.
- A non-test task is done when the tests it names pass, every other test passes except those a
  later task is listed to make pass, and `uv run ruff check`, `uv run ruff format --check` and
  `uv run mypy src` pass. Tests still allowed to fail: `tests/pac/test_public_api.py` until T015
  (the store names arrive last); a story's test file until its implementation task.
- Public names are exported from `src/mictlanix/cfdi/pac/__init__.py` exactly as listed in
  `contracts/public-api.md`; `src/mictlanix/cfdi/__init__.py` does not change (constitution
  v1.0.2, principle V).
- No test uses the network. Simulator tests pass a `clock` they control; only
  `tests/test_mexico.py` and T010's default-clock test read the real time.
- Every stamp the simulator returns in any test (T010, T012, T014) goes through
  `assert_valid_stamp` (SC-002).
- Sealed documents come from `make_sealed()`.
- Code and docstrings name no application (no mention of mbe-api); the design notes do.
- No error, `repr` or `str` may contain a password, key or certificate bytes, or a document's XML.
- SAT names keep their spelling (`TimbreFiscalDigital`, `UUID`, `FechaTimbrado`, `Sello`).

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: the subpackage skeleton, the test fixtures and the shared Mexico City time

- [ ] T001 Create `src/mictlanix/cfdi/pac/__init__.py` (docstring, empty `__all__`), `tests/pac/__init__.py` and `tests/pac/conftest.py` with fixtures: `make_sealed` (a factory; each call returns a new sealed income document as bytes: `make_invoice(totals=False, Folio=<next number>)`, sealed with the `csd` fixture of `tests/conftest.py`, optionally with an `Addenda`); `clock` (an instance of a `Clock` class whose attribute `now` holds a naive `datetime`, default `datetime(2026, 11, 17, 12, 0, 0)`, returned by each call, with `advance(timedelta)`); `assert_valid_stamp(stamp, sealed, clock_now=None)` (a helper asserting the SC-002 checks on any stamp: `RfcProvCertif == 'SIM010101SI0'`, `NoCertificadoSAT == '00001000000000000000'`, `SelloCFD` equals the sealed document's `Sello`, `FechaTimbrado == clock_now` when given, the values `read(stamp.xml)` gives equal those, the TFD element validates against the vendored `TimbreFiscalDigitalv11.xsd` through `mictlanix.cfdi._sat`, `tfd_original_string(stamp.xml) == f'||1.1|{UUID}|{FechaTimbrado:%Y-%m-%dT%H:%M:%S}|SIM010101SI0|{SelloCFD}|00001000000000000000||'`, and `original_string(stamp.xml) == original_string(sealed)`); and `credentials` (a `CsdCredentials` from `tests/fixtures/csd/` and the published test password, importing `CsdCredentials` inside the fixture body so it is usable once T009 lands). Supports FR-021 and SC-006
- [ ] T002 Write `tests/test_mexico.py` (failing): `mictlanix.cfdi._mexico.now()` is naive, has `microsecond == 0`, and is within 2 seconds of `datetime.now(UTC) - timedelta(hours=6)` without its time zone; `_mexico.MEXICO_CITY.utcoffset(None) == timedelta(hours=-6)`. Supports FR-012 (the simulator's default clock)
- [ ] T003 Move the fixed offset from `src/mictlanix/cfdi/_csd.py` to a new `src/mictlanix/cfdi/_mexico.py` exporting `MEXICO_CITY = timezone(timedelta(hours=-6))` (with the existing comment) and `now() -> datetime`; `_csd.py` imports it. Make T002 pass; `tests/test_csd.py` and `tests/test_seal.py` pass unchanged

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: the interface's values, enums, errors and protocol, which every story uses

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [ ] T004 [P] Write `tests/pac/test_public_api.py` (failing until T015): parse the `## Exports` block of `specs/002-pac-interface-simulator/contracts/public-api.md` as `tests/test_public_api.py` does and assert `set(mictlanix.cfdi.pac.__all__)` equals it, without duplicates, every name importable; `mictlanix.cfdi.__all__` contains none of these names; and every `import`/`from` statement in the files under `src/mictlanix/cfdi/pac/` names only the standard library, `lxml` or `mictlanix.cfdi` (FR-010)
- [ ] T005 [P] Write `tests/pac/test_errors.py` (failing): `PacRejected`, `PacUnavailable` and `PacTimeout` subclass `PacError`, which subclasses `mictlanix.cfdi.CfdiError`; `PacRejected('CFDI40102', 'Sello inválido')` has `.code`, `.message` and `str(error) == 'CFDI40102: Sello inválido'`; `PacUnavailable()` and `PacTimeout()` take no arguments and have fixed messages
- [ ] T006 [P] Write `tests/pac/test_values.py` (failing): `Stamp`, `CsdCredentials`, `CancellationRequest` and `SatStatus` are frozen (assigning a field raises `FrozenInstanceError`) and keyword-only; `repr(CsdCredentials(...))` equals `CsdCredentials(certificate=<N bytes>, private_key=<hidden>, password=<hidden>)` with N the certificate's length; `repr(Stamp(...))` equals `Stamp(xml=<N bytes>, timbre=<repr of the timbre>)` and does not contain the XML; neither those nor the `repr` of a request holding the credentials contains the password, the key bytes or the certificate bytes, raw or Base64; `CancellationAnswer`, `SatState`, `Cancellability` and `CancellationStatus` have exactly the members and values of data-model.md section 2 and compare equal to their string values; every method of `PacClient` is a coroutine function (`inspect.iscoroutinefunction`, FR-001)
- [ ] T007 [P] Write `tests/pac/test_cancellation_request.py` (failing): reasons '02', '03' and '04' without `substitute_uuid`, and '01' with one, build; each of '02', '03' and '04' with a `substitute_uuid` raises `ValidationError` with rule `cancellation-substitute-forbidden`, attribute `substitute_uuid`; '01' without one → `cancellation-substitute-required`, attribute `substitute_uuid`; '05' and '' → `cancellation-reason`, attribute `reason`; `uuid='not-a-uuid'` → `uuid-format`, attribute `uuid`; a malformed `substitute_uuid` → `uuid-format`, attribute `substitute_uuid`; every violation has `node='CancellationRequest'`; a lower-case UUID is accepted and kept as given; several problems come together in one error
- [ ] T008 Implement `PacError`, `PacRejected(code: str, message: str)`, `PacUnavailable` and `PacTimeout` in `src/mictlanix/cfdi/pac/_errors.py` per research.md R7 and export them; make T005 pass
- [ ] T009 Implement in `src/mictlanix/cfdi/pac/_interface.py`: the `StrEnum`s `CancellationAnswer`, `SatState`, `Cancellability`, `CancellationStatus` (data-model.md section 2); the frozen keyword-only dataclasses `Stamp(xml: bytes, timbre: tfd11.TimbreFiscalDigital)` with the `repr` "`Stamp(xml=<N bytes>, timbre=...)`", `CsdCredentials(certificate: bytes, private_key: bytes, password: str)` with the `repr` "`CsdCredentials(certificate=<N bytes>, private_key=<hidden>, password=<hidden>)`", `SatStatus(state, cancellability, cancellation)` and `CancellationRequest(issuer_rfc, recipient_rfc, uuid, total: Decimal, reason: str, substitute_uuid: str | None = None, csd)` whose `__post_init__` raises `ValidationError` with every violation per research.md R6 ("`reason` not in 01–04 → `cancellation-reason`; 01 without `substitute_uuid` → `cancellation-substitute-required`; 02–04 with it → `cancellation-substitute-forbidden`; `uuid` or `substitute_uuid` not `8-4-4-4-12` hex (any case) → `uuid-format`"); the `PacClient` `Protocol` with the four async methods of the contract. Export the public names; make T006 and T007 pass

**Checkpoint**: the interface exists and is tested; stories can start

---

## Phase 3: User Story 1 - Stamp a sealed document, safely (Priority: P1) 🎯 MVP

**Goal**: `SimulatedPac.stamp`, `find_stamp` and `configure_stamp` with every stamping outcome,
with the state kept in an in-memory store private to the instance

**Independent Test**: quickstart.md scenarios 1 and 2

### Tests for User Story 1

- [ ] T010 [US1] Write `tests/pac/test_simulated_stamp.py` (failing), each test with its own `SimulatedPac(clock=clock)` and documents from `make_sealed()`; every stamp goes through `assert_valid_stamp` (SC-001 is checked statically by `_conforms`):
  - a stamp: `timbre.UUID` is upper case and 36 characters, two documents get different UUIDs, `SelloSAT` is Base64 of 256 bytes, and `SIMULATED_PAC_RFC == 'SIM010101SI0'`
  - a clock returning a time with microseconds gives a `FechaTimbrado` without them
  - `stamp_of` (private, `mictlanix.cfdi.pac._interface`) of `tests/fixtures/stamped/ingreso_timbrado.xml` with its TFD's `UUID` written in lower case returns that UUID in upper case
  - `SimulatedPac()` without a clock stamps with `FechaTimbrado` within 2 seconds of `mictlanix.cfdi._mexico.now()`
  - idempotence: stamping the same document twice, and stamping the stamp's own `stamp.xml`, return the identical stamp; `find_stamp` returns it; `find_stamp` of a never-stamped document returns `None` and a later `stamp` of it still makes the first stamp (concurrent calls: T014)
  - `StampOutcome` has exactly the members and values of data-model.md section 2
  - `configure_stamp(doc, StampOutcome.REJECTED, code='CFDI40102', message='Sello inválido')` → `PacRejected` with that code and message, then `find_stamp` is `None`; `REJECTED` without code or message → `CFDI40999` / `Rechazo simulado`
  - `STAMPED` configured → a normal stamp, and the outcome is used up
  - an outcome configured for a document is neither used nor honoured by `find_stamp` (it returns `None`, then `stamp` applies the outcome); `REJECTED` with only `code` gives the default message, with only `message` the default code
  - `REJECTED`, `TIMEOUT_STAMPED` and `TIMEOUT_NOT_STAMPED` each on an already-stamped document → `PacRejected`, `PacTimeout`, `PacTimeout`, and `find_stamp` then returns the existing stamp
  - `UNAVAILABLE` → `PacUnavailable`, `find_stamp` is `None`; `UNAVAILABLE` on an already-stamped document → `PacUnavailable`, then the next `stamp` returns the existing stamp
  - `TIMEOUT_STAMPED` → `PacTimeout`, then `find_stamp` returns a stamp and `stamp` returns that same stamp
  - `TIMEOUT_NOT_STAMPED` → `PacTimeout`, `find_stamp` is `None`, and the next `stamp` succeeds (the outcome is used up)
  - bad input, through both `stamp` and `find_stamp`: `b'not xml'`, a non-CFDI XML, a `str` holding a sealed document and `None` → `PacRejected` code `301`; `to_xml(make_invoice())` (never sealed) and a sealed document with `Sello=""` → `302`; a sealed document with `Total="abc"` (edited after sealing), one without `Total`, and one whose `cfdi:Receptor` lost its `Rfc` → `301`; a document stamped earlier and then edited after sealing to `Total="abc"` (same `Sello`) → `301`, not the earlier stamp; a sealed document whose `Folio` was edited after sealing (still readable, seal no longer verifies) is stamped normally (FR-020); `tests/fixtures/stamped/ingreso_timbrado.xml` (a TFD this PAC has no record of) → `307` from `stamp` and `None` from `find_stamp`, and so does a `stamp.xml` made by another `SimulatedPac` (separate store); `configure_stamp` rejects the same invalid inputs with the same codes; nothing else is raised; no error's `str` or `repr` contains the input; every `PacRejected` has `__cause__ is None` and `__suppress_context__` true; invalid input with an outcome configured for its seal leaves that outcome for the next valid call
  - a sealed document with an `Addenda` and no `Complemento` gets `cfdi:Complemento` immediately before `cfdi:Addenda`, and `read(stamp.xml)` keeps the addenda

### Implementation for User Story 1

- [ ] T011 [US1] Add to `src/mictlanix/cfdi/pac/_interface.py` the private `stamp_of(xml: bytes) -> Stamp` (reads the document with `mictlanix.cfdi.read`, takes its `timbre`, upper-cases `UUID` with `dataclasses.replace`), and implement in `src/mictlanix/cfdi/pac/simulated.py`: `SIMULATED_PAC_RFC = 'SIM010101SI0'`; the `StampOutcome` `StrEnum` with the values of data-model.md section 2; `SimulatedPac.__init__(self, *, clock=None)` (keyword-only, default `_mexico.now`) holding a private dict-backed store; private JSON record helpers for the keys of data-model.md section 4; and `stamp`, `find_stamp` and `configure_stamp` per research.md R10–R11 and data-model.md section 5 "Stamp" (parse with the library's safe parser, check its input in the order of R11 (non-bytes, `301`/`302`/`301`, lookup by seal, `307`), always `from None`, then apply the configured outcome before returning a known document's stamp; build the TFD from a `tfd11.TimbreFiscalDigital` with the library's `serialize`; insert it into `cfdi:Complemento`, created before `cfdi:Addenda` or last; return `stamp_of(stamped_xml)`). Add the private conformance function `_conforms(pac: SimulatedPac) -> PacClient: return pac` so `mypy src` checks SC-001. Export `SIMULATED_PAC_RFC`, `SimulatedPac` and `StampOutcome`; make T010 pass

**Checkpoint**: a caller can stamp and recover from every failure without a second stamp

---

## Phase 4: User Story 2 - Cancel a stamped document and follow its SAT status (Priority: P2)

**Goal**: `request_cancellation`, `query_status`, `configure_cancellation` and
`answer_as_receiver`

**Independent Test**: quickstart.md scenarios 3 and 4

### Tests for User Story 2

- [ ] T012 [US2] Write `tests/pac/test_simulated_cancel.py` (failing). Requests use the stamp's RFCs, UUID and total, reason '02' and the `credentials` fixture; after each step assert the answer and then `query_status` (state / cancellability / cancellation):
  - `CancellationOutcome` and `ReceiverAnswer` have exactly the members and values of data-model.md section 2
  - before any request: valid / without_acceptance / none; after `clock.advance(timedelta(hours=24))` (exactly 24 hours): valid / with_acceptance / none
  - stamped 1 hour before → `accepted`; cancelled / without_acceptance / accepted
  - stamped exactly 24 hours before → `pending` (the boundary is "under 24 hours")
  - stamped 25 hours before → `pending`; valid / with_acceptance / pending; a second request → `pending`, unchanged
  - pending, then `answer_as_receiver(uuid, ReceiverAnswer.ACCEPT)` → cancelled / with_acceptance / accepted; `REJECT` → valid / with_acceptance / rejected, and a new request goes `pending` again; `EXPIRE` → cancelled / with_acceptance / expired
  - after accepted or expired, another request → `accepted`, unchanged
  - `configure_cancellation(uuid, CancellationOutcome.NOT_CANCELLABLE)` → `not_cancellable`; valid / not_cancellable / none; a later request with nothing configured → `not_cancellable` again; then `ACCEPTED` configured → `not_cancellable`, unchanged; then `TIMEOUT` configured → `PacTimeout`, unchanged (whether the ignored `ACCEPTED` was used up is not observable here; the pending case below checks it)
  - `ACCEPTED` on a document 25 hours old → `accepted`; `PENDING` on a document 1 hour old → `pending`, and its status is valid / with_acceptance / pending
  - `TIMEOUT` on a document 1 hour old → `PacTimeout`; valid / with_acceptance / pending
  - `PENDING` on a document 1 hour old, then `REJECT` by the receiver, then a request with nothing configured → `pending`
  - on a pending document: `ACCEPTED` configured → `pending`, unchanged; then the receiver `REJECT`s and a request with nothing configured → `pending` (a leftover `ACCEPTED` would answer `accepted`); `TIMEOUT` configured → `PacTimeout`, unchanged; on a cancelled document: `PENDING` configured → `accepted`, unchanged; `TIMEOUT` → `PacTimeout`, unchanged
  - `REJECTED` (with and without code and message) → `PacRejected`, unchanged; `UNAVAILABLE` → `PacUnavailable`, unchanged; each configured outcome is used up by one call
  - a UUID never stamped: query → valid / with_acceptance / none, whatever the RFCs and total; request → `pending`; then the receiver can accept it
  - a query with a different issuer RFC, recipient RFC or total → not_found / not_cancellable / none; the total written differently but equal (`Decimal('116.0')` for `116.00`) → found; a request with a mismatch → `PacRejected` code `205`, and with `TIMEOUT` configured the mismatch still answers `205` and the next matching request raises `PacTimeout`
  - a query with a malformed UUID → not_found / not_cancellable / none
  - a document stamped through `TIMEOUT_STAMPED` has its record: a request 1 hour later → `accepted`, and a request with a different total → `205`
  - a never-stamped UUID with an outcome configured, then `query_status` with arbitrary RFCs and total → valid / with_acceptance / none; with `NOT_CANCELLABLE` answered → valid / not_cancellable / none
  - `configure_cancellation` with a lower-case UUID applies to requests for the upper-case one; one configured for `'not-a-uuid'` never applies; `query_status` neither uses nor honours a configured outcome (the next request still gets it)
  - after a receiver `REJECT`, `NOT_CANCELLABLE` configured → `not_cancellable`; valid / not_cancellable / rejected
  - a lower-case UUID in a request or query finds the upper-case stamp
  - `answer_as_receiver` with nothing pending → `PacRejected` code `SIM01`
  - FR-020: a request whose `CsdCredentials` hold arbitrary bytes and password, with reason '01' and a substitute UUID the simulator never saw, is answered by the normal rules
  - no error's `str` or `repr` contains the password, key or certificate bytes

### Implementation for User Story 2

- [ ] T013 [US2] Make `stamp` also write the `uuid:` record (issuer and recipient RFCs, total, stamp date, state `valid`, cancellation `none`; data-model.md section 4) before the `seal:` record, on every path that stamps (`TIMEOUT_STAMPED` included); add the `CancellationOutcome` and `ReceiverAnswer` `StrEnum`s (data-model.md section 2) and export them; implement `request_cancellation`, `query_status`, `configure_cancellation` and `answer_as_receiver` in `src/mictlanix/cfdi/pac/simulated.py` per research.md R12 and data-model.md section 5 "Cancellation" (state machine; 24-hour rule by the clock; cancellability fixed at `with_acceptance` once a cancellation goes pending and at `not_cancellable` once answered so; the default answer following the cancellability; configured outcomes on pending, cancelled or not-cancellable documents; records created for unknown UUIDs; unknown and malformed UUIDs; decimal comparison of totals; codes `205` and `SIM01`; no check of the credentials or the substitute UUID); make T012 pass

**Checkpoint**: every cancellation path and status is reachable and tested

---

## Phase 5: User Story 3 - Share the simulated PAC's state (Priority: P3)

**Goal**: the caller supplies the store, so several simulators share one state

**Independent Test**: quickstart.md scenario 5

- [ ] T014 [US3] Write `tests/pac/test_simulated_store.py` (failing: `SimulatedPac` has no `store` parameter yet and the store names are not exported): two `SimulatedPac(store, clock=clock)` (store positional, as in quickstart scenario 5) over one `InMemoryStore()` — a stamp through one is found and re-returned by the other; a stamp outcome configured through one applies to the next stamp through the other; a cancellation outcome configured through one applies through the other; a receiver's answer through either is seen by both; two simulators created without a store (`SimulatedPac(clock=clock)`) share nothing; a caller's own store class with only `async get` and `async set` over a dict works the same; with a store whose `get` and `set` each `await asyncio.sleep(0)` first, `asyncio.gather` of two `stamp` calls of one new document through one instance returns the identical stamp and `find_stamp` returns it (SC-004; fails without the lock); a store whose `get` or whose `set` raises `RuntimeError` makes `stamp`, `find_stamp`, `request_cancellation`, `query_status`, `configure_stamp`, `configure_cancellation` and `answer_as_receiver` raise `PacUnavailable`, and no other exception, with `__cause__ is None` and `__suppress_context__` true; a store whose `set` fails only on the second write of a stamp makes `stamp` raise `PacUnavailable`, then `find_stamp` returns `None` and a new `stamp` returns a valid stamp; `SimulatedPac(store)` positionally works (quickstart scenario 5)
- [ ] T015 [US3] In `src/mictlanix/cfdi/pac/simulated.py` add one `asyncio.Lock` per `SimulatedPac` serializing its operations (research.md R9); the `SimulatorStore` `Protocol` (`async get(key: str) -> str | None`, `async set(key: str, value: str) -> None`) and the public `InMemoryStore` replacing the private dict-backed store; add the positional `store: SimulatorStore | None = None` parameter before the keyword-only `clock` of `SimulatedPac.__init__` (default a new `InMemoryStore()`); route every store call through one helper that turns any exception into `PacUnavailable` raised `from None`; extend `_conforms` to also return an `InMemoryStore` as a `SimulatorStore`; export `SimulatorStore` and `InMemoryStore`; make T014 and T004 pass (research.md R9; contract: the lock is per instance)

**Checkpoint**: all three stories work independently

---

## Phase 6: Polish & Cross-Cutting Concerns

- [ ] T016 [P] Add a "Stamping and cancelling" section to `README.md` with quickstart.md scenario 1 and a cancellation, naming `SimulatedPac` as the offline PAC and #3 as the first real one (SC-001)
- [ ] T017 [P] Add the PAC interface and the simulated PAC to the `Unreleased` section of `CHANGELOG.md`, noting that the Mexico City offset moved to a shared private module with no behaviour change (constitution V: changes are listed in the changelog)
- [ ] T018 Run quickstart.md end to end (`uv run pytest -q`, `uv run ruff check`, `uv run ruff format --check`, `uv run mypy src`, `uv build`); every test passes, `tests/pac/test_public_api.py` included, and `tests/test_no_secrets.py` and `tests/test_offline.py` still pass with the new tests (SC-006; SC-005 is asserted by T006, T010 and T012)

---

## Dependencies & Execution Order

- Phase 1: T001 before every test task (fixtures); T002 before T003; T003 before T011.
- Phase 2: T004–T007 in parallel; T008 after T005; T009 after T006 and T007 (it raises the
  library's `ValidationError`, so it does not need T008).
- US1: T010 then T011, after Phase 2. US2: T012 then T013, after US1 (cancellations start from
  stamped documents). US3: T014 then T015, after US2 (it re-plumbs every operation's store).
- Polish after the stories.

### Parallel Opportunities

- T004, T005, T006 and T007 (four test files).
- T016 and T017 (different files).
- The story phases share `simulated.py`, so their implementation tasks run in sequence.

### Parallel Example: Phase 2

```text
Task: "Write tests/pac/test_public_api.py (failing until T015)"
Task: "Write tests/pac/test_errors.py (failing)"
Task: "Write tests/pac/test_values.py (failing)"
Task: "Write tests/pac/test_cancellation_request.py (failing)"
```

## Implementation Strategy

### MVP First (User Story 1 only)

Phases 1–3 give a caller the interface and a simulator that stamps and exercises every stamping
failure. Stop there and validate with quickstart.md scenarios 1 and 2. Calls never stamp twice
from US1 on; concurrency can only interleave once a caller's store suspends, which US3 makes
possible, so the lock (FR-013) and its test arrive there.

### Incremental Delivery

US1 (stamping) → US2 (cancellation and status) → US3 (a caller-supplied, shared store). Each
adds tests first and leaves every gate green.

## Notes

- Do not commit per task. The project keeps one commit for the documents (made before
  implementation starts) and one for the code.
- `stamp_of` is private but is what the Multifacturas client (#3) will reuse to build its stamps.
