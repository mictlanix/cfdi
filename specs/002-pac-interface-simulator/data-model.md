# Data Model: Generic PAC Client Interface and a Simulated PAC

All values are frozen, keyword-only dataclasses or `StrEnum`s. Datetimes are naive Mexico City
time, as everywhere in the library. Decisions are in [research.md](research.md); the exact
exports are in [contracts/public-api.md](contracts/public-api.md).

> **Amended by feature 003 (mictlanix/cfdi#3), 2026-11-18:** `query_status` and its values
> (`SatStatus`, `SatState`, `Cancellability`, `CancellationStatus`) were removed from `PacClient`
> and `SimulatedPac`. The SAT's status service does not depend on the PAC; a PAC-independent
> client for it is tracked in mictlanix/cfdi#6. The requirements below that concern the SAT
> status are superseded; the simulator still keeps that state to decide its answers.

## 1. Interface values

| Entity | Fields | Rules |
|--------|--------|-------|
| `Stamp` | `xml: bytes`, `timbre: tfd11.TimbreFiscalDigital` | `xml` is the full stamped document with the TFD inside `cfdi:Complemento`; `timbre.UUID` is upper case and `timbre.FechaTimbrado` naive Mexico City time (R4); `repr` is `Stamp(xml=<N bytes>, timbre=...)`, never the XML |
| `CsdCredentials` | `certificate: bytes` (DER), `private_key: bytes` (encrypted PKCS#8, DER), `password: str` | `repr` is `CsdCredentials(certificate=<N bytes>, private_key=<hidden>, password=<hidden>)`; not validated (R5) |
| `CancellationRequest` | `issuer_rfc: str`, `recipient_rfc: str`, `uuid: str`, `total: Decimal`, `reason: str`, `substitute_uuid: str \| None = None`, `csd: CsdCredentials` | Construction raises `ValidationError` (R6): `reason` not in 01–04 → `cancellation-reason`; 01 without `substitute_uuid` → `cancellation-substitute-required`; 02–04 with it → `cancellation-substitute-forbidden`; `uuid` or `substitute_uuid` not `8-4-4-4-12` hex (any case) → `uuid-format`. Every violation has `node='CancellationRequest'` and `attribute` = the field name. Its `repr` shows the `csd` through its own `repr` |
| `SatStatus` | `state: SatState`, `cancellability: Cancellability`, `cancellation: CancellationStatus` | — |

## 2. Enums (R8)

| Enum | Members (value) |
|------|-----------------|
| `CancellationAnswer` | `ACCEPTED` (`accepted`), `PENDING` (`pending`), `NOT_CANCELLABLE` (`not_cancellable`) |
| `SatState` | `VALID` (`valid`), `CANCELLED` (`cancelled`), `NOT_FOUND` (`not_found`) |
| `Cancellability` | `WITHOUT_ACCEPTANCE` (`without_acceptance`), `WITH_ACCEPTANCE` (`with_acceptance`), `NOT_CANCELLABLE` (`not_cancellable`) |
| `CancellationStatus` | `NONE` (`none`), `REQUESTED` (`requested`), `PENDING` (`pending`), `ACCEPTED` (`accepted`), `REJECTED` (`rejected`), `EXPIRED` (`expired`) |
| `StampOutcome` | `STAMPED` (`stamped`), `REJECTED` (`rejected`), `UNAVAILABLE` (`unavailable`), `TIMEOUT_STAMPED` (`timeout_stamped`), `TIMEOUT_NOT_STAMPED` (`timeout_not_stamped`) |
| `CancellationOutcome` | `ACCEPTED` (`accepted`), `PENDING` (`pending`), `NOT_CANCELLABLE` (`not_cancellable`), `REJECTED` (`rejected`), `UNAVAILABLE` (`unavailable`), `TIMEOUT` (`timeout`) |
| `ReceiverAnswer` | `ACCEPT` (`accept`), `REJECT` (`reject`), `EXPIRE` (`expire`) |

## 3. Errors (R7)

| Error | Base | Carries | Meaning |
|-------|------|---------|---------|
| `PacError` | `CfdiError` | — | Base of everything a `PacClient` operation raises |
| `PacRejected` | `PacError` | `code: str`, `message: str` | The PAC or the SAT refused; nothing was done. `str` is `'{code}: {message}'` |
| `PacUnavailable` | `PacError` | — | The request did not reach the PAC; nothing was done; retrying is safe |
| `PacTimeout` | `PacError` | — | The outcome is unknown; resolve with `find_stamp` or `query_status` |

## 4. Simulator records (private, stored as JSON strings, R9)

| Key | Fields |
|-----|--------|
| `seal:<sha256 hex of Sello>` (written after the `uuid:` record) | `next_stamp` (outcome or null), `code`, `message`, `stamped_xml` (UTF-8 text or null) |
| `uuid:<UUID upper case>` | `issuer_rfc`, `recipient_rfc`, `total` (decimal text), `stamped_at` (ISO text), `state`, `cancellability` (null = by age; set when a cancellation goes pending or is configured not cancellable), `cancellation`, `next_cancellation`, `code`, `message` |

A UUID with no record is a document stamped elsewhere (R12): valid, with acceptance, cancellation
`none`, RFCs and total unchecked. Configuring a cancellation for it, or a request that changes its
state (pending, cancelled, not cancellable), creates its record without RFCs, total or stamp
date.

## 5. Transitions

**Stamp** (per sealed document; a configured outcome is consumed by the call). Input is checked
first, in the order of research.md R11 (`301`, `302`, `301`; the lookup by seal then decides
"already stamped?" and exempts this PAC's own TFD from `307`); invalid input is rejected before
any configured outcome, which then stays for the next call. Valid input then follows this table:

| Configured | Already stamped? | Result | Afterwards `find_stamp` |
|------------|------------------|--------|--------------------------|
| none / `STAMPED` | no | new `Stamp` (and the `uuid:` record) | that stamp |
| none / `STAMPED` | yes | the existing `Stamp` | that stamp |
| `REJECTED` | either | `PacRejected(code, message)` | unchanged |
| `UNAVAILABLE` | either | `PacUnavailable` | unchanged |
| `TIMEOUT_STAMPED` | no / yes | stamps (or keeps) then `PacTimeout` | the stamp |
| `TIMEOUT_NOT_STAMPED` | either | `PacTimeout` | unchanged (`None` if never stamped) |

**Cancellation** (per UUID; state shown as state / cancellability / cancellation):

```text
valid / by age / none
  ├─ request, without_acceptance or ACCEPTED ─────▶ answer accepted   → cancelled / by age / accepted
  ├─ request, with_acceptance, or PENDING ────────▶ answer pending    → valid / with_acceptance / pending
  ├─ request, NOT_CANCELLABLE ────────────────────▶ answer not_cancellable → valid / not_cancellable / none
  ├─ request, TIMEOUT ────────────────────────────▶ PacTimeout        → valid / with_acceptance / pending
  └─ request, REJECTED / UNAVAILABLE ─────────────▶ PacRejected / PacUnavailable, unchanged

valid / with_acceptance / pending
  ├─ receiver ACCEPT ─▶ cancelled / with_acceptance / accepted
  ├─ receiver REJECT ─▶ valid / with_acceptance / rejected   (a new request follows the first
  │                     block: nothing configured or PENDING → pending; ACCEPTED → cancelled /
  │                     with_acceptance / accepted; NOT_CANCELLABLE → valid / not_cancellable /
  │                     rejected, the cancellation status kept)
  ├─ receiver EXPIRE ─▶ cancelled / with_acceptance / expired
  └─ request again ───▶ answer pending, unchanged

cancelled / (unchanged) / accepted or expired
  └─ request again ───▶ answer accepted, unchanged
```

Cancellability is `with_acceptance` from the moment a cancellation goes pending (by age, a
configured `PENDING` or a `TIMEOUT`) and stays so afterwards, whatever the stamp's age: the SAT is
waiting for, or has heard from, the recipient. `NOT_CANCELLABLE` sets `not_cancellable`. Otherwise
it is by age: `without_acceptance` under 24 hours, `with_acceptance` from then on, and
`with_acceptance` for a UUID stamped elsewhere.

Without a configured outcome, the answer to a request follows the cancellability the status
would report at that moment: `without_acceptance` → accepted at once, `with_acceptance` →
pending, `not_cancellable` → not cancellable. So a document under 24 hours old whose pending
cancellation the recipient rejected goes pending again, not cancelled at once.

On a document already pending, or cancelled (accepted or expired), a configured `ACCEPTED`,
`PENDING` or `NOT_CANCELLABLE` is used up and the answer reflects the current state (pending, or
accepted), unchanged; a configured `REJECTED`, `UNAVAILABLE` or `TIMEOUT` raises its error and
changes nothing. The same holds for a document answered not cancellable: a request answers not
cancellable again, a configured `ACCEPTED`, `PENDING` or `NOT_CANCELLABLE` is used up without
effect, and a configured `REJECTED`, `UNAVAILABLE` or `TIMEOUT` raises and changes nothing. So
configured answers (`ACCEPTED`, `PENDING`, `NOT_CANCELLABLE`) apply only to a valid document with
no cancellation pending that is not marked not cancellable.

A cancellation request is checked in this order: RFCs and total against the stamped UUID's record
(a mismatch raises `PacRejected('205', ...)` and leaves any configured outcome for the next
request), then the configured outcome, then the rules above.

A status query for a UUID that is not well-formed answers `not_found / not_cancellable / none`,
as the SAT does (a cancellation request cannot hold one, FR-008).

A status query whose issuer RFC, recipient RFC or total does not match a stamped UUID's record
answers `not_found / not_cancellable / none`; a cancellation request with the same mismatch raises
`PacRejected('205', ...)`.
