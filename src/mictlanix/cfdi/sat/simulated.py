"""A simulated SAT status: the ``SatStatusClient`` over a ``SimulatedPac``'s state, offline."""

from __future__ import annotations

from decimal import Decimal

from mictlanix.cfdi.pac import PacUnavailable, SimulatedPac
from mictlanix.cfdi.sat._errors import SatUnavailable
from mictlanix.cfdi.sat._interface import (
    Cancellability,
    CancellationStatus,
    SatState,
    SatStatus,
    SatStatusClient,
)


class SimulatedSatStatusClient:
    """The SAT's status as a simulated PAC's state says, for development and tests.

    It always agrees with what that simulated PAC stamped, cancelled and was answered as the
    recipient, including other instances sharing its store.
    """

    def __init__(self, pac: SimulatedPac) -> None:
        self._pac = pac

    def __repr__(self) -> str:
        return 'SimulatedSatStatusClient(<SimulatedPac>)'

    async def query_status(
        self, issuer_rfc: str, recipient_rfc: str, uuid: str, total: Decimal
    ) -> SatStatus:
        try:
            state, cancellability, cancellation = await self._pac._sat_status(
                issuer_rfc, recipient_rfc, uuid, total
            )
        except PacUnavailable:
            raise SatUnavailable() from None
        return SatStatus(
            state=SatState(state),
            cancellability=Cancellability(cancellability),
            cancellation=CancellationStatus(cancellation),
        )


def _conforms(client: SimulatedSatStatusClient) -> SatStatusClient:
    """Checked by ``mypy src``: the simulated client implements the interface."""
    return client
