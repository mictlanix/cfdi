---

description: "Task list for the Facturación México (Multifacturas) PAC client"
---

# Tasks: Facturación México (Multifacturas) PAC Client

**Input**: Design documents from `/specs/003-multifacturas-pac/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/public-api.md,
quickstart.md

**Tests**: mandatory (constitution II, spec FR-015/FR-016). Every behaviour is first asserted by a
task marked "failing", done when its new tests fail for the expected reason and everything else
still passes.

**Organization**: Tasks are grouped by user story to enable independent implementation and
testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- Exact file paths are in the descriptions

## Conventions for every task

- Code lives in `src/mictlanix/cfdi/pac/`; tests in `tests/pac/`; recorded answers in
  `tests/fixtures/multifacturas/`.
- A non-test task is done when the tests it names pass, every other test passes except those a
  later task is listed to make pass, and `uv run ruff check`, `uv run ruff format --check` and
  `uv run mypy src` pass. `tests/pac/test_public_api.py` may fail from T011 until T014 (the client
  name arrives with US1).
- Offline tests never touch the network: they monkeypatch the private `_soap._post` seam (a
  `replay` fixture in `tests/pac/conftest.py`) and assert which operation and fields were sent.
- The library never reads the environment. Only `tools/record_multifacturas.py` and
  `tests/pac/test_multifacturas_live.py` read `MULTIFACTURAS_USER` and `MULTIFACTURAS_PASSWORD`.
- No error, `repr` or `str` may contain the PAC password, CSD material, a document's XML, the PAC's
  `messageDetail` or raw payload fields; every `PacError` is raised `from None`.
- Code and docstrings name no application; SAT and PAC field names keep their spelling.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: scrubbed recorded answers to test against

- [ ] T001 Write `tests/pac/test_multifacturas_fixtures.py` (failing: the folder does not exist yet): every file listed in `tests/fixtures/multifacturas/README.md` exists. No fixture holds a real credential: every `rfc`, `clave`, `usuario`, `pass` or `pwd` value is `USER` or `PASSWORD`. The only RFCs that appear, including inside Base64-decoded `cfdi` and `acuse` values, are `EKU9003173C9`, `URE180429TM6`, `XAXX010101000` and `AAA010101AAA`. `png`, `mensaje_original`, `mensaje_original_pac_json` and `messageDetail` are empty or absent. No fixture contains the original-string marker `||4.0|`. Supports FR-014, FR-015, SC-004
- [ ] T002 Write the dev-only `tools/record_multifacturas.py` and run it once against the PAC's test mode with `MULTIFACTURAS_USER`/`MULTIFACTURAS_PASSWORD` set to the PAC's published demo credentials (research.md R10).
  - **Requests** (`produccion=NO`, research R3/R6/R8): it seals a fresh test invoice with `tests/fixtures/csd/` and the current Mexico City time minus 1 hour, then records:
    - `timbrar33b64` ok;
    - the same document again (duplicate);
    - malformed XML (`301`);
    - a tampered `Sello` (`CFDI40102`);
    - `saldo`;
    - `cancelarCfdi` with the test CSD (SAT `205`) and with a wrong CSD password (`CACFDI33`);
    - the SAT `Consulta` for the stamped UUID (`No Encontrado`).
  - **Synthetic files**, derived from those envelopes:
    - `timbrar33b64_307_cfdi.xml`, `timbrar33b64_307_uuid.xml`, `timbrar33b64_307_none.xml`;
    - `acuseSAT_cfdi.xml` (the stamped CFDI in Base64) and `acuseSAT_200.xml`;
    - `cancelarCfdi_201.xml` and `cancelarCfdi_202.xml`;
    - `saldo_error.xml` (a non-`0` `codigo_mf_numero` with `ERROR: {"message":"…"}` text; demo mode ignores credentials, so no real error answer exists);
    - SAT `Consulta` answers for `Vigente`/without acceptance, `Vigente`/with acceptance/`En proceso`, `Vigente`/`No cancelable`, `Cancelado`/`Cancelado sin aceptación`, `Cancelado`/`Plazo vencido`, `Vigente`/`Solicitud rechazada`, and one with an unknown `Estado`.
  - **Scrubbing**: credential values become `USER`/`PASSWORD`; any RFC outside the allowed set, including the PAC's `RfcProvCertif`, becomes `AAA010101AAA`; `png` and the `mensaje_original*` fields are blanked.
  - **Output**: the files go to `tests/fixtures/multifacturas/` with a `README.md` listing each file, whether it is recorded or synthetic, and the recording date. Make T001 pass

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: shared input checks, the SOAP transport, the SAT status query, the settings

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [ ] T003 [P] Write `tests/pac/test_input.py` (failing: `mictlanix.cfdi.pac._input` does not exist): `check(sealed_xml)` raises `PacRejected` `301` for non-bytes, non-XML, non-CFDI 4.0, unreadable or `Total`-less input, and `302` for a missing or blank `Sello`, each `from None`; it returns the root, seal and `Comprobante` of a sealed document; `key` is `seal:` plus the SHA-256 hex of the seal (FR-013, FR-014)
- [ ] T004 Move `_reject`, `_Sealed` and `_check` from `src/mictlanix/cfdi/pac/simulated.py` to `src/mictlanix/cfdi/pac/_input.py` (public-within-package names `reject`, `Sealed`, `check`); `simulated.py` imports them; all `tests/pac/test_simulated_*.py` pass unchanged; make T003 pass
- [ ] T005 [P] Write `tests/pac/test_soap.py` (failing) for `src/mictlanix/cfdi/pac/_soap.py`:
  - **Envelope**: `envelope(operation, params)` builds a SOAP 1.1 RPC/encoded envelope in namespace `urn:wservicewsdl` with `xsi:type="xsd:string"` parameters. Values are XML-escaped (`<`, `&`, quotes). A `dict` parameter is a struct (`<datos xsi:type="tns:datos">…</datos>`). The `SOAPAction` is `"urn:wservicewsdl#<operation>"`.
  - **Return fields**: `fields(answer)` gives the leaf elements of the return as a `dict` of strings.
  - **Error text** (data-model.md §3), checked on the recorded `301`, `CFDI40102` and `CACFDI33` answers:
    - `error_of(numero, texto)` strips `ERROR: ` and reads JSON `message`;
    - it repairs the double encoding (`digestiÃ³n` → `digestión`);
    - it splits `CODE - message`, falling back to `numero` as the code;
    - it never includes `messageDetail`.
  - **Transport** (`_post(url, action, body, settings) -> bytes`, the raw exchange, with `http.client.HTTPSConnection` monkeypatched; and `call(url, operation, params, settings) -> dict[str, str]`, which builds the envelope, calls `_post` and parses, data-model.md §2):
    - a failure in `connect()` (`OSError`, `socket.gaierror`, `ssl.SSLError`, `TimeoutError`) → `PacUnavailable`;
    - a failure in `request`, `getresponse` or `read` (`TimeoutError`, `ConnectionResetError`, `http.client.HTTPException`) → `PacTimeout`;
    - a SOAP Fault body, sent with HTTP 500 as SOAP 1.1 does, or with 200 → `PacRejected('SOAP-FAULT', …)` from `call`, without the fault text;
    - any other HTTP status than 200 → `PacTimeout`;
    - a 200 HTML body → `PacTimeout` from `call`;
    - all raised `from None`.
  - **TLS**: the connection uses `ssl.create_default_context()` (`check_hostname` true, `CERT_REQUIRED`) and the settings' connect and read timeouts. (FR-003, FR-012, FR-013, FR-014, SC-006)
- [ ] T006 Implement `src/mictlanix/cfdi/pac/_soap.py` per research.md R2 and data-model.md §2–§3, with `_post` as the single seam the tests replace and `call` on top of it; make T005 pass
- [ ] T007 [P] Write `tests/pac/test_sat_status.py` (failing) for `src/mictlanix/cfdi/pac/_sat_status.py` `query(settings, issuer_rfc, recipient_rfc, uuid, total)`:
  - **Request**: it posts `Consulta` to `settings.sat_url` with SOAPAction `http://tempuri.org/IConsultaCFDIService/Consulta` and the expression `?re=…&rr=…&tt=…&id=…`. `tt` comes from `mictlanix.cfdi._read._qr_total` (`Decimal('642.20')` → `642.2`), the expression is XML-escaped, and there is no `fe`.
  - **Mapping**: each recorded and synthetic `Consulta` fixture maps per data-model.md §6. An unknown value raises `PacRejected('SAT-ANSWER', …)`.
  - **Malformed UUID**: returns `not_found / not_cancellable / none` without calling `_post`. (FR-010)
