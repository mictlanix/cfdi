# Contract: `mictlanix.cfdi.sat` public API

Everything below is exported from `mictlanix.cfdi.sat` and nothing else is (constitution v1.1.2,
principle V). The exports of `mictlanix.cfdi` and `mictlanix.cfdi.pac` do not change. Types are in
[../data-model.md](../data-model.md); decisions in [../research.md](../research.md).

## Exports

```python
# Interface
SatStatusClient,
SatStatus, SatState, Cancellability, CancellationStatus,
# Errors
SatError, SatRejected, SatUnavailable, SatTimeout,
# Clients
SatConsultaClient, SatConsultaSettings,
SimulatedSatStatusClient,
```

## The interface

```python
class SatStatusClient(Protocol):
    async def query_status(
        self, issuer_rfc: str, recipient_rfc: str, uuid: str, total: Decimal
    ) -> SatStatus
```

- It returns the status or raises a `SatError` subclass; nothing else escapes. Callers branch on
  the exception type and on `SatRejected.code`, never on text.
- No error or `repr` contains the raw answer.

## Values

```python
@dataclass(frozen=True, kw_only=True)
class SatStatus:
    state: SatState
    cancellability: Cancellability
    cancellation: CancellationStatus
```

The enumerations' members and values are in data model §1.

## Errors

```python
class SatError(CfdiError): ...
class SatRejected(SatError):
    code: str
    message: str
class SatUnavailable(SatError): ...  # the request was not sent; retrying is safe
class SatTimeout(SatError): ...      # the request was sent; no usable answer arrived
```

Codes the clients raise: `SAT-ANSWER` (a value outside the mapping), `SOAP-FAULT` (the service
answered a SOAP Fault; its text is not passed on).

## The SAT's service

```python
@dataclass(frozen=True, kw_only=True)
class SatConsultaSettings:
    url: str = 'https://consultaqr.facturaelectronica.sat.gob.mx/ConsultaCFDIService.svc'
    connect_timeout: float = 10.0
    read_timeout: float = 60.0

class SatConsultaClient:  # implements SatStatusClient
    def __init__(self, settings: SatConsultaSettings | None = None) -> None
```

- Settings raise `ValueError` naming the field for a URL that is not `https://` or a timeout ≤ 0.
- HTTPS with certificate verification; nothing is read from the environment; no credentials.
- A UUID that is not well formed returns not found without a request.
- Answer mapping and transport outcomes: data model §3 and §4.

## Simulated

```python
class SimulatedSatStatusClient:  # implements SatStatusClient
    def __init__(self, pac: SimulatedPac) -> None
```

- Answers from the simulated PAC's state (data model §5), so it always agrees with what that
  simulated PAC stamped, cancelled and was answered as recipient.
- A failure of the simulated PAC's store is `SatUnavailable`.
