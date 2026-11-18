# Quickstart: validating the SAT status client

**Prerequisites**: `uv sync`; the SAT's public test CSD in `tests/fixtures/csd/` (for the simulated
scenarios, which stamp with the simulated PAC).

**Offline** (the default):

```sh
uv run pytest -q tests/sat
uv run pytest -q
uv run ruff check && uv run ruff format --check && uv run mypy src
uv build
```

**Opt-in**, against the SAT's service. No credentials; nothing runs without the flag:

```sh
SAT_CONSULTA_LIVE=1 uv run pytest -q tests/sat/test_consulta_live.py
```

**Refreshing the recorded answer** (dev only; test RFCs and a test UUID, so nothing to scrub):

```sh
uv run python tools/record_sat_consulta.py
```

The API is in [contracts/public-api.md](contracts/public-api.md); the mapping, transport outcomes
and simulated status are in [data-model.md](data-model.md).

## Scenario 1 (P1): ask the SAT

```python
from mictlanix.cfdi.sat import SatConsultaClient, SatStatusClient

sat: SatStatusClient = SatConsultaClient()
status = await sat.query_status('EKU9003173C9', 'URE180429TM6', uuid, Decimal('116.00'))
```

| Replayed answer | Result |
|-----------------|--------|
| `consulta_no_encontrado.xml` (recorded) | `NOT_FOUND / NOT_CANCELLABLE / NONE` |
| synthetic, one per row of data model §3 (`Vigente` / `Cancelado` × each `EsCancelable` and `EstatusCancelacion` value) | the mapped `SatStatus` |
| synthetic, a value outside the mapping | `SatRejected('SAT-ANSWER', …)` |
| a SOAP Fault | `SatRejected('SOAP-FAULT', …)`, without the fault text |
| DNS, refused or TLS failure; a bad port | `SatUnavailable` |
| read timeout, reset, HTTP 500 without a Fault, an HTML body | `SatTimeout` |
| `uuid='nope'` | not found, no request sent |
| `SatConsultaSettings(url='http://…')`, a timeout ≤ 0 | `ValueError` naming the field |

The request sent carries SOAPAction `http://tempuri.org/IConsultaCFDIService/Consulta` and the
expression `?re=EKU9003173C9&rr=URE180429TM6&tt=116.0&id=<uuid>`.

## Scenario 2 (P2): follow a cancellation with the simulator

```python
from mictlanix.cfdi.pac import SimulatedPac
from mictlanix.cfdi.sat import SimulatedSatStatusClient

pac = SimulatedPac(clock=clock)
sat = SimulatedSatStatusClient(pac)
```

| Steps with `pac` | `await sat.query_status(...)` |
|------------------|-------------------------------|
| stamp, under 24 hours | `VALID / WITHOUT_ACCEPTANCE / NONE` |
| stamp, 24 hours later | `VALID / WITH_ACCEPTANCE / NONE` |
| cancel under 24 hours (accepted) | `CANCELLED / WITHOUT_ACCEPTANCE / ACCEPTED` |
| cancel after 24 hours (pending) | `VALID / WITH_ACCEPTANCE / PENDING` |
| … then `answer_as_receiver` accept / reject / expire | `CANCELLED / … / ACCEPTED`, `VALID / … / REJECTED`, `CANCELLED / … / EXPIRED` |
| configured not cancellable, then cancel | `VALID / NOT_CANCELLABLE / NONE` |
| other RFCs or total, or a malformed UUID | `NOT_FOUND / NOT_CANCELLABLE / NONE` |
| a UUID never stamped | `VALID / WITH_ACCEPTANCE / NONE` |

## Regression

After the transport moves to `mictlanix.cfdi._soap`, the Multifacturas and simulated PAC tests
pass with only two kinds of change: the replay fixture patches the new seam, and the transport
tests of `tests/pac/test_soap.py` call the shared module and expect the private exceptions, while
its PAC mapping tests keep expecting the PAC errors.