- [ ] T008 Implement `src/mictlanix/cfdi/pac/_sat_status.py` per research.md R7; make T007 pass
- [ ] T009 [P] Write `tests/pac/test_multifacturas_settings.py` (failing): `MultifacturasSettings` is frozen and keyword-only with the defaults of data-model.md §1 ("`base_url` | `'https://ws.multifacturas.com'` | MUST start with `https://`", "`connect_timeout` | `10.0`", "`read_timeout` | `60.0`", both "> 0"); `http://` base or SAT URLs and timeouts ≤ 0 raise `ValueError` naming the field; `repr` shows `password=<hidden>` and not the password (FR-002, FR-003, FR-004)
- [ ] T010 Implement `MultifacturasSettings` in `src/mictlanix/cfdi/pac/multifacturas.py` and export it from `src/mictlanix/cfdi/pac/__init__.py`; make T009 pass
- [ ] T011 Update `tests/pac/test_public_api.py` so the expected exports are the union of the `## Exports` blocks of `specs/002-pac-interface-simulator/contracts/public-api.md` and `specs/003-multifacturas-pac/contracts/public-api.md` (failing until T014: `MultifacturasPac` is not exported yet); the import check still allows only the standard library, `lxml` and `mictlanix.cfdi`; add a `replay` fixture to `tests/pac/conftest.py` that monkeypatches `mictlanix.cfdi.pac._soap._post`, answers each call from a queue of fixture files (or raises a given exception) and records the URL, the SOAPAction and the parameters parsed from the envelope sent, so `call`'s envelope building and parsing still run

