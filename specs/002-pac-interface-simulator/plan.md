# Implementation Plan: Generic PAC Client Interface and a Simulated PAC

**Branch**: `002-pac-interface-simulator` | **Date**: 2026-11-18 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/002-pac-interface-simulator/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command; its definition describes the execution workflow.

## Summary

Callers stamp and cancel CFDI 4.0 documents through one asynchronous interface, `PacClient`, and
its immutable values (`Stamp`, `CancellationRequest`, `SatStatus`, `CsdCredentials`) and three
typed errors under `PacError`. The first implementation is `SimulatedPac`: offline, configurable
per document and per UUID, and backed by a small key-value store the caller can supply so several
processes share one simulated PAC. Everything lives in the subpackage `mictlanix.cfdi.pac`, as
constitution v1.0.2 (principle V) requires for the PAC interface and its clients; the
Multifacturas client (#3) will be a sibling module behind the same interface.

Technical approach: no new dependency. The interface is a `typing.Protocol`; the values are
frozen dataclasses and `StrEnum`s. The simulator writes its TimbreFiscalDigital with the library's
own `tfd11` model and serializer and inserts it into the caller's sealed XML, leaving every
other node and the original string unchanged, so the stamp is valid against the vendored SAT
schema and reads back through `read`, `timbre` and `tfd_original_string`. The design follows
mbe-api's simulator (`app/services/pac/simulated.py`), which the library's simulator is meant to
replace.

## Technical Context

**Language/Version**: Python 3.12 (`requires-python >= 3.12`)

**Primary Dependencies**: none new. `lxml` (inserting the TFD, already a dependency) and the
library's own `tfd11` model, mapper, reader and fixed Mexico City offset. Standard library:
`asyncio`, `uuid`, `secrets`, `json`, `hashlib`, `dataclasses`, `enum`, `typing.Protocol`.

**Storage**: the simulator's state lives in a caller-supplied async key-value store of strings
(`SimulatorStore`); the default, `InMemoryStore`, is a dict. No storage in the interface.

**Testing**: pytest with pytest-asyncio (`asyncio_mode = "auto"`, already configured); sealed
documents come from the library's `seal` with the SAT's public test CSD (fixtures from #1).
Offline; no PAC test environment in this feature.

**Target Platform**: any platform CPython 3.12 runs on.

**Project Type**: library (subpackage `mictlanix.cfdi.pac`).

**Performance Goals**: none beyond test speed; the simulator does no I/O except through its store.

**Constraints**: offline; async; no secrets in errors, reprs or logs (the library does not log);
nothing but `PacError` subclasses escapes a `PacClient` operation; mypy strict.

**Scale/Scope**: one interface (4 operations), 11 public value and enum types (4 values, 4
status enums, 3 simulator enums), 4 errors, one simulated client with 3 configuration
operations, one store protocol and its in-memory default, and the constant
`SIMULATED_PAC_RFC`: 20 exported names.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | How this plan complies | Status |
|-----------|------------------------|--------|
| I. The SAT is the source of truth | The simulator's TFD is built with the `tfd11` model generated from the SAT's XSD, validated against the vendored `TimbreFiscalDigitalv11.xsd`, and its original string checked with the vendored `cadenaoriginal_TFD_1_1.xslt`. The status vocabulary follows the SAT's consultation service. No SAT artifact changes | Pass |
| II. Test-first, always | Every task writes its tests first; tests cover every simulator path (spec FR-021, SC-003) and the cancellation-request rules. All offline; there is no PAC test environment in this feature, so no opt-in tests are needed yet | Pass |
| III. Secrets never leak | Credentials arrive only in `CsdCredentials`, from the caller; its `repr` shows the certificate's size and hides the key and password; no error carries XML, keys or passwords; tests assert the secrets are absent from `str` and `repr` of every value and error; the library has no logging | Pass |
| IV. Never stamp twice | `PacClient` is async; errors are `PacRejected(code, message)`, `PacUnavailable`, `PacTimeout`; `find_stamp` resolves a timeout; re-stamping the same sealed document returns its stamp; callers branch on types and `code`, never text | Pass |
| V. Small, stable, typed API | Exported from `mictlanix.cfdi.pac` only, listed exactly in `contracts/public-api.md` and checked by a test; `mictlanix.cfdi`'s exports are unchanged; mypy strict. Constitution v1.0.2 puts the PAC interface (protocol, values, enums, errors) and every PAC client in `mictlanix.cfdi.pac` only | Pass |
| VI. Simplicity | No new dependency; the simulator lives in its own module (`pac/simulated.py`) behind the generic interface; the store is two methods over strings; no retry, logging or plug-in machinery | Pass |
| Workflow | uv, ruff, mypy strict, pytest green before merge; English; SAT names keep their spelling (`TimbreFiscalDigital`, `UUID`, `FechaTimbrado`); PR references #2 | Pass |

Post-design re-check (after Phase 1): still Pass. The design adds no dependency, exports only
from `mictlanix.cfdi.pac`, and every value that holds credentials hides them in its `repr`.

## Project Structure

### Documentation (this feature)

```text
specs/002-pac-interface-simulator/
├── plan.md              # This file
├── research.md          # Phase 0: decisions R1–R12
├── data-model.md        # Phase 1: values, enums, errors, simulator records and transitions
├── quickstart.md        # Phase 1: end-to-end validation scenarios
├── contracts/
│   └── public-api.md    # Phase 1: exactly what mictlanix.cfdi.pac exports
└── tasks.md             # Phase 2 (/speckit-tasks)
```

### Source Code (repository root)

```text
src/mictlanix/cfdi/
├── _mexico.py               # MEXICO_CITY offset and now(), shared with _csd.py (moved there)
├── _csd.py                  # imports MEXICO_CITY from _mexico.py; behaviour unchanged
└── pac/
    ├── __init__.py          # exports exactly the contract's list
    ├── _interface.py        # PacClient protocol, Stamp, CsdCredentials, CancellationRequest,
    │                        # CancellationAnswer, SatStatus and its enums, private stamp_of
    ├── _errors.py           # PacError, PacRejected, PacUnavailable, PacTimeout
    └── simulated.py         # SimulatedPac, SimulatorStore, InMemoryStore, outcome enums

tests/pac/
├── __init__.py
├── conftest.py              # make_sealed(), a controllable clock, assert_valid_stamp, credentials
├── test_public_api.py       # exports equal contracts/public-api.md
├── test_values.py           # Stamp, CsdCredentials repr, SatStatus, enums
├── test_cancellation_request.py  # reason 01/02–04 and substitute UUID, UUID format
├── test_errors.py           # hierarchy, PacRejected code/message, no secrets
├── test_simulated_stamp.py  # US1: every stamp path, idempotence, find_stamp, bad input
├── test_simulated_cancel.py # US2: every cancellation path, receiver, status, mismatches
└── test_simulated_store.py  # US3: two simulators over one store, in-memory isolation

tests/test_mexico.py         # the shared Mexico City clock
```

**Structure Decision**: a subpackage `mictlanix/cfdi/pac/` with private modules for the interface
and errors and one public module per PAC client (`simulated.py` now, `multifacturas.py` in #3).
Tests mirror it under `tests/pac/`. The Mexico City offset moves from `_csd.py` to a shared
private module so `_csd.py` and the simulator's clock use one definition.

## Complexity Tracking

No constitution violations; nothing to justify. (The PAC export rule this feature first
recorded here as a deviation is now principle V itself, amended in constitution v1.0.2.)
