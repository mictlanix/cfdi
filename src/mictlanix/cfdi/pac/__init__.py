"""Stamping and cancelling CFDI 4.0 documents through a PAC.

One asynchronous interface, ``PacClient``, with its values and errors; ``SimulatedPac`` implements
it offline.
"""

from mictlanix.cfdi.pac._errors import PacError, PacRejected, PacTimeout, PacUnavailable
from mictlanix.cfdi.pac._interface import (
    Cancellability,
    CancellationAnswer,
    CancellationRequest,
    CancellationStatus,
    CsdCredentials,
    PacClient,
    SatState,
    SatStatus,
    Stamp,
)
from mictlanix.cfdi.pac.simulated import (
    SIMULATED_PAC_RFC,
    CancellationOutcome,
    InMemoryStore,
    ReceiverAnswer,
    SimulatedPac,
    SimulatorStore,
    StampOutcome,
)

__all__ = [
    'PacClient',
    'Stamp',
    'CsdCredentials',
    'CancellationRequest',
    'SatStatus',
    'CancellationAnswer',
    'SatState',
    'Cancellability',
    'CancellationStatus',
    'PacError',
    'PacRejected',
    'PacUnavailable',
    'PacTimeout',
    'SimulatedPac',
    'SimulatorStore',
    'InMemoryStore',
    'StampOutcome',
    'CancellationOutcome',
    'ReceiverAnswer',
    'SIMULATED_PAC_RFC',
]