**Checkpoint**: transport, SAT status and settings exist and are tested

---

## Phase 3: User Story 1 - Stamp through Multifacturas (Priority: P1) 🎯 MVP

**Goal**: `MultifacturasPac.stamp` and `find_stamp`

**Independent Test**: quickstart.md scenarios 1 and 2

- [ ] T012 [US1] Write `tests/pac/test_multifacturas_stamp.py` (failing), every test with `MultifacturasPac(MultifacturasSettings(user='USER', password='PASSWORD', production=…))` and the `replay` fixture:
  - **Request**: `stamp` sends `timbrar33b64` to `<base_url>/pac/index.php` with `rfc=USER`, `clave=PASSWORD`, `xml`= Base64 of the input, and `produccion` `SI`/`NO` according to `production`.
  - **Success**: the recorded ok answer gives a `Stamp` whose UUID is in upper case, whose `SelloCFD` is the input's `Sello`, and with `timbre(read(stamp.xml)) == stamp.timbre`. The recorded duplicate answer gives the same UUID.
  - **307**:
    - with `cfdi` → that stamp;
    - with only `uuid` and `acuseSAT_cfdi` → a second call to `acuseSAT` with `rfc`, `pwd` and the UUID, and that stamp;
    - with `acuseSAT_200` → `PacTimeout`;
    - with neither → `PacTimeout`.
  - **Rejections**:
    - recorded `301` → `PacRejected('301', 'La estructura del comprobante es incorrecta.')`;
    - recorded `CFDI40102` → code `CFDI40102`, whose message has `digestión` and no `||`;
    - a `0` answer without `cfdi`, with a `cfdi` lacking a TFD, or carrying another seal → `PacRejected('MF-ANSWER', …)`.
  - **Input checks**: non-bytes, unsealed and tampered-to-unreadable input are rejected with `301`/`302` before any `_post` call.
  - **`find_stamp`**: returns `None` with no `_post` call, and rejects bad input the same way.
  - **Transport**: `PacUnavailable` and `PacTimeout` from the seam reach the caller unchanged.
  - **Secrets**: no error's `str`/`repr` contains `PASSWORD` or the input XML. (FR-001, FR-005, FR-006, FR-007, FR-012, FR-014, SC-002, SC-003)
- [ ] T013 [US1] Implement `MultifacturasPac.__init__`, `stamp` and `find_stamp` in `src/mictlanix/cfdi/pac/multifacturas.py` per data-model.md §4 (reusing `_input.check` and `_interface.stamp_of`); make T012 pass
- [ ] T014 [US1] Export `MultifacturasPac` from `src/mictlanix/cfdi/pac/__init__.py`; make `tests/pac/test_public_api.py` (T011) pass

**Checkpoint**: a caller can stamp through Multifacturas and resolve a timeout without a second stamp

---

## Phase 4: User Story 2 - Cancel through Multifacturas and follow the SAT status (Priority: P2)

**Goal**: `request_cancellation` and `query_status`

**Independent Test**: quickstart.md scenario 3

- [ ] T015 [US2] Write `tests/pac/test_multifacturas_cancel.py` (failing), using the `replay` fixture and the `credentials` fixture (the SAT test CSD):
  - **Request**: `request_cancellation` sends `cancelarCfdi` to `<base_url>/cancelacion2022/index.php` with the struct `datos`:
    - `usuario=USER`, `pass=PASSWORD`, `accion=cancelar`, `produccion` `SI`/`NO`;
    - `uuid` in upper case, `rfc` = the issuer RFC;
    - `password` = the CSD password, `motivo`;
    - `folioSustitucion`: `''` for reason `02`, the substitute UUID for `01`;
    - `b64Cer`, `b64Key`: Base64 of the certificate and key;
    - no recipient RFC or total.
  - **Mapping** (data-model.md §5):
    - `201` then SAT `Cancelado` → `ACCEPTED`;
    - `201` then `En proceso` → `PENDING`;
    - `201` then `No cancelable` → `NOT_CANCELLABLE`;
    - `201` then `Vigente` with no status → `PENDING`;
    - `201` then a `PacTimeout` from the status query → `PENDING`;
    - `202` then `Cancelado` → `ACCEPTED`, `202` otherwise → `PENDING`;
    - recorded `205` → `PacRejected('205', 'No Existe')`;
    - recorded `CACFDI33` → `PacRejected('CACFDI33', 'Problemas con los campos.')`.
  - **`query_status`**: delegates to `_sat_status.query` with `settings.sat_url` and returns its `SatStatus`.
  - **Secrets**: no error's `str`/`repr` contains the CSD password, `PASSWORD`, or the certificate or key (raw or Base64). (FR-001, FR-008, FR-009, FR-010, FR-012, FR-014)
