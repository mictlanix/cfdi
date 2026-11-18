# Quickstart: validating the feature end to end

Prerequisites: the repository set up with `uv sync`; the SAT's public test CSD in
`tests/fixtures/csd/` (from #1). Everything runs offline.

```sh
uv run pytest -q tests/pac
uv run pytest -q
uv run ruff check && uv run ruff format --check && uv run mypy src
uv build
```

Expected: all green. The scenarios below are what those tests exercise; the API is in
[contracts/public-api.md](contracts/public-api.md).

## Scenario 1 (P1): stamp and read back

Seal the quickstart invoice of #1 (`Fecha` inside the test CSD's validity), then:

```python
from mictlanix.cfdi import read, tfd_original_string, timbre
from mictlanix.cfdi.pac import PacClient, SimulatedPac

pac: PacClient = SimulatedPac()
stamp = await pac.stamp(sealed)
```

Expected:

- `stamp.timbre.UUID` is upper case, `stamp.timbre.RfcProvCertif == 'SIM010101SI0'`,
  `stamp.timbre.SelloCFD` equals the document's `Sello`.
- `timbre(read(stamp.xml)) == stamp.timbre`; the TFD in `stamp.xml` is valid against the vendored
  `TimbreFiscalDigitalv11.xsd`; `tfd_original_string(stamp.xml)` starts with `||1.1|<UUID>|`.
- `await pac.stamp(sealed) == stamp` and `await pac.find_stamp(sealed) == stamp`.

## Scenario 2 (P1): failures without a second stamp

For a fresh sealed document each time, `configure_stamp` then `stamp`:

| Outcome | `stamp` raises | then `find_stamp` |
|---------|----------------|-------------------|
| `REJECTED`, code `CFDI40102` | `PacRejected` with that code and message | `None` |
| `UNAVAILABLE` | `PacUnavailable` | `None` |
| `TIMEOUT_STAMPED` | `PacTimeout` | the stamp; stamping again returns it |
| `TIMEOUT_NOT_STAMPED` | `PacTimeout` | `None`; stamping again succeeds |

Input that is not XML, not a CFDI 4.0 or not sealed raises `PacRejected` with `301` or `302` (from
`stamp` and from `find_stamp`); a document carrying a TFD this PAC has no record of raises `307`
from `stamp`, and `find_stamp` returns `None` for it. No error's text contains the input.

## Scenario 3 (P2): cancellation paths

With a clock the test controls, stamp, then request a cancellation (reason `02`, the test
`CsdCredentials`) and query the status after each step:

| Setup | Answer | Status (state / cancellability / cancellation) |
|-------|--------|-----------------------------------------------|
| stamped 1 hour ago | `accepted` | cancelled / without_acceptance / accepted |
| stamped 25 hours ago | `pending` | valid / with_acceptance / pending |
| … then `answer_as_receiver(ACCEPT)` | — | cancelled / with_acceptance / accepted |
| … or `REJECT` | — | valid / with_acceptance / rejected |
| … or `EXPIRE` | — | cancelled / with_acceptance / expired |
| `NOT_CANCELLABLE` configured | `not_cancellable` | valid / not_cancellable / none |
| `TIMEOUT` configured | `PacTimeout` | valid / with_acceptance / pending |
| `REJECTED` / `UNAVAILABLE` configured | `PacRejected` / `PacUnavailable` | unchanged |
| UUID never stamped | `pending` | valid / with_acceptance / pending |
| wrong total in the query | — | not_found / not_cancellable / none |

## Scenario 4 (P2): cancellation requests

| Built with | Result |
|------------|--------|
| reason `01`, no `substitute_uuid` | `ValidationError`, rule `cancellation-substitute-required` |
| reason `02`, a `substitute_uuid` | `ValidationError`, rule `cancellation-substitute-forbidden` |
| reason `05` | `ValidationError`, rule `cancellation-reason` |
| `uuid='not-a-uuid'` | `ValidationError`, rule `uuid-format` |
| reason `01` with a substitute, or `02`–`04` without | built |

`repr(request)` and `repr(request.csd)` contain neither the password nor the key or certificate
bytes.

## Scenario 5 (P3): one store, two simulators

`store = InMemoryStore()`; `a = SimulatedPac(store)`, `b = SimulatedPac(store)`. Stamp through
`a`: `b.find_stamp` returns it. Configure `TIMEOUT_NOT_STAMPED` through `b`: the next
`a.stamp` of that document raises `PacTimeout`. `SimulatedPac()` with no store shares nothing.
