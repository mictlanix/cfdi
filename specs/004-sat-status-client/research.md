# Research: Generic SAT CFDI Status Client

Sources:
- **mictlanix/cfdi#6** and its decision comment (2026-11-18): the request, the expression and the
  mapping that feature 003 verified, and the design (a client of its own, outside `PacClient`).
- **A live call to the SAT's service** on 2026-11-18 with the SAT's test RFCs and a test UUID
  (no credentials): HTTP 200, `ConsultaResponse/ConsultaResult` with the leaves `CodigoEstatus`
  (`N - 602: Comprobante no encontrado.`), `EsCancelable` (empty), `Estado` (`No Encontrado`),
  `EstatusCancelacion` (empty) and `ValidacionEFOS` (empty).
- **The code feature 003 merged**: `mictlanix.cfdi.pac._soap` (HTTPS transport, envelope parsing),
  `SimulatedPac` (the state it keeps per UUID), `mictlanix.cfdi._read._qr_total`.
- **Constitution v1.1.2**, principle V: the SAT status surface (protocol, values, enums, errors,
  every SAT status client) is exported from `mictlanix.cfdi.sat`, and only from there.

## R1. Module layout and exports

- **Decision**: a new package `mictlanix.cfdi.sat`:
  - `_errors.py`: `SatError(CfdiError)`, `SatRejected(code, message)`, `SatUnavailable`,
    `SatTimeout`;
  - `_interface.py`: `SatStatus`, `SatState`, `Cancellability`, `CancellationStatus` and the
    `SatStatusClient` protocol;
  - `consulta.py`: `SatConsultaSettings` and `SatConsultaClient`, the real client;
  - `simulated.py`: `SimulatedSatStatusClient`;
  - `__init__.py` exports exactly those eleven names.
- **Rationale**: principle V, as amended to v1.1.2. The layout mirrors `mictlanix.cfdi.pac` (errors,
  interface, one module per client). `mictlanix.cfdi` and `mictlanix.cfdi.pac` exports are
  unchanged.
- **Alternatives considered**: names after the PAC side (`SatStatusService`) or the service
  (`ConsultaCfdiClient`). `SatConsultaClient` names both the SAT and its service, `Consulta`, and
  leaves `SatStatusClient` for the protocol, as the constitution names it.

## R2. A shared HTTPS transport

- **Decision**: move the transport out of `mictlanix.cfdi.pac._soap` into a shared private module,
  `mictlanix.cfdi._soap`:
  - `_post(url, action, body, timeouts) -> bytes`: the HTTPS exchange, and the one seam the offline
    tests replace. `timeouts` is anything with `connect_timeout` and `read_timeout` (a protocol),
    which both settings classes satisfy.
  - `answer(raw) -> etree._Element`: the first child of the envelope's body.
  - It raises three private exceptions, `Unreachable`, `NoAnswer` and `Fault`, with no message.
  - `mictlanix.cfdi.pac._soap` keeps the RPC envelope, `fields`, `error_of` and `call`, and maps the
    three to `PacUnavailable`, `PacTimeout` and `PacRejected('SOAP-FAULT', …)`; the SAT client maps
    them to its own errors the same way. Every mapping is raised `from None`.
