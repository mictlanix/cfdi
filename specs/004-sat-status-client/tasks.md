---

description: "Task list for the generic SAT CFDI status client"
---

# Tasks: Generic SAT CFDI Status Client

**Input**: Design documents from `/specs/004-sat-status-client/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/public-api.md,
quickstart.md

**Tests**: mandatory (constitution II, spec FR-010). Every behaviour is first asserted by a task
marked "failing", done when its new tests fail for the expected reason and everything else still
passes.

**Organization**: Tasks are grouped by user story to enable independent implementation and
testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2)
- Exact file paths are in the descriptions

## Conventions for every task

- Code lives in `src/mictlanix/cfdi/sat/` and `src/mictlanix/cfdi/_soap.py`; tests in
  `tests/sat/`; answers in `tests/fixtures/sat/`.
- A non-test task is done when the tests it names pass, every other test passes except those a
  later task is listed to make pass, and `uv run ruff check`, `uv run ruff format --check` and
  `uv run mypy src` pass. `tests/sat/test_public_api.py` may fail from T007 until T016 (the client
  names arrive with US1 and US2).
- Offline tests never touch the network: they monkeypatch `mictlanix.cfdi._soap._post` and assert
  what was sent.
- The library never reads the environment. Only `tests/sat/test_consulta_live.py` reads
  `SAT_CONSULTA_LIVE`.
- Every `SatError` is raised `from None` and carries no part of the SAT's answer.
- `mictlanix.cfdi.pac` never imports `mictlanix.cfdi.sat` (research R6).

---

## Phase 1: Setup

**Purpose**: the recorded and synthetic answers every later test replays.

- [X] T001 Write `tools/record_sat_consulta.py` (dev-only, never imported by the library or tests) and run it once. It posts the `Consulta` request of research R3 for `re=EKU9003173C9`, `rr=URE180429TM6`, `tt=116.0`, `id=939513EF-CEAA-4E44-9AD9-6224778D9A9D` to the SAT's service and saves the answer as `tests/fixtures/sat/consulta_no_encontrado.xml`. From that envelope it writes synthetic answers by setting `CodigoEstatus` (`S - Comprobante obtenido satisfactoriamente.`), `Estado`, `EsCancelable` and `EstatusCancelacion`, at least: `consulta_vigente_sin_aceptacion.xml` (`Vigente`, `Cancelable sin aceptación`, empty), `consulta_vigente_con_aceptacion.xml` (`Vigente`, `Cancelable con aceptación`, empty), `consulta_vigente_no_cancelable.xml` (`Vigente`, `No cancelable`, empty), `consulta_vigente_en_proceso.xml` (`Vigente`, `Cancelable con aceptación`, `En proceso`), `consulta_vigente_rechazada.xml` (`Vigente`, `Cancelable con aceptación`, `Solicitud rechazada`), `consulta_cancelado_sin_aceptacion.xml` (`Cancelado`, `Cancelable sin aceptación`, `Cancelado sin aceptación`), `consulta_cancelado_con_aceptacion.xml` (`Cancelado`, `Cancelable con aceptación`, `Cancelado con aceptación`), `consulta_cancelado_plazo_vencido.xml` (`Cancelado`, `Cancelable con aceptación`, `Plazo vencido`), `consulta_cancelado_sin_estatus.xml` (`Cancelado`, `Cancelable sin aceptación`, empty), `consulta_codigo_n.xml` (`CodigoEstatus` `N - 601: La expresión impresa proporcionada no es válida.`, `Estado` `Vigente`), and one answer per field with a value outside data model §3: `consulta_estado_desconocido.xml` (`Suspendido`), `consulta_cancelable_desconocido.xml` (`Cancelable`), `consulta_estatus_desconocido.xml` (`Desconocido`). It also writes `tests/fixtures/sat/README.md`: the date, how it was recorded (the SAT's test RFCs and a test UUID, no credentials, nothing to scrub) and a table of every file, recorded or synthetic.
- [X] T002 [P] Write `tests/sat/__init__.py` and `tests/sat/test_consulta_fixtures.py`: every file the README's table lists exists, every `consulta_*.xml` in the folder is listed, and no fixture carries an RFC other than `EKU9003173C9` and `URE180429TM6` (FR-010)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: the shared transport (research R2) and the SAT's values and errors (research R1, R5).

- [X] T003 Write the shared transport's tests (failing) in `tests/test_soap_transport.py`, moving the transport cases of `tests/pac/test_soap.py` (the `FakeConnection` fixture, verified TLS and both timeouts, connect failures including a bad port and a `UnicodeError`, failures after connecting, a Fault whatever the status, another status, a body that is not an envelope) to `mictlanix.cfdi._soap`: `_post` raises `_soap.Unreachable` before the connection opens and `_soap.NoAnswer` after it; `_soap.answer(raw)` returns the first child of the body, raises `_soap.Fault` for a Fault and `_soap.NoAnswer` for anything that is not an envelope with a body; each raised `from None` with no message. Keep in `tests/pac/test_soap.py` the envelope, `fields`, `error_of` and `call` cases, and add that `call` maps `Unreachable`, `NoAnswer` and `Fault` to `PacUnavailable`, `PacTimeout` and `PacRejected('SOAP-FAULT', 'the service refused the request')`, `from None`
- [X] T004 Create `src/mictlanix/cfdi/_soap.py` with `SOAP_ENV`, the private exceptions `Unreachable`, `NoAnswer`, `Fault`, a `Timeouts` protocol (`connect_timeout: float`, `read_timeout: float`), `_post(url, action, body, timeouts) -> bytes` and `answer(raw) -> etree._Element` (moved from `src/mictlanix/cfdi/pac/_soap.py`, behaviour unchanged except the exceptions). In `src/mictlanix/cfdi/pac/_soap.py` keep `envelope`, `fields`, `error_of`, `_repair`, `call` and `Params`, reach `_post` as an attribute of the shared module (so the seam can be patched), and map the three exceptions to the PAC errors. Point the `replay` fixture of `tests/pac/conftest.py` at `mictlanix.cfdi._soap._post`. Make T003 pass and every existing PAC test pass unchanged otherwise
- [X] T005 [P] Write `tests/sat/test_values.py` (failing): `SatStatus` is frozen and keyword-only with `state`, `cancellability`, `cancellation`; the enums have exactly the members and values of data model §1 (`SatState`: `VALID`/`valid`, `CANCELLED`/`cancelled`, `NOT_FOUND`/`not_found`; `Cancellability`: `WITHOUT_ACCEPTANCE`/`without_acceptance`, `WITH_ACCEPTANCE`/`with_acceptance`, `NOT_CANCELLABLE`/`not_cancellable`; `CancellationStatus`: `NONE`/`none`, `PENDING`/`pending`, `ACCEPTED`/`accepted`, `REJECTED`/`rejected`, `EXPIRED`/`expired`); `SatStatusClient.query_status` is a coroutine function; `SatError` subclasses `CfdiError`, not `PacError`; `SatRejected(code, message)` keeps both and prints `code: message`; `SatUnavailable()` and `SatTimeout()` take no arguments and print fixed messages naming the SAT
- [X] T006 Implement `src/mictlanix/cfdi/sat/_errors.py` (`SatError`, `SatRejected`, `SatUnavailable`, `SatTimeout`, mirroring `src/mictlanix/cfdi/pac/_errors.py` per research R5) and `src/mictlanix/cfdi/sat/_interface.py` (`SatState`, `Cancellability`, `CancellationStatus`, the frozen keyword-only `SatStatus`, the `SatStatusClient` protocol per contracts/public-api.md); make T005 pass
- [X] T007 [P] Write `tests/sat/test_public_api.py` (failing until T016; FR-009): `mictlanix.cfdi.sat.__all__` equals the `## Exports` block of `specs/004-sat-status-client/contracts/public-api.md` exactly, without duplicates, each importable; none of them is exported from `mictlanix.cfdi` or `mictlanix.cfdi.pac`; no module under `src/mictlanix/cfdi/pac/` imports `mictlanix.cfdi.sat`
- [X] T008 Create `src/mictlanix/cfdi/sat/__init__.py` exporting the interface, values and errors (the clients are added by T013 and T016)