- [ ] T016 [US2] Implement `request_cancellation` and `query_status` in `src/mictlanix/cfdi/pac/multifacturas.py` per research.md R6–R7, and add the private `_conforms(pac: MultifacturasPac) -> PacClient` so `mypy src` checks SC-001; make T015 pass

**Checkpoint**: every cancellation answer and SAT status maps as specified

---

## Phase 5: User Story 3 - Check the stamp balance (Priority: P3)

**Goal**: `MultifacturasPac.balance`

**Independent Test**: quickstart.md scenario 4

- [ ] T017 [US3] Write `tests/pac/test_multifacturas_balance.py` (failing): `balance()` sends `saldo` with `rfc=USER`, `clave=PASSWORD` and returns `20` from the recorded answer; `saldo_error.xml` → `PacRejected` with the code and message of data-model.md §3; a non-integer `saldo` → `PacRejected('MF-ANSWER', …)`; transport errors pass through (FR-011, FR-012)
- [ ] T018 [US3] Implement `balance` in `src/mictlanix/cfdi/pac/multifacturas.py` per research.md R8; make T017 pass

**Checkpoint**: all three stories work independently

---

## Phase 6: Polish & Cross-Cutting Concerns

- [ ] T019 Write `tests/pac/test_multifacturas_live.py`, marked `pytest.mark.skipif` unless both `MULTIFACTURAS_USER` and `MULTIFACTURAS_PASSWORD` are set (constitution II, FR-016). Against `production=False`:
  - stamp a fresh sealed test invoice: valid stamp, and stamping it again gives the same UUID (SC-003);
  - `find_stamp` is `None`;
  - `balance()` is an `int`;
  - `request_cancellation` of that stamp raises `PacRejected` with code `205` (test stamps never reach the SAT);
  - `query_status` of it is `not_found`.
  Running it with the demo credentials passes, and without them it is skipped.
- [ ] T020 [P] Add a "Multifacturas" subsection to the "Stamping and cancelling" section of `README.md` (creating the client from `MultifacturasSettings`, `production=False` for test mode, `balance()`, `find_stamp` returning `None` and why) and the client to `CHANGELOG.md` `Unreleased`
- [ ] T021 Run quickstart.md end to end (`uv run pytest -q`, `uv run ruff check`, `uv run ruff format --check`, `uv run mypy src`, `uv build`); every test passes, the live tests are skipped without the variables, and `tests/test_no_secrets.py` and `tests/test_offline.py` still pass (SC-002, SC-004, SC-005, SC-006)

---

## Dependencies & Execution Order

- Phase 1: T001 then T002.
- Phase 2: T003, T005, T007 and T009 in parallel. Then:
  - T004 after T003;
  - T006 after T005;
  - T008 after T007 and T006 (it posts through `_soap`);
  - T010 after T009;
  - T011 after T006 and T010.
- US1 (T012–T014) after Phase 2. US2 (T015–T016) after US1 (it shares the client class and needs
  the recorded stamp). US3 (T017–T018) after Phase 2; it can run alongside US2, but it edits the
  same file, so the two run in sequence.
- Polish after the stories.

### Parallel Opportunities

- T003, T005, T007, T009 (four test files).
- T020 alongside T019.

### Parallel Example: Phase 2

```text
Task: "Write tests/pac/test_input.py (failing)"
Task: "Write tests/pac/test_soap.py (failing)"
Task: "Write tests/pac/test_sat_status.py (failing)"
Task: "Write tests/pac/test_multifacturas_settings.py (failing)"
```

## Implementation Strategy

### MVP First (User Story 1 only)

Phases 1–3 let a caller stamp through Multifacturas with every failure mapped. Validate with
quickstart.md scenarios 1 and 2.

### Incremental Delivery

US1 (stamping) → US2 (cancellation and SAT status) → US3 (balance) → opt-in live tests. Each step
adds tests first and leaves every gate green.

## Notes

- Do not commit per task: one docs commit before implementation, one code commit after.
- The PAC's demo credentials are used only through `MULTIFACTURAS_USER`/`MULTIFACTURAS_PASSWORD`
  when recording and running the live tests; they are never written to the repository.
