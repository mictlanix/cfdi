# Implementation Plan: Facturación México (Multifacturas) PAC Client

**Branch**: `003-multifacturas-pac` | **Date**: 2026-11-18 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/003-multifacturas-pac/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command; its definition describes the execution workflow.

## Summary

`MultifacturasPac` implements spec 002's `PacClient` for Facturación México, so a caller swaps
`SimulatedPac` for it and changes nothing else.

- **Stamping**: it stamps with `timbrar33b64`. The PAC deduplicates by sealed document, which was
  verified in its test mode, so stamping again after a timeout returns the existing stamp.
- **`find_stamp`**: returns `None`; this was the user's decision.
- **Cancelling**: it cancels through the PAC's `cancelacion2022` service. The SAT's code decides
  pending (201) or accepted (202).
- **SAT status**: removed from this client and from `PacClient` (2026-11-18); the SAT's status
  service does not depend on the PAC, and mictlanix/cfdi#6 tracks a PAC-independent client.
- **`balance()`**: an extra method on this client that exposes the PAC's `saldo`.

Technical approach: no new dependency. A small hand-written SOAP 1.1 RPC client uses the standard
library's `http.client` and `ssl`, with certificate verification on. Each call runs in a worker
thread. Connect failures become `PacUnavailable` and anything after the connection opens becomes
`PacTimeout`. Answers are parsed with `lxml`. Offline tests replay recorded, scrubbed answers
through one private seam, and live tests against the PAC's test mode are opt-in. Decisions R1–R10
are in [research.md](research.md).

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: none new.
- **Standard library**: `http.client`, `ssl`, `asyncio`, `base64`, `json`.
- **lxml**: already a dependency, used to parse answers.
- **The library's own code**: the reader, `stamp_of`, `_qr_total`, and the input checks of spec
  002 (moved to a shared private module).

**Storage**: N/A

**Testing**: pytest with pytest-asyncio.
- **Offline**: replays recorded answers by monkeypatching the private `_post` seam.
- **Live**: opt-in, gated on `MULTIFACTURAS_USER` and `MULTIFACTURAS_PASSWORD`, against the PAC's
  test mode.

**Target Platform**: any CPython 3.12 with a system CA trust store.

**Project Type**: library (module `mictlanix.cfdi.pac.multifacturas`).

**Performance Goals**: one HTTPS round trip per operation (two for a 307 answer without the
stamped document).

**Constraints**:
- HTTPS only, with verified certificates;
- no environment reads;
- no secrets, raw payloads or `messageDetail` in errors or reprs;
- only `PacError` subclasses escape;
- mypy strict.

**Scale/Scope**:
- 4 PAC operations (`timbrar33b64`, `acuseSAT`, `saldo`, `cancelarCfdi`);
- 2 new public names (`MultifacturasPac`, `MultifacturasSettings`);
- 1 dev-only recorder script.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | How this plan complies | Status |
|-----------|------------------------|--------|
| I. The SAT is the source of truth | Cancellation outcomes use the SAT's code; stamps are checked to carry the TFD and the submitted seal | Pass |
| II. Test-first, always | Every task writes its tests first; offline tests replay recorded answers; PAC tests are opt-in through `MULTIFACTURAS_USER`/`MULTIFACTURAS_PASSWORD` and skipped without them | Pass |
| III. Secrets never leak | Credentials come only from the caller's `MultifacturasSettings` (repr hides the password) and `CsdCredentials`; errors carry only the PAC's code and short message, never `messageDetail`, raw payloads or XML; fixtures are scrubbed by the recorder and checked by a test | Pass |
| IV. Never stamp twice | Async; typed errors; a timeout is resolved by resubmitting the sealed document, which the PAC answers from its record with the existing stamp (verified, research R3/R4), or SAT 307 → existing stamp; never a second UUID | Pass (constitution v1.1.0 admits resolving a timeout by a resubmission the PAC answers with the existing stamp) |
| V. Small, stable, typed API | `MultifacturasPac` and `MultifacturasSettings` exported from `mictlanix.cfdi.pac` only; mypy strict; checked by the contract test | Pass |
| VI. Simplicity | No new dependency (standard library HTTP + existing lxml); the client lives in its own module behind `PacClient` | Pass |
| Workflow | uv, ruff, mypy strict, pytest; English; SAT names unchanged; PR references #3 | Pass |

Post-design re-check: still Pass. The design adds no dependency, exports two names from
`mictlanix.cfdi.pac`, and every value holding credentials hides them in its `repr`.

## Project Structure

### Documentation (this feature)

```text
specs/003-multifacturas-pac/
├── plan.md              # This file
├── research.md          # R1–R10
├── data-model.md        # settings, answer mappings, code map
├── quickstart.md        # validation scenarios
├── contracts/
│   └── public-api.md    # the two new exports and their behaviour
└── tasks.md             # /speckit-tasks
```

### Source Code (repository root)

```text
src/mictlanix/cfdi/pac/
├── __init__.py          # + MultifacturasPac, MultifacturasSettings
├── _input.py            # NEW: sealed-input checks check, Sealed, reject (from simulated.py)
├── _soap.py             # NEW: _post (raw HTTPS exchange, transport errors; the test seam) and
│                        #      call (envelope + _post + Fault check + parsing)
├── multifacturas.py     # NEW: MultifacturasSettings, MultifacturasPac
└── simulated.py         # imports the input checks from _input.py; query_status removed

tools/record_multifacturas.py   # NEW, dev-only: records and scrubs fixtures from the test mode

tests/pac/
├── test_input.py                 # the moved checks (simulator tests keep passing unchanged)
├── test_soap.py                  # envelopes, answer parsing, mojibake repair, transport mapping
├── test_multifacturas_settings.py
├── test_multifacturas_stamp.py   # US1
├── test_multifacturas_cancel.py  # US2
├── test_multifacturas_balance.py # US3
├── test_multifacturas_fixtures.py # fixtures carry no credentials, real RFCs or PAC payload fields
└── test_multifacturas_live.py    # opt-in, skipped without MULTIFACTURAS_USER/PASSWORD

tests/fixtures/multifacturas/     # recorded and synthetic answers + README
```

**Structure Decision**: the client gets its own module, as constitution VI requires. Transport and
SOAP are private modules shared by future PAC clients. The simulator's input checks
move to `_input.py` so both clients reject invalid input the same way.

## Complexity Tracking

No constitution violations; nothing to justify. (The timeout resolution this feature first recorded
here as a deviation from principle IV is admitted by constitution v1.1.0, amended on 2026-11-18 for
it: the PAC answers a resubmission of the same sealed document with the existing stamp.)
