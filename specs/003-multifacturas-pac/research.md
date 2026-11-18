# Research: Facturación México (Multifacturas) PAC Client

Sources:
- **The PAC's WSDLs:** `https://ws.multifacturas.com/pac/index.php?wsdl` and
  `https://ws.multifacturas.com/cancelacion2022/index.php?wsdl`, both fetched on 2026-11-18.
- **The current system's client:** mictlanix `dfacture-client` `DFactureClient40.cs`, called from
  mbe `Web/Helpers/CFDHelpers40.cs`.
- **The PAC's public examples:** `ejemplos.cfdi4.com.mx`.
- **Live calls to the PAC's test mode** (`produccion=NO`, 2026-11-18). These used the demo
  credentials the PAC publishes, the SAT's public test CSD and a test invoice, with the user's
  approval.
- **The SAT's public consultation service.** It was queried with a CFDI the user provided for SAT
  checks.

## R1. Endpoints and transport security

- **Decision**: one base URL, `https://ws.multifacturas.com`, with the paths `/pac/index.php`
  (stamping, retrieval, balance) and `/cancelacion2022/index.php` (cancellation). TLS always
  verifies certificates with the platform's default trust store. A base URL that is not `https`
  is refused when the settings are created.
- **Rationale**: both paths answer over verified TLS on that host (`ssl_verify_result=0`). The
  `facturacionmexico` hosts (`ws.`, `pac1.`) fail verification. Both WSDLs advertise
  `http://ws.multifacturas.com/...` as their `soap:address`. The current system works only because
  it disables certificate checks (`ServerCertificateValidationCallback => true`) and uses plain
  HTTP for cancellation; this client does neither.
- **Alternatives considered**: following the WSDL's HTTP address (rejected: plain text with
  credentials and CSD material); the `facturacionmexico` hosts with verification off (rejected:
  insecure).

## R2. A small hand-written SOAP 1.1 RPC client, no new dependency

- **Decision**: build the RPC/encoded envelopes by hand (four operations) and send them with the
  standard library's `http.client` over `ssl`. Each call runs in a worker thread
  (`asyncio.to_thread`) so the interface stays async. Answers are parsed with `lxml`, which is
  already a dependency, using the library's safe parser.
- **Rationale**:
  - The client uses four operations: `timbrar33b64`, `acuseSAT`, `saldo` and `cancelarCfdi`. Each
    takes flat string parameters, or one flat struct for `cancelarCfdi`. A SOAP library (zeep) or
    an async HTTP client (httpx) would be the library's first network dependency, for little gain
    (constitution VI).
  - `http.client` separates connecting from sending and waiting. That gives the error split the
    spec requires (FR-013):
    - `connect()` failures (DNS, refused, TLS) → `PacUnavailable`;
    - anything after the connection is open (sending, waiting, reading, a closed connection) →
      `PacTimeout`;
    - a SOAP Fault body, whatever the HTTP status → `PacRejected('SOAP-FAULT')`.
  - Two private functions: `_post` does the raw exchange (the test seam) and `call` builds the
    envelope, calls `_post` and parses the answer (data-model.md §2).
- **Alternatives considered**:
  - `zeep` (heavy, sync, more surface);
  - `httpx` (a new dependency; its async API would avoid the thread);
  - `urllib.request` (it wraps send-phase errors with connect-phase ones, so the phases can't be
    told apart).

## R3. Stamping: `timbrar33b64`, and the PAC returns an existing stamp itself

- **Decision**:
  - **Request**: stamp with `timbrar33b64(rfc=user, clave=password, xml=Base64 of the sealed XML,
    produccion='SI'|'NO')`.
  - **Success**: `codigo_mf_numero` `0` with a non-empty `cfdi`. Base64-decode `cfdi` and build the
    stamp with the private `stamp_of` (spec 002). It must carry the TFD, and its `SelloCFD` must
    equal the submitted document's `Sello`; anything else is a `PacRejected` with the library code
    `MF-ANSWER`.
  - **Duplicates**: if `codigo_mf_numero` is not `0` but the code parsed from the text is `307`
    ("previously stamped"), use the answer's `cfdi` when present. Otherwise fetch the stamp with
    `acuseSAT(uuid)` when the answer has a `uuid`. If neither yields a stamp, raise `PacTimeout`:
    the SAT has a stamp, but it can't be obtained now.
- **Rationale**: verified in test mode on 2026-11-18.
  - **First stamp**: answered `0 / [MODO PRUEBAS] OK` with `uuid` (lower case) and `cfdi`.
  - **Resubmission**: sending the same sealed document again answered `0` with the same UUID and
    the same stamped XML, served from the PAC's record (`servidor: 100000`, same execution time).
  - **No new stamp**: the PAC deduplicates by sealed document and returns the existing stamp
    without making a new one. That is the "already stamped" behaviour FR-006 needs.
  - **307 path**: the explicit 307 path covers a PAC that reports the duplicate instead; mbe
    reads the stamp back with `acuseSAT` in production. It is tested offline with a synthetic
    answer.
  - **Choice of operation**: `timbrar33b64` is the operation the current system uses for CFDI 4.0
    in production, despite its 3.3 description. It returns a typed struct, while `timbrar` and
    `timbrar64` return untyped `xsd:Array`s.
