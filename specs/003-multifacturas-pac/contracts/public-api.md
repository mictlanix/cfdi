# Contract: the Multifacturas client in `mictlanix.cfdi.pac`

This feature adds two exports to `mictlanix.cfdi.pac` and changes nothing else. Spec 002's
contract still lists everything else (`specs/002-pac-interface-simulator/contracts/public-api.md`).
The exports test of `mictlanix.cfdi.pac` reads both contracts.

## Exports

```python
MultifacturasPac, MultifacturasSettings,
```

## Settings

```python
@dataclass(frozen=True, kw_only=True)
class MultifacturasSettings:
    user: str
    password: str
    production: bool
    base_url: str = 'https://ws.multifacturas.com'
    sat_url: str = 'https://consultaqr.facturaelectronica.sat.gob.mx/ConsultaCFDIService.svc'
    connect_timeout: float = 10.0
    read_timeout: float = 60.0
```

- Construction raises `ValueError` naming the field for a URL that is not `https://` or a timeout
  ≤ 0.
- `repr` shows `password=<hidden>`.
- Nothing is read from the environment.

## Client

```python
class MultifacturasPac:  # implements PacClient
    def __init__(self, settings: MultifacturasSettings) -> None
    async def stamp(self, sealed_xml: bytes) -> Stamp
    async def find_stamp(self, sealed_xml: bytes) -> Stamp | None
    async def request_cancellation(self, request: CancellationRequest) -> CancellationAnswer
    async def query_status(
        self, issuer_rfc: str, recipient_rfc: str, uuid: str, total: Decimal
    ) -> SatStatus
    async def balance(self) -> int
```

- **`stamp`**:
  - Input that is not a sealed CFDI 4.0 is rejected before any call, as by `SimulatedPac` (`301`,
    `302`).
  - A document already stamped returns its existing stamp. Stamping again after a `PacTimeout` is
    the way to resolve the timeout; it never makes a second stamp.
- **`find_stamp`**: checks the input like `stamp` and returns `None` without calling the PAC. The
  PAC has no lookup by sealed document.
- **`request_cancellation`**: sends the PAC the CSD's certificate, encrypted key and password, the
  issuer RFC, the UUID, the reason and the substitute UUID. Data-model §5 explains how the answer
  is decided.
- **`query_status`**: answers from the SAT's public consultation service.
- **`balance`**: the PAC account's remaining stamps. It belongs to this client only.
- **Errors**: every operation returns its result or raises a `PacError` subclass, `from None`:
  - `PacUnavailable` when the connection could not be made;
  - `PacTimeout` after it was made;
  - `PacRejected` with the PAC's or the SAT's code and a short message.
- **Never exposed**: no error, `repr` or log contains the PAC password, the CSD material, the
  document's XML, or the PAC's `messageDetail` or raw payloads.
- **Codes**: [../data-model.md](../data-model.md) §8.
