"""User Story 2: following a cancellation with the simulated PAC and its simulated SAT status."""

from dataclasses import dataclass
from datetime import timedelta
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
    ReceiverAnswer,
    SimulatedPac,
)
from mictlanix.cfdi.sat import (
    Cancellability,
    CancellationStatus,
    SatConsultaClient,
    SatState,
    SatStatus,
    SatStatusClient,
    SatUnavailable,
    SimulatedSatStatusClient,
)
from tests.pac.conftest import Clock, MakeSealed

NEVER_STAMPED = '6A1B2C3D-4E5F-4061-8293-A4B5C6D7E8F9'


def status(state: str, cancellability: str, cancellation: str) -> SatStatus:
    return SatStatus(
        state=SatState(state),
        cancellability=Cancellability(cancellability),
        cancellation=CancellationStatus(cancellation),
    )


NOT_FOUND = status('not_found', 'not_cancellable', 'none')


@dataclass
class Doc:
    """A document the simulated PAC stamped, and the values a cancellation and a query need."""

    pac: SimulatedPac
    sat: SimulatedSatStatusClient
    credentials: CsdCredentials
    uuid: str
    issuer: str
    recipient: str
    total: Decimal

    async def status(self, **changes: Any) -> SatStatus:
        values: dict[str, Any] = {
            'issuer_rfc': self.issuer,
            'recipient_rfc': self.recipient,
            'uuid': self.uuid,
            'total': self.total,
        }
        values.update(changes)
        return await self.sat.query_status(**values)

    async def cancel(self) -> CancellationAnswer:
        request = CancellationRequest(
            issuer_rfc=self.issuer,
            recipient_rfc=self.recipient,
            uuid=self.uuid,
            total=self.total,
            reason='02',
            csd=self.credentials,
        )
        return await self.pac.request_cancellation(request)


@pytest.fixture
def pac(clock: Clock) -> SimulatedPac:
    return SimulatedPac(clock=clock)


@pytest.fixture
def stamped(
    pac: SimulatedPac, make_sealed: MakeSealed, credentials: CsdCredentials, clock: Clock
) -> Any:
    async def make(hours: float = 0) -> Doc:
        stamp = await pac.stamp(make_sealed())
        comprobante = read(stamp.xml)
        assert comprobante.Total is not None
        clock.advance(timedelta(hours=hours))
        return Doc(
            pac,
            SimulatedSatStatusClient(pac),
            credentials,
            stamp.timbre.UUID,
            comprobante.Emisor.Rfc,
            comprobante.Receptor.Rfc,
            comprobante.Total,
        )

    return make


async def test_after_stamping_and_after_24_hours(stamped: Any, clock: Clock) -> None:
    doc = await stamped()
    assert await doc.status() == status('valid', 'without_acceptance', 'none')
    clock.advance(timedelta(hours=24))
    assert await doc.status() == status('valid', 'with_acceptance', 'none')


async def test_an_accepted_cancellation(stamped: Any) -> None:
    doc = await stamped(1)
    assert await doc.cancel() == CancellationAnswer.ACCEPTED
    assert await doc.status() == status('cancelled', 'without_acceptance', 'accepted')


@pytest.mark.parametrize(
    ('answer', 'after'),
    [
        (ReceiverAnswer.ACCEPT, ('cancelled', 'with_acceptance', 'accepted')),
        (ReceiverAnswer.REJECT, ('valid', 'with_acceptance', 'rejected')),
        (ReceiverAnswer.EXPIRE, ('cancelled', 'with_acceptance', 'expired')),
    ],
)
async def test_a_pending_cancellation_and_the_recipients_answer(
    stamped: Any, answer: ReceiverAnswer, after: tuple[str, str, str]
) -> None:
    doc = await stamped(25)
    assert await doc.cancel() == CancellationAnswer.PENDING
    assert await doc.status() == status('valid', 'with_acceptance', 'pending')
    await doc.pac.answer_as_receiver(doc.uuid, answer)
    assert await doc.status() == status(*after)


async def test_not_cancellable(stamped: Any) -> None:
    doc = await stamped(1)
    await doc.pac.configure_cancellation(doc.uuid, CancellationOutcome.NOT_CANCELLABLE)
    assert await doc.cancel() == CancellationAnswer.NOT_CANCELLABLE
    assert await doc.status() == status('valid', 'not_cancellable', 'none')


async def test_mismatches_and_malformed_uuids_are_not_found(stamped: Any) -> None:
    doc = await stamped(1)
    assert await doc.status(issuer_rfc='AAA010101AAA') == NOT_FOUND
    assert await doc.status(recipient_rfc='AAA010101AAA') == NOT_FOUND
    assert await doc.status(total=doc.total + 1) == NOT_FOUND
    assert await doc.status(uuid='nope') == NOT_FOUND
    assert await doc.status(total=Decimal('116.0')) == status('valid', 'without_acceptance', 'none')


async def test_a_lower_case_uuid_finds_the_stamp(stamped: Any) -> None:
    doc = await stamped(1)
    assert await doc.status(uuid=doc.uuid.lower()) == status('valid', 'without_acceptance', 'none')


async def test_a_uuid_never_stamped_is_valid_and_stamped_elsewhere(pac: SimulatedPac) -> None:
    sat = SimulatedSatStatusClient(pac)
    answer = await sat.query_status('X', 'Y', NEVER_STAMPED, Decimal('3'))
    assert answer == status('valid', 'with_acceptance', 'none')


async def test_simulated_pacs_over_one_store_agree(make_sealed: MakeSealed, clock: Clock) -> None:
    store = InMemoryStore()
    a, b = SimulatedPac(store, clock=clock), SimulatedPac(store, clock=clock)
    stamp = await a.stamp(make_sealed())
    comprobante = read(stamp.xml)
    assert comprobante.Total is not None
    args = (comprobante.Emisor.Rfc, comprobante.Receptor.Rfc, stamp.timbre.UUID, comprobante.Total)
    answers = [await SimulatedSatStatusClient(pac).query_status(*args) for pac in (a, b)]
    assert answers[0] == answers[1] == status('valid', 'without_acceptance', 'none')


class BrokenStore:
    async def get(self, key: str) -> str | None:
        raise RuntimeError('store down')

    async def set(self, key: str, value: str) -> None:
        raise RuntimeError('store down')


async def test_a_store_failure_is_unavailable() -> None:
    sat = SimulatedSatStatusClient(SimulatedPac(BrokenStore()))
    with pytest.raises(SatUnavailable) as caught:
        await sat.query_status('A', 'B', NEVER_STAMPED, Decimal('1'))
    assert caught.value.__cause__ is None
    assert caught.value.__suppress_context__


def test_both_clients_are_status_clients(pac: SimulatedPac) -> None:
    clients: list[SatStatusClient] = [SimulatedSatStatusClient(pac), SatConsultaClient()]
    assert all(hasattr(client, 'query_status') for client in clients)
