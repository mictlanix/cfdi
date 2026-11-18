"""Opt-in tests against Multifacturas' test mode (produccion=NO).

Skipped unless MULTIFACTURAS_USER and MULTIFACTURAS_PASSWORD are set; they are the only tests in
the suite that use the network.
"""

import os
from collections.abc import Iterator
from datetime import timedelta
from decimal import Decimal

import pytest
from lxml import etree

from mictlanix.cfdi import CSD, _mexico, read, seal
from mictlanix.cfdi.pac import (
    CancellationRequest,
    CsdCredentials,
    MultifacturasPac,
    MultifacturasSettings,
    PacRejected,
)
from tests.conftest import invoice

USER = os.environ.get('MULTIFACTURAS_USER')
PASSWORD = os.environ.get('MULTIFACTURAS_PASSWORD')

pytestmark = pytest.mark.skipif(
    not (USER and PASSWORD),
    reason='set MULTIFACTURAS_USER and MULTIFACTURAS_PASSWORD to run against the test mode',
)


@pytest.fixture(autouse=True)
def _no_network() -> Iterator[None]:
    """These tests talk to the PAC; this replaces the suite's network block for this module."""
    yield


@pytest.fixture
def pac() -> MultifacturasPac:
    assert USER and PASSWORD
    return MultifacturasPac(MultifacturasSettings(user=USER, password=PASSWORD, production=False))


@pytest.fixture
def sealed(csd: CSD) -> bytes:
    fecha = _mexico.now() - timedelta(hours=1)
    return seal(invoice(totals=False, Fecha=fecha, Folio=fecha.strftime('%H%M%S')), csd)


async def test_stamping_twice_gives_one_stamp(pac: MultifacturasPac, sealed: bytes) -> None:
    first = await pac.stamp(sealed)
    assert first.timbre.UUID == first.timbre.UUID.upper()
    assert first.timbre.SelloCFD == etree.fromstring(sealed).get('Sello')
    assert read(first.xml).Complemento
    second = await pac.stamp(sealed)
    assert second.timbre.UUID == first.timbre.UUID
    assert await pac.find_stamp(sealed) is None


async def test_balance(pac: MultifacturasPac) -> None:
    assert isinstance(await pac.balance(), int)


async def test_cancelling_a_test_stamp(
    pac: MultifacturasPac, sealed: bytes, credentials: CsdCredentials
) -> None:
    stamp = await pac.stamp(sealed)
    request = CancellationRequest(
        issuer_rfc='EKU9003173C9',
        recipient_rfc='URE180429TM6',
        uuid=stamp.timbre.UUID,
        total=Decimal('116.00'),
        reason='02',
        csd=credentials,
    )
    with pytest.raises(PacRejected) as caught:
        await pac.request_cancellation(request)
    assert caught.value.code == '205'  # test stamps never reach the SAT
