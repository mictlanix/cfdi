"""User Story 3: the caller supplies the store, so several simulated PACs share one state."""

import asyncio
from decimal import Decimal
from typing import Any

import pytest

from mictlanix.cfdi import read
from mictlanix.cfdi.pac import (
    CancellationAnswer,
    CancellationOutcome,
    CancellationRequest,
    CsdCredentials,
    InMemoryStore,
    PacTimeout,
    PacUnavailable,
    ReceiverAnswer,
    SatState,
    SimulatedPac,
    StampOutcome,
)
from tests.pac.conftest import Clock, MakeSealed, assert_valid_stamp


class DictStore:
    """A caller's own store: only ``get`` and ``set``."""

    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self.values.get(key)

    async def set(self, key: str, value: str) -> None:
        self.values[key] = value


class YieldingStore(DictStore):
    """Suspends before every access, as a real shared store does."""

    async def get(self, key: str) -> str | None:
        await asyncio.sleep(0)
        return await super().get(key)

    async def set(self, key: str, value: str) -> None:
        await asyncio.sleep(0)
        await super().set(key, value)


class FailingStore(DictStore):
    def __init__(self, *, get: bool = False, set_after: int | None = None) -> None:
        super().__init__()
        self.fail_get = get
        self.set_after = set_after
        self.sets = 0

    async def get(self, key: str) -> str | None:
        if self.fail_get:
            raise RuntimeError(f'cannot read {key}')
        return await super().get(key)

    async def set(self, key: str, value: str) -> None:
        self.sets += 1
        if self.set_after is not None and self.sets > self.set_after:
            raise RuntimeError(f'cannot write {value}')
        await super().set(key, value)


def _request(stamp_xml: bytes, credentials: CsdCredentials) -> CancellationRequest:
    comprobante = read(stamp_xml)
    assert comprobante.Total is not None
    tfd = comprobante.Complemento[-1]
    return CancellationRequest(
        issuer_rfc=comprobante.Emisor.Rfc,
        recipient_rfc=comprobante.Receptor.Rfc,
        uuid=tfd.UUID,  # type: ignore[union-attr]
        total=comprobante.Total,
        reason='02',
        csd=credentials,
    )


async def test_two_simulators_over_one_store_share_stamps(
    make_sealed: MakeSealed, clock: Clock
) -> None:
    store = InMemoryStore()
    a, b = SimulatedPac(store, clock=clock), SimulatedPac(store, clock=clock)
    sealed = make_sealed()
    stamp = await a.stamp(sealed)
    assert_valid_stamp(stamp, sealed, clock.now)
    assert await b.find_stamp(sealed) == stamp
    assert await b.stamp(sealed) == stamp


async def test_a_stamp_outcome_configured_through_one_applies_through_the_other(
    make_sealed: MakeSealed, clock: Clock
) -> None:
    store = InMemoryStore()
    a, b = SimulatedPac(store, clock=clock), SimulatedPac(store, clock=clock)
    sealed = make_sealed()
    await b.configure_stamp(sealed, StampOutcome.TIMEOUT_NOT_STAMPED)
    with pytest.raises(PacTimeout):
        await a.stamp(sealed)


async def test_cancellations_are_shared(
    make_sealed: MakeSealed, clock: Clock, credentials: CsdCredentials
) -> None:
    store = InMemoryStore()
    a, b = SimulatedPac(store, clock=clock), SimulatedPac(store, clock=clock)
    sealed = make_sealed()
    stamp = await a.stamp(sealed)
    assert_valid_stamp(stamp, sealed, clock.now)
    request = _request(stamp.xml, credentials)
    await a.configure_cancellation(request.uuid, CancellationOutcome.PENDING)
    assert await b.request_cancellation(request) == CancellationAnswer.PENDING
    await b.answer_as_receiver(request.uuid, ReceiverAnswer.ACCEPT)
    for pac in (a, b):
        query = await pac.query_status(
            request.issuer_rfc, request.recipient_rfc, request.uuid, request.total
        )
        assert query.state == SatState.CANCELLED


async def test_simulators_without_a_store_share_nothing(
    make_sealed: MakeSealed, clock: Clock
) -> None:
    a, b = SimulatedPac(clock=clock), SimulatedPac(clock=clock)
    sealed = make_sealed()
    stamp = await a.stamp(sealed)
    assert_valid_stamp(stamp, sealed, clock.now)
    assert await b.find_stamp(sealed) is None


