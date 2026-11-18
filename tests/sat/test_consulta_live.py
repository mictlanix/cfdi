"""Opt-in test against the SAT's status service. It needs no credentials.

Skipped unless SAT_CONSULTA_LIVE=1; with it, this module may use the network.
"""

import os
from collections.abc import Iterator
from decimal import Decimal

import pytest

from mictlanix.cfdi.sat import (
    Cancellability,
    CancellationStatus,
    SatConsultaClient,
    SatState,
    SatStatus,
)

pytestmark = pytest.mark.skipif(
    os.environ.get('SAT_CONSULTA_LIVE') != '1',
    reason='set SAT_CONSULTA_LIVE=1 to ask the SAT',
)


@pytest.fixture(autouse=True)
def _no_network() -> Iterator[None]:
    """This test asks the SAT; this replaces the suite's network block for this module."""
    yield


async def test_the_sat_does_not_know_a_test_uuid() -> None:
    status = await SatConsultaClient().query_status(
        'EKU9003173C9', 'URE180429TM6', '939513EF-CEAA-4E44-9AD9-6224778D9A9D', Decimal('116.00')
    )
    assert status == SatStatus(
        state=SatState.NOT_FOUND,
        cancellability=Cancellability.NOT_CANCELLABLE,
        cancellation=CancellationStatus.NONE,
    )
