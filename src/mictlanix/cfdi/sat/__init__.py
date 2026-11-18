"""The SAT's status of a CFDI, whichever PAC stamped it.

One asynchronous interface, ``SatStatusClient``, with its values and errors;
``SatConsultaClient`` asks the SAT's public status service and ``SimulatedSatStatusClient``
answers from a ``SimulatedPac``'s state.
"""

from mictlanix.cfdi.sat._errors import SatError, SatRejected, SatTimeout, SatUnavailable
from mictlanix.cfdi.sat._interface import (
    Cancellability,
    CancellationStatus,
    SatState,
    SatStatus,
    SatStatusClient,
)
from mictlanix.cfdi.sat.consulta import SatConsultaClient, SatConsultaSettings
from mictlanix.cfdi.sat.simulated import SimulatedSatStatusClient

__all__ = [
    'SatStatusClient',
    'SatStatus',
    'SatState',
    'Cancellability',
    'CancellationStatus',
    'SatError',
    'SatRejected',
    'SatUnavailable',
    'SatTimeout',
    'SatConsultaClient',
    'SatConsultaSettings',
    'SimulatedSatStatusClient',
]
