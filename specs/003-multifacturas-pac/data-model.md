# Data Model: Facturación México (Multifacturas) PAC Client

Decisions are in [research.md](research.md). The interface values (`Stamp`, `CancellationRequest`,
`CancellationAnswer`) are spec 002's.

## 1. Settings

| Field | Type | Default | Rules |
|-------|------|---------|-------|
| `user` | `str` | required | The PAC user (`rfc`/`usuario` in the PAC's operations) |
| `password` | `str` | required | The PAC password (`clave`/`pass`); never printed |
| `production` | `bool` | required | `True` sends `produccion='SI'`, `False` sends `'NO'` (test mode) |
| `base_url` | `str` | `'https://ws.multifacturas.com'` | MUST start with `https://`; paths `/pac/index.php` and `/cancelacion2022/index.php` are appended |
| `connect_timeout` | `float` | `10.0` | Seconds; > 0 |
| `read_timeout` | `float` | `60.0` | Seconds; > 0 |

`MultifacturasSettings` is a frozen, keyword-only dataclass. Its `__post_init__` raises
`ValueError` naming the field for a `base_url` that is not `https://` or a timeout ≤ 0. Its `repr`
is `MultifacturasSettings(user='…', password=<hidden>, production=…, base_url='…',
connect_timeout=…, read_timeout=…)`.

## 2. Transport outcomes (all operations, R2)

Two private functions in `_soap.py`:

- `_post(url, action, body, settings) -> bytes` performs the raw HTTPS exchange and maps transport
  failures. It is the one seam offline tests replace.
- `call(url, operation, params, settings) -> dict[str, str]` builds the envelope, calls `_post`,
  checks for a Fault and parses the return into its leaf fields. Replaying `_post` still exercises
  all of this.

| Where it fails | Error |
|----------------|-------|
| Name resolution, TCP connect, TLS handshake or certificate verification | `PacUnavailable` |
| Sending the request, waiting, reading, connection reset after connect, read timeout | `PacTimeout` |
| A body that is a SOAP Fault, whatever the HTTP status (SOAP 1.1 sends Faults with 500) | `PacRejected('SOAP-FAULT', <fixed message>)` (the fault text is not passed on) |
| Any other HTTP status than 200 | `PacTimeout` |
| A 200 body that is not a SOAP envelope with the expected return | `PacTimeout` |

Every error is raised `from None`.

## 3. Answer text → code and message (R5)

1. Start from `codigo_mf_texto`. Strip a leading `ERROR: `.
2. If what remains parses as a JSON object with a `message`, use `message`. `messageDetail` and
   `data` are dropped.
3. If the text re-encodes as Latin-1 and then decodes as UTF-8, use the decoded text. This repairs
   `digestiÃ³n` to `digestión`.
4. If the text matches `^(?P<code>[A-Z0-9]+) - (?P<message>.+)$`, use those two parts. Otherwise
   the code is `codigo_mf_numero` and the message is the text.

## 4. Stamp answers (`timbrar33b64`, R3)

The input is first checked as in spec 002 (`_input`): `301`/`302` `PacRejected` before any call.
The answer is read in this order:

| `codigo_mf_numero` | Parsed code | `cfdi` / `uuid` | Result |
|--------------------|-------------|-----------------|--------|
| `0` | — | `cfdi` decodes to a stamped CFDI 4.0 whose TFD `SelloCFD` is the input's `Sello` | `Stamp` (UUID upper case) |
| `0` | — | `cfdi` missing, not decodable, no TFD or another seal | `PacRejected('MF-ANSWER', …)` |
| ≠ `0` | `307` | `cfdi` valid as above | that `Stamp` |
| ≠ `0` | `307` | no `cfdi`, `uuid` present | `acuseSAT(uuid)`: a Base64 stamped CFDI checked as above (TFD, the input's seal) → that `Stamp`, one failing the check → `PacRejected('MF-ANSWER', …)`; anything else → `PacTimeout` |
| ≠ `0` | `307` | neither | `PacTimeout` |
| ≠ `0` | other | — | `PacRejected(code, message)` |

`find_stamp`: the input checks, then `None`; no call (R4).

## 5. Cancellation answers (`cancelarCfdi`, R6)

Request struct `datos`:
- `usuario`, `pass`: from the settings;
- `accion='cancelar'`, `produccion`;
- `uuid` (upper case), `rfc` = the request's `issuer_rfc`;
- `password` = `csd.password`;
- `motivo` = the request's `reason`;
- `folioSustitucion`: the request's `substitute_uuid`, or `''`;
- `b64Cer`, `b64Key`: Base64 of `csd.certificate` and `csd.private_key`.

| `codigo_mf_numero` | `codigo_respuesta_sat` | Result |
|--------------------|------------------------|--------|
| ≠ `0` | — | `PacRejected` per section 3 |
| `0` | `201` (request received) | `PENDING` |
| `0` | `202` (previously requested) | `ACCEPTED` |
| `0` | any other | `PacRejected(<SAT code>, codigo_respuesta_sat_texto)` (`SAT-ANSWER` when there is no code) |

The client never answers `NOT_CANCELLABLE`; whether a pending cancellation is accepted, rejected
or expires, or the document is not cancellable, is the SAT's status (mictlanix/cfdi#6).

## 6. SAT status answers (removed 2026-11-18)

The SAT's status query (`Consulta`) does not depend on the PAC and is no longer part of this
client or of the PAC interface; mictlanix/cfdi#6 tracks a PAC-independent client and carries the
mapping this section held.

## 7. Balance (`saldo`, R8)

`codigo_mf_numero` `0` → `int(saldo)`; otherwise → `PacRejected` per section 3; a non-integer
`saldo` → `PacRejected('MF-ANSWER', …)`.

## 8. Code map

| Code | Source | Meaning | Result |
|------|--------|---------|--------|
| `0` | PAC | Success | answer as above |
| `2` + `301` | PAC (SAT validation) | XML structure incorrect | `PacRejected('301', …)` |
| `2` + `CFDI40102` | PAC (SAT validation) | Seal does not verify | `PacRejected('CFDI40102', …)` |
| `307` | SAT via PAC | CFDI previously stamped | existing `Stamp` |
| `10` + `CACFDI33` | PAC (cancellation) | Fields problem, e.g. the certificate does not belong to the key | `PacRejected('CACFDI33', …)` |
| `CSF101` | PAC (cancellation, documented) | Cannot be cancelled | `PacRejected('CSF101', …)` |
| `40150` | PAC (cancellation, documented) | Invalid cancellation reason | `PacRejected('40150', …)` |
| `201` | SAT cancellation | Request received | `PENDING` |
| `202` | SAT cancellation | Previously requested | `ACCEPTED` |
| `203` | SAT cancellation | Issuer does not match | `PacRejected('203', …)` |
| `205` | SAT cancellation | UUID does not exist (observed in test mode) | `PacRejected('205', …)` |
| `MF-ANSWER` | library | Success answer without a usable stamp or balance | `PacRejected` |
| `SAT-ANSWER` | library | A cancellation answer without a SAT code | `PacRejected` |
| `SOAP-FAULT` | library | The service answered a SOAP Fault | `PacRejected` |
