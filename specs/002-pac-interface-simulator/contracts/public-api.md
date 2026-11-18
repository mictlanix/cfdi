# Contract: `mictlanix.cfdi.pac` public API

Everything below is exported from `mictlanix.cfdi.pac` and nothing else is. `mictlanix.cfdi`'s
exports do not change. Types are in [../data-model.md](../data-model.md); decisions in
[../research.md](../research.md).

## Exports

```python
# Interface
PacClient,
Stamp, CsdCredentials, CancellationRequest, SatStatus,
CancellationAnswer, SatState, Cancellability, CancellationStatus,
# Errors
PacError, PacRejected, PacUnavailable, PacTimeout,
# Simulated PAC
SimulatedPac, SimulatorStore, InMemoryStore,
StampOutcome, CancellationOutcome, ReceiverAnswer,
SIMULATED_PAC_RFC,
```

## The interface

```python
class PacClient(Protocol):
    async def stamp(self, sealed_xml: bytes) -> Stamp
    async def find_stamp(self, sealed_xml: bytes) -> Stamp | None
    async def request_cancellation(self, request: CancellationRequest) -> CancellationAnswer
    async def query_status(
        self, issuer_rfc: str, recipient_rfc: str, uuid: str, total: Decimal
    ) -> SatStatus
```

- Every operation either returns its result or raises a `PacError` subclass; nothing else
  escapes. Callers branch on the exception type and on `PacRejected.code`, never on text.
- `stamp`: a document the PAC already stamped returns its existing stamp. A real client whose PAC
  answers "previously stamped" (SAT 307) instead fetches and returns that stamp; #3 confirms how
  Multifacturas allows it.
- `find_stamp`: never stamps; `None` when the PAC has no stamp for that sealed document.
- `request_cancellation`: `PacTimeout` means the request may have reached the SAT; resolve it
  with `query_status`.
- No error, `repr` or log contains credentials, CSD material, a document's XML or a raw PAC
  payload.

## Values

```python
@dataclass(frozen=True, kw_only=True)
class Stamp:
    xml: bytes
    timbre: tfd11.TimbreFiscalDigital

@dataclass(frozen=True, kw_only=True)
class CsdCredentials:
    certificate: bytes
    private_key: bytes
    password: str

@dataclass(frozen=True, kw_only=True)
class CancellationRequest:
    issuer_rfc: str
    recipient_rfc: str
    uuid: str
    total: Decimal
    reason: str                      # '01', '02', '03' or '04'
    substitute_uuid: str | None = None
    csd: CsdCredentials

@dataclass(frozen=True, kw_only=True)
class SatStatus:
    state: SatState
    cancellability: Cancellability
    cancellation: CancellationStatus
```

`CancellationRequest(...)` raises `mictlanix.cfdi.ValidationError` with every violation at once
(`node='CancellationRequest'`, `attribute` = field, `rule` in `cancellation-reason`,
`cancellation-substitute-required`, `cancellation-substitute-forbidden`, `uuid-format`).

`repr(Stamp(...))` is `Stamp(xml=<N bytes>, timbre=<the TimbreFiscalDigital's repr>)`: the
document's XML, which carries the issuer's certificate, is never printed.

`repr(CsdCredentials(...))` is
`CsdCredentials(certificate=<N bytes>, private_key=<hidden>, password=<hidden>)`.

## Errors

```python
class PacError(CfdiError): ...
class PacRejected(PacError):
    code: str
    message: str
class PacUnavailable(PacError): ...
class PacTimeout(PacError): ...
```

## Simulated PAC

```python
SIMULATED_PAC_RFC = 'SIM010101SI0'

class SimulatorStore(Protocol):
    async def get(self, key: str) -> str | None
    async def set(self, key: str, value: str) -> None

class InMemoryStore:  # implements SimulatorStore with a dict
    ...

class SimulatedPac:  # implements PacClient
    def __init__(
        self,
        store: SimulatorStore | None = None,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None
    async def configure_stamp(
        self, sealed_xml: bytes, outcome: StampOutcome,
        *, code: str | None = None, message: str | None = None,
    ) -> None
    async def configure_cancellation(
        self, uuid: str, outcome: CancellationOutcome,
        *, code: str | None = None, message: str | None = None,
    ) -> None
    async def answer_as_receiver(self, uuid: str, answer: ReceiverAnswer) -> None
```

- `store`: where the state lives; a new `InMemoryStore` when omitted. Keys and values are the
  simulator's own (strings); a store only keeps them. Several `SimulatedPac`s over one store share
  stamps, cancellations and configured outcomes. One `SimulatedPac` serializes its own operations;
  separate instances (in one process or several) do not lock each other, so concurrent stamps of
  one new document through two instances can both stamp it. Share the instance within a process.
- `clock`: returns naive Mexico City time; defaults to the current time at UTC-6.
- A configured stamp outcome is used by the next `stamp` of that document only, and a configured
  cancellation outcome by the next `request_cancellation` of that UUID only; `find_stamp` and
  `query_status` neither use nor honour them. `code` and `message` apply to `REJECTED` (ignored
  otherwise), each defaulting on its own to `CFDI40999` and `Rechazo simulado`.
- `configure_cancellation` accepts any UUID string and compares it upper-cased; one that is not
  a well-formed UUID simply never matches a request.
- `answer_as_receiver` raises `PacRejected('SIM01', ...)` when the UUID has no pending
  cancellation.
- `stamp` and `find_stamp` both reject input that is not a well-formed, sealed CFDI 4.0 with
  `PacRejected`; no other exception escapes them.
- `find_stamp` of a document carrying a TFD this PAC has no record of returns `None`.
  `configure_stamp` rejects invalid input with the same codes as `stamp`.
- Rejection codes the simulator raises on its own: `301` (not bytes, not well-formed, not a CFDI
  4.0, not readable by the library, or without `Total`), `302` (no or blank `Sello`), `307`
  (already carries a TFD this PAC has no record of), `205` (RFCs or total do not match the
  stamped UUID), `SIM01` (nothing pending for the receiver).
- Exceptions raised by the store become `PacUnavailable`, raised `from None`.
- Behaviour per path: [../data-model.md](../data-model.md) section 5.