async def test_a_callers_own_store_works_the_same(make_sealed: MakeSealed, clock: Clock) -> None:
    store = DictStore()
    a, b = SimulatedPac(store, clock=clock), SimulatedPac(store, clock=clock)
    sealed = make_sealed()
    stamp = await a.stamp(sealed)
    assert_valid_stamp(stamp, sealed, clock.now)
    assert await b.find_stamp(sealed) == stamp
    assert store.values


async def test_concurrent_stamps_through_one_instance_make_one_stamp(
    make_sealed: MakeSealed, clock: Clock
) -> None:
    pac = SimulatedPac(YieldingStore(), clock=clock)
    sealed = make_sealed()
    first, second = await asyncio.gather(pac.stamp(sealed), pac.stamp(sealed))
    assert first == second
    assert_valid_stamp(first, sealed, clock.now)
    assert await pac.find_stamp(sealed) == first


UUID = '6A1B2C3D-4E5F-4061-8293-A4B5C6D7E8F9'


def _request_for(credentials: CsdCredentials) -> CancellationRequest:
    return CancellationRequest(
        issuer_rfc='A',
        recipient_rfc='B',
        uuid=UUID,
        total=Decimal('1'),
        reason='02',
        csd=credentials,
    )


def _assert_unavailable(error: PacUnavailable) -> None:
    assert error.__cause__ is None
    assert error.__suppress_context__


async def test_a_store_that_cannot_read_makes_every_operation_unavailable(
    make_sealed: MakeSealed, clock: Clock, credentials: CsdCredentials
) -> None:
    pac = SimulatedPac(FailingStore(get=True), clock=clock)
    sealed = make_sealed()
    calls: list[Any] = [
        pac.stamp(sealed),
        pac.find_stamp(sealed),
        pac.request_cancellation(_request_for(credentials)),
        pac.query_status('A', 'B', UUID, Decimal('1')),
        pac.configure_stamp(sealed, StampOutcome.STAMPED),
        pac.configure_cancellation(UUID, CancellationOutcome.ACCEPTED),
        pac.answer_as_receiver(UUID, ReceiverAnswer.ACCEPT),
    ]
    for call in calls:
        with pytest.raises(PacUnavailable) as caught:
            await call
        _assert_unavailable(caught.value)


async def test_a_store_that_cannot_write_makes_every_write_unavailable(
    make_sealed: MakeSealed, clock: Clock, credentials: CsdCredentials
) -> None:
    pac = SimulatedPac(FailingStore(set_after=0), clock=clock)
    sealed = make_sealed()
    calls: list[Any] = [
        pac.stamp(sealed),
        pac.request_cancellation(_request_for(credentials)),
        pac.configure_stamp(sealed, StampOutcome.STAMPED),
        pac.configure_cancellation(UUID, CancellationOutcome.ACCEPTED),
    ]
    for call in calls:
        with pytest.raises(PacUnavailable) as caught:
            await call
        _assert_unavailable(caught.value)


async def test_a_failure_between_the_two_writes_of_a_stamp(
    make_sealed: MakeSealed, clock: Clock
) -> None:
    store = FailingStore(set_after=1)
    pac = SimulatedPac(store, clock=clock)
    sealed = make_sealed()
    with pytest.raises(PacUnavailable):
        await pac.stamp(sealed)
    store.set_after = None
    assert await pac.find_stamp(sealed) is None
    stamp = await pac.stamp(sealed)
    assert_valid_stamp(stamp, sealed, clock.now)


class GarbageStore(DictStore):
    """Returns values that are not the simulator's own JSON objects."""

    def __init__(self, value: str) -> None:
        super().__init__()
        self.value = value

    async def get(self, key: str) -> str | None:
        return self.value


@pytest.mark.parametrize('value', ['not json', '[]'])
async def test_a_store_returning_garbage_makes_every_operation_unavailable(
    value: str, make_sealed: MakeSealed, clock: Clock, credentials: CsdCredentials
) -> None:
    pac = SimulatedPac(GarbageStore(value), clock=clock)
    sealed = make_sealed()
    calls: list[Any] = [
        pac.stamp(sealed),
        pac.find_stamp(sealed),
        pac.request_cancellation(_request_for(credentials)),
        pac.query_status('A', 'B', UUID, Decimal('1')),
        pac.configure_stamp(sealed, StampOutcome.STAMPED),
        pac.configure_cancellation(UUID, CancellationOutcome.ACCEPTED),
        pac.answer_as_receiver(UUID, ReceiverAnswer.ACCEPT),
    ]
    for call in calls:
        with pytest.raises(PacUnavailable) as caught:
            await call
        _assert_unavailable(caught.value)