**Checkpoint**: the transport is shared, the PAC tests pass, and the SAT's values and errors exist.

---

## Phase 3: User Story 1 - Ask the SAT the status of a CFDI (Priority: P1) 🎯 MVP

**Goal**: `SatConsultaClient` answers the status of any CFDI from the SAT's service.

**Independent Test**: replay every fixture of T001 and check the value or error; opt-in, ask the
real service about the test UUID and get not found.

- [X] T009 [P] [US1] Write `tests/sat/test_consulta_settings.py` (failing): defaults `url='https://consultaqr.facturaelectronica.sat.gob.mx/ConsultaCFDIService.svc'`, `connect_timeout=10.0`, `read_timeout=60.0`; frozen and keyword-only; `ValueError` naming the field for a `url` that does not start with `https://` and for a timeout ≤ 0 (data model §2)
- [X] T010 [P] [US1] Write `tests/sat/conftest.py` with a `replay` fixture that patches `mictlanix.cfdi._soap._post`, answers from a queue of fixture names in `tests/fixtures/sat/`, raw bytes or exceptions, and records each request's URL, SOAPAction and `expresionImpresa`, and that re-exports the `clock`, `make_sealed` and `credentials` fixtures of `tests/pac/conftest.py` and `tests/conftest.py` for US2; and `tests/sat/test_consulta.py` (failing): the request goes to the settings' URL with SOAPAction `http://tempuri.org/IConsultaCFDIService/Consulta` and the expression `?re=EKU9003173C9&rr=URE180429TM6&tt=116.0&id=<uuid>` for `Decimal('116.00')` (and `tt=642.2` for `Decimal('642.20')`), XML-escaped (an RFC with `&` arrives intact), a lower-case UUID sent as given, and exactly one request per status (SC-003); every mapping fixture of T001 returns the `SatStatus` data model §3 prescribes; each `*_desconocido.xml` raises `SatRejected('SAT-ANSWER', 'unexpected SAT status')`; a Fault raises `SatRejected('SOAP-FAULT', …)` without the fault text; `_soap.Unreachable` and `_soap.NoAnswer` from the seam raise `SatUnavailable` and `SatTimeout`, and an HTML body or an empty body from the seam raises `SatTimeout`; a malformed UUID (`'nope'`) returns `NOT_FOUND / NOT_CANCELLABLE / NONE` with no request; every error has no `__cause__` and its `str`/`repr` contains nothing from the answer; with `os.environ` emptied and `os.getenv` and `os.environ.get` patched to fail, `SatConsultaClient()` still answers a replayed status (FR-003: nothing is read from the environment)
- [X] T011 [US1] Implement `SatConsultaSettings` in `src/mictlanix/cfdi/sat/consulta.py` per data model §2; make T009 pass
- [X] T012 [US1] Implement `SatConsultaClient(settings: SatConsultaSettings | None = None)` in `src/mictlanix/cfdi/sat/consulta.py` (FR-001, FR-004, FR-005, FR-006): `query_status` runs in `asyncio.to_thread`, builds the expression with `mictlanix.cfdi._read._qr_total` and the document/literal envelope of research R3, posts it through `_soap._post`, reads `_soap.answer` and maps `ConsultaResult`'s leaves by local name per data model §3, and maps the transport per data model §4; make T010 pass
- [X] T013 [US1] Export `SatConsultaClient` and `SatConsultaSettings` from `src/mictlanix/cfdi/sat/__init__.py` (FR-009)
- [X] T014 [US1] Write `tests/sat/test_consulta_live.py`: skipped unless `SAT_CONSULTA_LIVE=1`, overriding the suite's autouse network block for this module only; asks the SAT about the test UUID of T001 with the SAT's test RFCs and `Decimal('116.00')` and gets `NOT_FOUND / NOT_CANCELLABLE / NONE`

