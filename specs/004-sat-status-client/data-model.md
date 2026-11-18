# Data Model: Generic SAT CFDI Status Client

Decisions are in [research.md](research.md); the exports are in
[contracts/public-api.md](contracts/public-api.md).

## 1. Values

`SatStatus` is a frozen, keyword-only dataclass: `state: SatState`,
`cancellability: Cancellability`, `cancellation: CancellationStatus`. The enumerations are
`StrEnum`s with these members and values, restored as spec 002 had them:

| Enum | Members (value) |
|------|-----------------|
| `SatState` | `VALID` (`valid`), `CANCELLED` (`cancelled`), `NOT_FOUND` (`not_found`) |
| `Cancellability` | `WITHOUT_ACCEPTANCE` (`without_acceptance`), `WITH_ACCEPTANCE` (`with_acceptance`), `NOT_CANCELLABLE` (`not_cancellable`) |
| `CancellationStatus` | `NONE` (`none`), `PENDING` (`pending`), `ACCEPTED` (`accepted`), `REJECTED` (`rejected`), `EXPIRED` (`expired`) |

Spec 002's `CancellationStatus.REQUESTED` does not come back: no answer of the SAT maps to it and
the simulator never recorded it (FR-002 lists five cancellation statuses).

The not-found value, `NOT_FOUND / NOT_CANCELLABLE / NONE`, is the same for both clients.

## 2. Settings

| Field | Type | Default | Rules |
|-------|------|---------|-------|
| `url` | `str` | `'https://consultaqr.facturaelectronica.sat.gob.mx/ConsultaCFDIService.svc'` | MUST start with `https://` |
| `connect_timeout` | `float` | `10.0` | Seconds; > 0 |
| `read_timeout` | `float` | `60.0` | Seconds; > 0 |

`SatConsultaSettings` is a frozen, keyword-only dataclass; `__post_init__` raises `ValueError`
naming the field for a URL that is not `https://` or a timeout ≤ 0.

## 3. Answer mapping (`ConsultaResult`, R4)

The leaves of `ConsultaResult` are read by local name; a missing or nil leaf is empty.

1. `CodigoEstatus` starts with `N`, or `Estado` is `No Encontrado` → `NOT_FOUND / NOT_CANCELLABLE /
   NONE`.
2. Otherwise each field through its table; a value outside it → `SatRejected('SAT-ANSWER',
   'unexpected SAT status')`.

| `Estado` | `SatState` |
|----------|------------|
| `Vigente` | `VALID` |
| `Cancelado` | `CANCELLED` |

| `EsCancelable` | `Cancellability` |
|----------------|------------------|
| `Cancelable sin aceptación` | `WITHOUT_ACCEPTANCE` |
| `Cancelable con aceptación` | `WITH_ACCEPTANCE` |
| `No cancelable` | `NOT_CANCELLABLE` |

| `EstatusCancelacion` | `CancellationStatus` |
|----------------------|----------------------|
| empty | `NONE` |
| `En proceso` | `PENDING` |
| `Plazo vencido` | `EXPIRED` |
| `Cancelado con aceptación` | `ACCEPTED` |
| `Cancelado sin aceptación` | `ACCEPTED` |
| `Solicitud rechazada` | `REJECTED` |

`ValidacionEFOS` is ignored.

## 4. Transport outcomes (R2, R5)

| Outcome | Error |
|---------|-------|
| The URL cannot be addressed (bad port, a host IDNA cannot encode), name resolution, connection or TLS failure | `SatUnavailable` |
| Read timeout, connection reset, any failure after the connection opened | `SatTimeout` |
| A SOAP Fault, whatever the HTTP status | `SatRejected('SOAP-FAULT', 'the service refused the request')` |
| An HTTP status other than 200 without a Fault, or a body that is not a SOAP envelope with a body | `SatTimeout` |

Every error is raised `from None` and carries no part of the answer.

## 5. Simulated status (R6)

`SimulatedSatStatusClient(pac).query_status(...)` returns what the simulated PAC's state says, read
under its lock:

| Situation | `SatStatus` |
|-----------|-------------|
| UUID not well formed | `NOT_FOUND / NOT_CANCELLABLE / NONE` |
| A UUID the simulated PAC stamped, with other RFCs or another total | `NOT_FOUND / NOT_CANCELLABLE / NONE` |
| Otherwise | state and cancellation status as recorded (default `VALID` / `NONE`); cancellability as recorded, or from the clock: `WITHOUT_ACCEPTANCE` under 24 hours since stamping, `WITH_ACCEPTANCE` from then on or when the stamp date is unknown (a UUID stamped elsewhere) |

The records change only through `SimulatedPac` (spec 002 data model §5): an accepted cancellation
records cancelled / accepted, a pending one pending with acceptance, not cancellable records the
cancellability, and the recipient's answers record cancelled / accepted, valid / rejected or
cancelled / expired. A store failure is `SatUnavailable`.
