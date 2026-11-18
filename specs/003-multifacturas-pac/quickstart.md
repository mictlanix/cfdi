# Quickstart: validating the Multifacturas client

**Prerequisites**:
- `uv sync`;
- the SAT's public test CSD in `tests/fixtures/csd/`;
- for the opt-in scenarios only, Multifacturas test-mode credentials.

**Offline** (the default):

```sh
uv run pytest -q tests/pac
uv run pytest -q
uv run ruff check && uv run ruff format --check && uv run mypy src
uv build
```

**Opt-in**, against the PAC's test mode. Nothing runs without these variables:

```sh
MULTIFACTURAS_USER=… MULTIFACTURAS_PASSWORD=… uv run pytest -q tests/pac/test_multifacturas_live.py
```

**Refreshing the recorded answers** (dev only; the output is scrubbed):

```sh
MULTIFACTURAS_USER=… MULTIFACTURAS_PASSWORD=… uv run python tools/record_multifacturas.py
```

The API is in [contracts/public-api.md](contracts/public-api.md), and the mappings and codes are in
[data-model.md](data-model.md).

## Scenario 1 (P1): swap the simulator for Multifacturas

```python
from mictlanix.cfdi.pac import MultifacturasPac, MultifacturasSettings, PacClient

pac: PacClient = MultifacturasPac(
    MultifacturasSettings(user=user, password=password, production=False)
)
stamp = await pac.stamp(sealed)
```

Expected, offline from the recorded answer and opt-in live:
- `stamp.timbre.UUID` is in upper case;
- `stamp.timbre.SelloCFD` equals the document's `Sello`;
- `timbre(read(stamp.xml))` equals `stamp.timbre` except that the PAC writes the UUID in lower
  case in the XML, which the stamp upper-cases;
- `await pac.stamp(sealed)` again returns the same UUID;
- `await pac.find_stamp(sealed)` is `None`.

## Scenario 2 (P1): errors

| Recorded answer or failure | Raised |
|----------------------------|--------|
| `2` / `301 - La estructura del comprobante es incorrecta.` | `PacRejected('301', 'La estructura del comprobante es incorrecta.')` |
| `2` / `CFDI40102 - …` (double-encoded) | `PacRejected('CFDI40102', 'El resultado de la digestión …')`, without the original string from `messageDetail` |
| synthetic `307` with `uuid`, `acuseSAT` returning the stamped CFDI | the existing `Stamp` |
| DNS, refused or TLS failure | `PacUnavailable` |
| read timeout, reset, HTTP 500 without a SOAP Fault, HTML body | `PacTimeout` |
| a SOAP Fault (with HTTP 500 or 200) | `PacRejected('SOAP-FAULT', …)` |
| `MultifacturasSettings(base_url='http://…')` | `ValueError` |

## Scenario 3 (P2): cancel

| Recorded answers | Result |
|------------------|--------|
| `cancelarCfdi` `0` + SAT `201` (synthetic) | `PENDING` |
| `0` + SAT `202` (synthetic) | `ACCEPTED` |
| `0` + SAT `205 No Existe` (recorded in test mode) | `PacRejected('205', 'No Existe')` |
| `10` / `CACFDI33 - Problemas con los campos.` (recorded) | `PacRejected('CACFDI33', …)` |

The request sent to the PAC carries `b64Cer`, `b64Key` and the CSD password, and no other CSD
data. No error's `str` or `repr` contains them.

## Scenario 4 (P3): balance

The recorded `saldo` answer (`0` / `saldo` 20) gives `await pac.balance() == 20`.