**Checkpoint**: User Story 1 is complete and testable on its own.

---

## Phase 4: User Story 2 - Follow a cancellation with the simulator (Priority: P2)

**Goal**: `SimulatedSatStatusClient(pac)` answers from a `SimulatedPac`'s state.

**Independent Test**: stamp, cancel and answer as the recipient with the simulated PAC, checking the
simulated status after each step (quickstart Scenario 2).

- [X] T015 [P] [US2] Write `tests/sat/test_simulated.py` (failing; FR-007, FR-008, SC-002), using the fixtures `tests/sat/conftest.py` re-exports (T010): every row of quickstart Scenario 2 and data model §5 (under and from 24 hours; accepted; pending; the recipient's accept, reject and expire; configured not cancellable; mismatching issuer, recipient or total; a malformed UUID; a UUID never stamped; a lower-case UUID finds the stamp); two simulated PACs over one `InMemoryStore` give the same status; a store whose `get` raises gives `SatUnavailable` from `None`; the simulated client and `SatConsultaClient` both satisfy `SatStatusClient` (checked by mypy through a `_conforms` function in the module)
- [X] T016 [US2] Add the private, locked `SimulatedPac._sat_status(issuer_rfc, recipient_rfc, uuid, total) -> tuple[str, str, str]` to `src/mictlanix/cfdi/pac/simulated.py` (the former `query_status` of spec 002, returning the stored strings, not-found as `('not_found', 'not_cancellable', 'none')`), and implement `SimulatedSatStatusClient` in `src/mictlanix/cfdi/sat/simulated.py` (wrapping the strings in `SatStatus`, `PacUnavailable` → `SatUnavailable` from `None`); export it from `src/mictlanix/cfdi/sat/__init__.py` (FR-009); add a `_conforms` function checked by `mypy src`; make T015 and T007 pass

**Checkpoint**: both user stories work independently.

---

## Phase 5: Polish & Cross-Cutting Concerns

- [X] T017 [P] Add a "SAT status" subsection to `README.md` (asking the SAT with `SatConsultaClient`, following a simulated cancellation with `SimulatedSatStatusClient(pac)`, that no credentials are needed, and that errors are `SatError`s) and the package to `CHANGELOG.md` `Unreleased`, with constitution v1.1.1 and v1.1.2
- [X] T018 Run quickstart.md end to end (`uv run pytest -q`, `uv run ruff check`, `uv run ruff format --check`, `uv run mypy src`, `uv build`); every test passes, the live test is skipped without its flag and passes with `SAT_CONSULTA_LIVE=1`, and `tests/test_no_secrets.py` and `tests/test_offline.py` still pass, and the dependencies in `pyproject.toml` are unchanged (SC-001, SC-004, SC-005, SC-006, FR-011)

---

## Dependencies & Execution Order

- **Phase 1** (T001, T002) has no dependencies; T002 after T001.
- **Phase 2**: T003 → T004; T005 → T006 → T008; T007 any time (fails until T016). Phase 2
  blocks both stories.
- **US1** (T009–T014) after Phase 2 and T001. **US2** (T015–T016) after Phase 2 and T010 (its
  conftest); T016 also completes T007's export check.
- **Polish** after both stories.

## Parallel Example: User Story 1

```text
Task: "Write tests/sat/test_consulta_settings.py (failing)"        # T009
Task: "Write tests/sat/conftest.py and tests/sat/test_consulta.py"  # T010
```

## Parallel Example: User Story 2

```text
Task: "Write tests/sat/test_simulated.py (failing)"  # T015, while US1's T011–T014 run
```

## Implementation Strategy

MVP first: Phase 1, Phase 2, then US1. The SAT client is usable on its own at that checkpoint.
US2 adds the simulator. Each step adds tests first and leaves every gate green.

## Notes

- Do not commit per task: one docs commit before implementation, one code commit after.
- The SAT's service needs no credentials; the only live call outside the opt-in test is T001's
  recording, with the SAT's test RFCs.