- **Alternatives considered**: `timbrar64` (untyped answer); `timbrar` (ISO-8859-1 XML).

## R4. find_stamp returns `None` (user decision, 2026-11-18), and constitution IV

- **Decision**: `find_stamp` checks its input like the simulator does (`PacRejected` 301/302 for
  input that is not a sealed CFDI 4.0) and returns `None` without calling the PAC.
- **Rationale**:
  - **No lookup by document**: the PAC can't look up a stamp by sealed document. `acuseSAT` and
    `factura_recupera_respaldo` need the UUID. In test mode `acuseSAT` answers just `200` and
    `factura_recupera_respaldo` answers `ERROR`.
  - **Safe re-stamp**: after a timeout the caller stamps again (spec 002), and R3 shows that the
    PAC answers a resubmission from its record. So the second call is a lookup by sealed document
    that never makes a second stamp.
  - **Principle IV**: constitution v1.1.0 (amended 2026-11-18 for this feature) admits resolving
    a timeout "by resubmitting the same sealed document to a PAC that answers a resubmission with
    the existing stamp", which is exactly this PAC's behaviour.
- **Alternatives considered**: raising an error (breaks swapping the client for the simulator);
  searching `factura_reporte` (bulk reports are out of scope, and its format is undocumented).

## R5. Error answers and the code map

- **Decision**:
  - **Code and message**: a `codigo_mf_numero` other than `0` is a `PacRejected`. Its code and
    message come from the answer's text, `codigo_mf_texto`:
    - Strip a leading `ERROR: `. If what remains is JSON, take its `message` field.
    - Repair the double-encoded UTF-8 when the text re-encodes cleanly (`digestiÃ³n` →
      `digestión`).
    - Split `"<CODE> - <message>"`. When the text has no such code, the code is
      `codigo_mf_numero`.
  - **Never passed on**: `messageDetail`, `mensaje_original_pac_json` and `mensaje_original`.
    For `CFDI40102`, `messageDetail` carries the document's whole original string, with its RFCs
    and names (FR-014).
- **Rationale**: the answers observed in test mode:
  - malformed XML: `2 / 301 - La estructura del comprobante es incorrecta.`;
  - a seal that does not verify: `2 / CFDI40102 - El resultado de la digestión …`;
  - a cancellation whose key does not match: `10 / ERROR: {"message":"CACFDI33 - Problemas con los
    campos.", …}`.
  The PAC's examples also name `CSF101` (not cancellable) and `40150` (invalid reason). Demo mode
  ignores the password, so a credential error can't be observed there. Any such code is passed on
  as-is.
- **Alternatives considered**: using `codigo_mf_numero` (`2`, `10`) as the code. It is too coarse
  for a caller to act on.

## R6. Cancellation: `cancelarCfdi` of `cancelacion2022`, the SAT's answer decides

- **Decision**:
  - **Request**: call `cancelarCfdi` with the struct `datos`, containing:
    - `usuario`, `pass`: the PAC user and password;
    - `accion='cancelar'`, `produccion='SI'|'NO'`;
    - `uuid`, `rfc` (issuer);
    - `password`: the CSD key's password;
    - `motivo`, and `folioSustitucion` (empty unless the reason is 01);
    - `b64Cer`, `b64Key`: the certificate DER and the encrypted PKCS#8 key, Base64.
    The recipient RFC and total are not sent; the service does not take them.
  - **PAC refusal**: a `codigo_mf_numero` other than `0` is a `PacRejected` (R5).
  - **On `0`**: the SAT's code (`codigo_respuesta_sat`, the same as the receipt's `EstatusUUID`)
    decides:
    - **`201`**, request received: `query_status` with the request's RFCs and total then decides:
      - `Cancelado` → accepted;
      - cancellation `En proceso` → pending;
      - `No cancelable` → not cancellable;
      - anything else, including a status query that fails → pending.
    - **`202`**, cancellation previously requested: query the status the same way. Accepted if
      cancelled, otherwise pending.
    - **Any other SAT code**: a `PacRejected` with the SAT code and `codigo_respuesta_sat_texto`
      (for example `205 No Existe`).
- **Rationale**:
  - **Same PAC as today**: the current system uses this service and these fields.
  - **The older operations can't be used**: the PAC service's `cancelar` and `cancela_ut8` take no
    SAT reason, so they can't make a 2022 cancellation. The CSD is sent as the PAC's examples show
    (Base64 `.cer` and `.key` plus the password), so `generar_pem` isn't needed.
  - **Observed in test mode**: the request reached the SAT, which answered `205 No Existe`, because
    test stamps never reach the SAT. A wrong key gave `10 / CACFDI33`.
  - **Why `201` needs a status query**: `201` does not say whether the cancellation was immediate
    or waits for the recipient. The SAT's status, the source of truth, does.
