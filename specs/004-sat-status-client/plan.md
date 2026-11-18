# Implementation Plan: Generic SAT CFDI Status Client

**Branch**: `004-sat-status-client` | **Date**: 2026-11-18 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/004-sat-status-client/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command; its definition describes the execution workflow.

## Summary

A new package, `mictlanix.cfdi.sat`, offers the SAT's public status service (ConsultaCFDIService)
as its own asynchronous client, independent of any PAC (mictlanix/cfdi#6).

- **`SatStatusClient`**: a protocol with one operation, `query_status(issuer_rfc, recipient_rfc,
  uuid, total) -> SatStatus`. `SatStatus`, `SatState`, `Cancellability` and `CancellationStatus`
  come back here, as spec 002 had them except `CancellationStatus.REQUESTED`, which nothing
  produces (data model §1).
- **`SatConsultaClient`**: the real client, configured with `SatConsultaSettings` (the SAT's URL by
  default, connect and read timeouts). It sends the verified expression and maps the answer exactly
  as #6 records it; anything else is `SatRejected('SAT-ANSWER')`.
- **Errors**: the SAT's own (`SatError`, `SatRejected`, `SatUnavailable`, `SatTimeout`), in the
  style of the PAC errors (user's decision, 2026-11-18; constitution v1.1.2).
- **`SimulatedSatStatusClient(pac)`**: answers from a `SimulatedPac`'s state, so a caller follows a
  simulated cancellation as before feature 003.

Technical approach: no new dependency. The HTTPS transport that feature 003 wrote moves to a
shared private module, `mictlanix.cfdi._soap`, which raises private transport exceptions that each
client maps to its own errors; the PAC client keeps its behaviour. The simulated PAC gains one
private method, the former `query_status`, that the simulated status client reads under the
simulated PAC's lock. Decisions R1–R8 are in [research.md](research.md).

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: none new.
- **Standard library**: `http.client`, `ssl`, `asyncio`, `re`, `xml.sax.saxutils`.
- **lxml**: already a dependency, used to parse answers.
- **The library's own code**: the transport of feature 003 (moved), `_read._qr_total`,
  `SimulatedPac`.

**Storage**: N/A

**Testing**: pytest with pytest-asyncio.
- **Offline**: replays a recorded not-found answer and synthetic answers through the
  `mictlanix.cfdi._soap._post` seam; the simulated client is tested through `SimulatedPac`.
- **Live**: opt-in with `SAT_CONSULTA_LIVE=1`; no credentials.

**Target Platform**: any CPython 3.12 with a system CA trust store.

**Project Type**: library (package `mictlanix.cfdi.sat`).

**Performance Goals**: one HTTPS round trip per status (none for a malformed UUID).

**Constraints**:
- HTTPS only, with verified certificates;
- no environment reads in the library;
- only `SatError` subclasses escape, raised `from None`, carrying no part of the answer;
- `mictlanix.cfdi.sat` depends on `mictlanix.cfdi.pac` (the simulator), never the reverse;
- mypy strict.

**Scale/Scope**:
- 1 SAT operation (`Consulta`);
- 11 public names in `mictlanix.cfdi.sat`;
- 1 dev-only recorder script.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | How this plan complies | Status |
|-----------|------------------------|--------|
| I. The SAT is the source of truth | The status comes from the SAT's own service; unknown values are rejected, never guessed | Pass |
| II. Test-first, always | Every task writes its tests first; offline tests cover every row of the mapping; the live test is opt-in through `SAT_CONSULTA_LIVE` | Pass |
| III. Secrets never leak | The service takes no credentials; errors carry only a code and a fixed message, never the answer; the recorded fixture uses the SAT's test RFCs and a test UUID | Pass |
| IV. Never stamp twice | Not affected: the client only reads a status; the PAC transport's behaviour is unchanged by the move | Pass |
| V. Small, stable, typed API | Eleven names exported from `mictlanix.cfdi.sat` only (v1.1.2: protocol, values, enums, errors, every SAT status client); `mictlanix.cfdi` and `mictlanix.cfdi.pac` exports unchanged; checked by a contract test; mypy strict | Pass |
| VI. Simplicity | No new dependency; one transport shared instead of a second copy; the simulated client reuses the simulator's rule instead of duplicating it | Pass |
| Workflow | uv, ruff, mypy strict, pytest; English; SAT names unchanged; PR references #6 | Pass |

Post-design re-check: still Pass. The design adds no dependency, keeps the PAC surface unchanged,
and the simulated status client lives in `mictlanix.cfdi.sat` as principle V requires (research
R6).

## Project Structure

### Documentation (this feature)

```text
specs/004-sat-status-client/
├── plan.md              # This file
├── research.md          # R1–R8
├── data-model.md        # values, settings, answer mapping, transport, simulated status
├── quickstart.md        # validation scenarios
├── contracts/
│   └── public-api.md    # mictlanix.cfdi.sat exports and behaviour
└── tasks.md             # /speckit-tasks
```

### Source Code (repository root)

```text
src/mictlanix/cfdi/
├── _soap.py             # NEW: shared HTTPS transport (_post, answer), private exceptions
│                        #      Unreachable / NoAnswer / Fault (moved from pac/_soap.py)
├── pac/
│   ├── _soap.py         # keeps the RPC envelope, fields, error_of, call; maps the transport
│   │                    # exceptions to PacUnavailable / PacTimeout / PacRejected('SOAP-FAULT')
│   └── simulated.py     # + private _sat_status (the former query_status), under the lock
└── sat/
    ├── __init__.py      # NEW: the eleven exports
    ├── _errors.py       # NEW: SatError, SatRejected, SatUnavailable, SatTimeout
    ├── _interface.py    # NEW: SatStatus, SatState, Cancellability, CancellationStatus,
    │                    #      SatStatusClient
    ├── consulta.py      # NEW: SatConsultaSettings, SatConsultaClient, the answer mapping
    └── simulated.py     # NEW: SimulatedSatStatusClient

tools/record_sat_consulta.py      # NEW, dev-only: records the not-found answer, writes synthetics

tests/
├── pac/
│   ├── conftest.py               # replay patches mictlanix.cfdi._soap._post
│   └── test_soap.py              # RPC envelope, fields, error_of, call and its error mapping
├── test_soap_transport.py        # NEW: the shared transport's cases (moved from pac/test_soap.py)
├── sat/
│   ├── __init__.py
│   ├── conftest.py               # replay for the SAT, simulated PAC fixtures
│   ├── test_public_api.py        # exports equal the contract; none from mictlanix.cfdi or .pac
│   ├── test_values.py            # values, enums, errors
│   ├── test_consulta_settings.py
│   ├── test_consulta.py          # US1: request, every mapping row, transport, SAT-ANSWER
│   ├── test_consulta_fixtures.py # every listed fixture exists; no real RFCs
│   ├── test_consulta_live.py     # opt-in, SAT_CONSULTA_LIVE=1
│   └── test_simulated.py         # US2: status through stamping, cancelling and the recipient
└── fixtures/sat/                 # recorded and synthetic answers + README
```

**Structure Decision**: the SAT status client gets its own package beside `mictlanix.cfdi.pac`, as
principle V requires. The transport becomes a private module of `mictlanix.cfdi` that both
packages use; the PAC-specific RPC code stays in `mictlanix.cfdi.pac._soap`.

## Complexity Tracking

No constitution violations; nothing to justify.