- **Rationale**: FR-011 (reuse, no new dependency) and FR-006 (the SAT's own errors). The transport
  stops knowing which family of errors it serves. The PAC client's behaviour is unchanged, and its
  tests keep passing with the replay seam moved to `mictlanix.cfdi._soap._post`.
- **Alternatives considered**:
  - The SAT client calls `mictlanix.cfdi.pac._soap._post` and translates the PAC errors: a SAT
    module would depend on PAC error types for its transport.
  - `_post` takes the error classes as an argument: three constructor parameters on every call
    for what three private exceptions say.

## R3. The request

- **Decision**:
  - POST to `settings.url`, default
    `https://consultaqr.facturaelectronica.sat.gob.mx/ConsultaCFDIService.svc`, with SOAPAction
    `http://tempuri.org/IConsultaCFDIService/Consulta`.
  - The body is a document/literal SOAP 1.1 envelope:
    `<tem:Consulta xmlns:tem="http://tempuri.org/"><tem:expresionImpresa>…</tem:expresionImpresa></tem:Consulta>`.
  - The expression is `?re={issuer}&rr={recipient}&tt={_qr_total(total)}&id={uuid}`, XML-escaped,
    with the UUID as given; no `fe`.
  - A UUID that does not match the 8-4-4-4-12 hex pattern returns not found before any request.
  - The call runs in a worker thread (`asyncio.to_thread`), as the PAC clients do.
- **Rationale**: verified in feature 003 and again on 2026-11-18 (above); spec 001 verified `tt`
  with any number of trailing zeros. `_qr_total` is the verification QR's formatting (FR-004).
- **Alternatives considered**: sending `fe` (the last 8 characters of the seal): the answer does not
  change, and the arguments do not include the seal.

## R4. Reading the answer

- **Decision**: take the leaves of `ConsultaResult` by local name, absent or nil as empty, then:
  - `CodigoEstatus` starting with `N`, or `Estado` `No Encontrado` → not found / not cancellable /
    none, whatever the other fields say;
  - otherwise `Estado`, `EsCancelable` and `EstatusCancelacion` each through its table (data model
    §3); a value outside its table → `SatRejected('SAT-ANSWER', 'unexpected SAT status')`;
  - `ValidacionEFOS` is ignored.
- **Rationale**: FR-005, never a guess. The live answer above shows the empty-element form of the
  not-found answer.
- **Alternatives considered**: mapping unknown values to the nearest known one: a guess, which the
  spec forbids.

## R5. Errors

- **Decision**: `SatError(CfdiError)` with `SatRejected(code: str, message: str)`,
  `SatUnavailable()` and `SatTimeout()`, mirroring spec 002's PAC errors: the same fixed messages
  with "the SAT" for "the PAC", and `SatRejected` printing `code: message`. Codes the client raises:
  `SAT-ANSWER` (a value outside the mapping) and `SOAP-FAULT` (a SOAP Fault, without its text).
  Transport mapping as for the PAC (003 data model §2): before the connection opens, unavailable;
  after it, a timeout, including a non-200 status without a Fault and a body that is not an
  envelope.
- **Rationale**: FR-006, clarified with the user on 2026-11-18 (the SAT's own errors).
- **Alternatives considered**: the PAC errors (rejected by the user).

## R6. The simulated status client

- **Decision**: `SimulatedSatStatusClient(pac: SimulatedPac)`. It asks the simulated PAC, through a
  private method `SimulatedPac._sat_status(issuer, recipient, uuid, total) -> tuple[str, str, str]`
  that runs under the simulated PAC's lock, for the state, cancellability and cancellation status
  as stored strings, and returns them as a `SatStatus`. The method is spec 002's `query_status` as
  it was before 003 removed it: the 24-hour rule from the simulated PAC's clock, mismatches and
  malformed UUIDs as not found, a UUID never stamped as valid and stamped elsewhere. A
  `PacUnavailable` from the simulated PAC's store becomes `SatUnavailable`.
- **Rationale**: FR-007 and FR-008. One state, one lock and one clock, so the two always agree
  (also across instances sharing one store). The simulated PAC keeps its private enums and does not
  import `mictlanix.cfdi.sat`, so the packages do not import each other in a cycle: `sat` depends
  on `pac`, never the reverse.
- **Alternatives considered**:
  - `SimulatedPac` implements `SatStatusClient` itself (the first decision on #6): it would export a
    SAT status client from `mictlanix.cfdi.pac`, against principle V.
  - A simulated client over the simulated PAC's store: it would duplicate the 24-hour rule and the
    record format outside the simulator.

## R7. Settings

- **Decision**: `SatConsultaSettings`, a frozen keyword-only dataclass: `url` (default the SAT's
  service), `connect_timeout=10.0`, `read_timeout=60.0`. `__post_init__` raises `ValueError` naming
  the field for a URL that is not `https://` or a timeout ≤ 0. `SatConsultaClient(settings=None)`
  uses the defaults when none is given.
- **Rationale**: FR-003; the same rules and defaults as `MultifacturasSettings`. There are no
  credentials, so the default `repr` is fine.

## R8. Offline and live tests

- **Decision**:
  - Fixtures in `tests/fixtures/sat/`: `consulta_no_encontrado.xml` recorded from the live service
    (test RFCs, a test UUID, so nothing to scrub), and synthetic answers derived from it for every
    other row of the mapping and one value outside it, written by a dev-only
    `tools/record_sat_consulta.py` with a README listing each file.
  - `tests/sat/conftest.py` has its own small replay fixture patching `mictlanix.cfdi._soap._post`
    (the PAC tests' replay patches the same seam after the move) and re-exports the simulated PAC
    fixtures of `tests/pac/conftest.py` (`clock`, `make_sealed`) for the simulated client's tests.
  - A live test, `tests/sat/test_consulta_live.py`, runs only when `SAT_CONSULTA_LIVE=1` and asks
    the SAT about the test UUID: not found.
- **Rationale**: FR-010; test stamps never reach the SAT, so only the not-found answer can be
  recorded. The SAT needs no credentials, so the live switch is a flag, not a secret.
- **Alternatives considered**: a live test against a real CFDI given through a variable: possible
  later; the not-found query already proves the request and the parsing against the real service.
