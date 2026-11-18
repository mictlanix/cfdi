"""The SAT status interface and its values."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from typing import Protocol


class SatState(StrEnum):
    VALID = 'valid'
    CANCELLED = 'cancelled'
    NOT_FOUND = 'not_found'


class Cancellability(StrEnum):
    WITHOUT_ACCEPTANCE = 'without_acceptance'
    WITH_ACCEPTANCE = 'with_acceptance'
    NOT_CANCELLABLE = 'not_cancellable'


class CancellationStatus(StrEnum):
    NONE = 'none'
    PENDING = 'pending'
    ACCEPTED = 'accepted'
    REJECTED = 'rejected'
    EXPIRED = 'expired'


@dataclass(frozen=True, kw_only=True)
class SatStatus:
    """The SAT's status of one UUID."""

    state: SatState
    cancellability: Cancellability
    cancellation: CancellationStatus


NOT_FOUND = SatStatus(
    state=SatState.NOT_FOUND,
    cancellability=Cancellability.NOT_CANCELLABLE,
    cancellation=CancellationStatus.NONE,
)


class SatStatusClient(Protocol):
    """Answers the SAT's status of a CFDI. Raises only ``SatError`` subclasses."""

    async def query_status(
        self, issuer_rfc: str, recipient_rfc: str, uuid: str, total: Decimal
    ) -> SatStatus:
        """The SAT's current status of the UUID with these RFCs and total."""
        ...