- **Alternatives considered**: `consultarCancelarCfdi` of the PAC for the status. It answered
  `1100` with `json_uuids: null` in test mode and is less direct than the SAT. Sending PEM through
  `generar_pem` was rejected because it isn't needed.

## R7. query_status from the SAT's public consultation service

- **Decision**:
  - **Request**: POST the SOAP `Consulta` to
    `https://consultaqr.facturaelectronica.sat.gob.mx/ConsultaCFDIService.svc` with the expression
    `?re=…&rr=…&tt=…&id=…`. `tt` is formatted with spec 001's `_qr_total`, and `fe` is omitted.
  - **`Estado`**: `Vigente` → valid, `Cancelado` → cancelled, `No Encontrado` (or a `CodigoEstatus`
    starting `N`) → not found / not cancellable / none.
  - **`EsCancelable`**: `Cancelable sin aceptación` → without acceptance, `Cancelable con
    aceptación` → with acceptance, `No cancelable` → not cancellable.
  - **`EstatusCancelacion`**:
    - empty → none;
    - `En proceso` → pending;
    - `Plazo vencido` → expired;
    - `Cancelado con aceptación` and `Cancelado sin aceptación` → accepted;
    - `Solicitud rechazada` → rejected.
  - **Unknown text**: a value outside these is a `PacRejected('SAT-ANSWER', …)`.
  - **Failures**: transport failures map as in R2.
- **Rationale**:
  - **Source of truth**: the SAT is authoritative (constitution I) and needs no credentials.
  - **Verified on 2026-11-18**: the query answers the same with and without `fe` (`S -
    Comprobante obtenido satisfactoriamente`, `Vigente`, `Cancelable sin aceptación`), so the
    interface's arguments are enough. Spec 001 verified `tt` with any number of trailing zeros.
  - **Reusable**: it is a private module, so the next PAC client can use it.
- **Alternatives considered**: the PAC's `consultarCancelarCfdi` (R6).

## R8. Balance: `saldo`

- **Decision**: `MultifacturasPac.balance()` calls `saldo(rfc, clave)` and returns the `saldo`
  field as an `int`. A code other than `0` is a `PacRejected`.
- **Rationale**: one call, observed in test mode as `0 / OK : MODO DEMO (SIEMPRE CON SALDO 20)`
  with `saldo: 20`. It is not part of `PacClient` (FR-011).

## R9. Settings and credentials

- **Decision**: a frozen keyword-only dataclass `MultifacturasSettings` with these fields:
  - `user`, `password`, `production: bool`;
  - `base_url='https://ws.multifacturas.com'`;
  - `sat_url='https://consultaqr.facturaelectronica.sat.gob.mx/ConsultaCFDIService.svc'`;
  - `connect_timeout=10.0`, `read_timeout=60.0`.

  Its `repr` hides the password. `__post_init__` refuses non-https URLs and non-positive timeouts
  with `ValueError`. The client is `MultifacturasPac(settings)`.
- **Rationale**:
  - **FR-002, FR-003, FR-004**: everything comes from the caller, nothing from the environment.
  - **Defaults**: the verified host and reasonable timeouts. A caller can override them, for
    example to point at a recorded server.
- **Alternatives considered**: positional constructor arguments (no single immutable value to
  print safely); reading environment variables (forbidden by FR-002).

## R10. Offline tests: recorded, scrubbed answers replayed through one seam

- **Decision**:
  - **Seam**: every HTTP exchange goes through one private function, `_post(url, action, body,
    settings) -> bytes`. Offline tests monkeypatch it to replay files from
    `tests/fixtures/multifacturas/` and to raise the transport errors.
  - **Recorder**: the dev-only `tools/record_multifacturas.py` records the fixtures from the PAC's
    test mode. Its credentials come from `MULTIFACTURAS_USER` and `MULTIFACTURAS_PASSWORD`.
  - **Scrubbing**: the recorder replaces credentials, keeps the SAT's public test CSD and RFCs, and
    replaces other RFCs, including the PAC's own `RfcProvCertif`, with test RFCs. It blanks `png`
    and the `mensaje_original*` fields.
  - **Synthetic fixtures**: the 307 and SAT status fixtures are derived from recorded envelopes and
    marked as synthetic in the fixtures' README.
  - **Opt-in tests**: `tests/pac/test_multifacturas_live.py` runs only when both environment
    variables are set.
- **Rationale**: constitution II and III and FR-015/FR-016. One seam keeps the client free of
  test-only parameters.
- **Alternatives considered**:
  - a public `transport` parameter (API surface for tests only);
  - a local fake HTTPS server (certificate setup for no gain).
