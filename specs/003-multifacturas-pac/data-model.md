# Data Model: Facturación México (Multifacturas) PAC Client

Decisions are in [research.md](research.md). The interface values (`Stamp`, `CancellationRequest`,
`SatStatus` and the enums) are spec 002's.

## 1. Settings

| Field | Type | Default | Rules |
|-------|------|---------|-------|
| `user` | `str` | required | The PAC user (`rfc`/`usuario` in the PAC's operations) |
| `password` | `str` | required | The PAC password (`clave`/`pass`); never printed |
| `production` | `bool` | required | `True` sends `produccion='SI'`, `False` sends `'NO'` (test mode) |
| `base_url` | `str` | `'https://ws.multifacturas.com'` | MUST start with `https://`; paths `/pac/index.php` and `/cancelacion2022/index.php` are appended |
| `sat_url` | `str` | `'https://consultaqr.facturaelectronica.sat.gob.mx/ConsultaCFDIService.svc'` | MUST start with `https://` |
| `connect_timeout` | `float` | `10.0` | Seconds; > 0 |
| `read_timeout` | `float` | `60.0` | Seconds; > 0 |

`MultifacturasSettings` is a frozen, keyword-only dataclass. Its `__post_init__` raises
`ValueError` naming the field for a URL that is not `https://` or a timeout ≤ 0. Its `repr` is
`MultifacturasSettings(user='…', password=<hidden>, production=…, base_url='…', sat_url='…',
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
| `0` | `201` (request received) | `query_status(issuer, recipient, uuid, total)`, read as in the next table |
| `0` | `202` (previously requested) | the same status query: `Cancelado` → `accepted`, otherwise `pending` |
| `0` | any other | `PacRejected(<SAT code>, codigo_respuesta_sat_texto)` |

After a `201`, the status decides the answer:

| Status | Answer |
|--------|--------|
| state `cancelled` | `ACCEPTED` |
| cancellation `pending` | `PENDING` |
| cancellability `not_cancellable` | `NOT_CANCELLABLE` |
| anything else, or the status query raises `PacError` | `PENDING` |

## 6. SAT status answers (`Consulta`, R7)

The query sends the expression `?re={issuer}&rr={recipient}&tt={_qr_total(total)}&id={uuid}`,
XML-escaped. A UUID that is not well formed returns `not_found / not_cancellable / none` without a
call.

| SAT field | Value | Maps to |
|-----------|-------|---------|
| `CodigoEstatus` starting `N` or `Estado` `No Encontrado` | — | `NOT_FOUND / NOT_CANCELLABLE / NONE` |
| `Estado` | `Vigente` / `Cancelado` | `VALID` / `CANCELLED` |
| `EsCancelable` | `Cancelable sin aceptación` / `Cancelable con aceptación` / `No cancelable` | `WITHOUT_ACCEPTANCE` / `WITH_ACCEPTANCE` / `NOT_CANCELLABLE` |
| `EstatusCancelacion` | empty / `En proceso` / `Plazo vencido` / `Cancelado con aceptación` / `Cancelado sin aceptación` / `Solicitud rechazada` | `NONE` / `PENDING` / `EXPIRED` / `ACCEPTED` / `ACCEPTED` / `REJECTED` |

Any other value is `PacRejected('SAT-ANSWER', 'unexpected SAT status')`.

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
| `201` | SAT cancellation | Request received | status query decides |
| `202` | SAT cancellation | Previously requested | status query decides |
| `203` | SAT cancellation | Issuer does not match | `PacRejected('203', …)` |
| `205` | SAT cancellation | UUID does not exist (observed in test mode) | `PacRejected('205', …)` |
| `MF-ANSWER` | library | Success answer without a usable stamp or balance | `PacRejected` |
| `SAT-ANSWER` | library | Unexpected SAT status value | `PacRejected` |
| `SOAP-FAULT` | library | The service answered a SOAP Fault | `PacRejected` |
