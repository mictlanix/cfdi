"""User Story 2: cancelling through the simulated PAC and following the SAT status."""

from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from typing import Any

import pytest

from mictlanix.cfdi import read
from mictlanix.cfdi.pac import (
    Cancellability,
    CancellationAnswer,
    CancellationOutcome,
    CancellationRequest,
    CancellationStatus,
    CsdCredentials,
    PacRejected,
    PacTimeout,
    PacUnavailable,
    ReceiverAnswer,
    SatState,
    SatStatus,
    SimulatedPac,
    Stamp,
    StampOutcome,
)
from tests.conftest import CsdFiles
from tests.pac.conftest import Clock, MakeSealed, assert_valid_stamp

A = CancellationAnswer
Out = CancellationOutcome
NEVER_STAMPED = '6A1B2C3D-4E5F-4061-8293-A4B5C6D7E8F9'


def status(state: str, cancellability: str, cancellation: str) -> SatStatus:
    return SatStatus(
        state=SatState(state),
        cancellability=Cancellability(cancellability),
        cancellation=CancellationStatus(cancellation),
    )


@dataclass
class Doc:
    """A stamped document and the values a cancellation and a query need."""

    pac: SimulatedPac
    stamp: Stamp
    credentials: CsdCredentials
    issuer: str
    recipient: str
    total: Decimal

    @property
    def uuid(self) -> str:
        return self.stamp.timbre.UUID

    def request(self, **changes: Any) -> CancellationRequest:
        values: dict[str, Any] = {
            'issuer_rfc': self.issuer,
            'recipient_rfc': self.recipient,
            'uuid': self.uuid,
            'total': self.total,
            'reason': '02',
            'csd': self.credentials,
        }
        values.update(changes)
        return CancellationRequest(**values)

    async def cancel(self, **changes: Any) -> CancellationAnswer:
        return await self.pac.request_cancellation(self.request(**changes))

    async def status(self, **changes: Any) -> SatStatus:
        values: dict[str, Any] = {
            'issuer_rfc': self.issuer,
            'recipient_rfc': self.recipient,
            'uuid': self.uuid,
            'total': self.total,
        }
        values.update(changes)
        return await self.pac.query_status(**values)

    async def configure(self, outcome: CancellationOutcome, **options: Any) -> None:
        await self.pac.configure_cancellation(self.uuid, outcome, **options)

    async def receiver(self, answer: ReceiverAnswer) -> None:
        await self.pac.answer_as_receiver(self.uuid, answer)


@pytest.fixture
def pac(clock: Clock) -> SimulatedPac:
    return SimulatedPac(clock=clock)


@pytest.fixture
def stamped(
    pac: SimulatedPac, make_sealed: MakeSealed, credentials: CsdCredentials, clock: Clock
) -> Any:
    async def make(hours: float = 0, *, timeout_stamped: bool = False) -> Doc:
        sealed = make_sealed()
        if timeout_stamped:
            await pac.configure_stamp(sealed, StampOutcome.TIMEOUT_STAMPED)
            with pytest.raises(PacTimeout):
                await pac.stamp(sealed)
            stamp = await pac.find_stamp(sealed)
            assert stamp is not None
        else:
            stamp = await pac.stamp(sealed)
        assert_valid_stamp(stamp, sealed, clock.now)
        comprobante = read(stamp.xml)
        assert comprobante.Total is not None
        clock.advance(timedelta(hours=hours))
        return Doc(
            pac,
            stamp,
            credentials,
            comprobante.Emisor.Rfc,
            comprobante.Receptor.Rfc,
            comprobante.Total,
        )

    return make


def test_outcome_and_answer_values() -> None:
    assert {m.name: m.value for m in CancellationOutcome} == {
        'ACCEPTED': 'accepted',
        'PENDING': 'pending',
        'NOT_CANCELLABLE': 'not_cancellable',
        'REJECTED': 'rejected',
        'UNAVAILABLE': 'unavailable',
        'TIMEOUT': 'timeout',
    }
    assert {m.name: m.value for m in ReceiverAnswer} == {
        'ACCEPT': 'accept',
        'REJECT': 'reject',
        'EXPIRE': 'expire',
    }


async def test_status_before_any_request(stamped: Any, clock: Clock) -> None:
    doc = await stamped()
    assert await doc.status() == status('valid', 'without_acceptance', 'none')
    clock.advance(timedelta(hours=24))
    assert await doc.status() == status('valid', 'with_acceptance', 'none')


async def test_under_24_hours_is_cancelled_at_once(stamped: Any) -> None:
    doc = await stamped(1)
    assert await doc.cancel() == A.ACCEPTED
    assert await doc.status() == status('cancelled', 'without_acceptance', 'accepted')


async def test_exactly_24_hours_needs_acceptance(stamped: Any) -> None:
    doc = await stamped(24)
    assert await doc.cancel() == A.PENDING


async def test_after_24_hours_it_goes_pending(stamped: Any) -> None:
    doc = await stamped(25)
    assert await doc.cancel() == A.PENDING
    assert await doc.status() == status('valid', 'with_acceptance', 'pending')
    assert await doc.cancel() == A.PENDING
    assert await doc.status() == status('valid', 'with_acceptance', 'pending')


@pytest.mark.parametrize(
    ('answer', 'after'),
    [
        (ReceiverAnswer.ACCEPT, ('cancelled', 'with_acceptance', 'accepted')),
        (ReceiverAnswer.REJECT, ('valid', 'with_acceptance', 'rejected')),
        (ReceiverAnswer.EXPIRE, ('cancelled', 'with_acceptance', 'expired')),
    ],
)
async def test_the_receiver_answers(
    stamped: Any, answer: ReceiverAnswer, after: tuple[str, str, str]
) -> None:
    doc = await stamped(25)
    await doc.cancel()
    await doc.receiver(answer)
    assert await doc.status() == status(*after)
    if answer == ReceiverAnswer.REJECT:
        assert await doc.cancel() == A.PENDING
        assert await doc.status() == status('valid', 'with_acceptance', 'pending')
    else:
        assert await doc.cancel() == A.ACCEPTED
        assert await doc.status() == status(*after)


async def test_not_cancellable(stamped: Any) -> None:
    doc = await stamped(1)
    await doc.configure(Out.NOT_CANCELLABLE)
    assert await doc.cancel() == A.NOT_CANCELLABLE
    assert await doc.status() == status('valid', 'not_cancellable', 'none')
    assert await doc.cancel() == A.NOT_CANCELLABLE
    await doc.configure(Out.ACCEPTED)
    assert await doc.cancel() == A.NOT_CANCELLABLE
    assert await doc.status() == status('valid', 'not_cancellable', 'none')
    await doc.configure(Out.TIMEOUT)
    with pytest.raises(PacTimeout):
        await doc.cancel()
    assert await doc.status() == status('valid', 'not_cancellable', 'none')


async def test_configured_answers_override_the_24_hour_rule(stamped: Any) -> None:
    old = await stamped(25)
    await old.configure(Out.ACCEPTED)
    assert await old.cancel() == A.ACCEPTED
    recent = await stamped(1)
    await recent.configure(Out.PENDING)
    assert await recent.cancel() == A.PENDING
    assert await recent.status() == status('valid', 'with_acceptance', 'pending')


async def test_a_timeout_leaves_it_pending(stamped: Any) -> None:
    doc = await stamped(1)
    await doc.configure(Out.TIMEOUT)
    with pytest.raises(PacTimeout):
        await doc.cancel()
    assert await doc.status() == status('valid', 'with_acceptance', 'pending')


async def test_once_pending_it_needs_acceptance_from_then_on(stamped: Any) -> None:
    doc = await stamped(1)
    await doc.configure(Out.PENDING)
    await doc.cancel()
    await doc.receiver(ReceiverAnswer.REJECT)
    assert await doc.cancel() == A.PENDING


async def test_configured_outcomes_on_a_pending_document(stamped: Any) -> None:
    doc = await stamped(25)
    await doc.cancel()
    await doc.configure(Out.ACCEPTED)
    assert await doc.cancel() == A.PENDING
    assert await doc.status() == status('valid', 'with_acceptance', 'pending')
    await doc.receiver(ReceiverAnswer.REJECT)
    assert await doc.cancel() == A.PENDING
    await doc.configure(Out.TIMEOUT)
    with pytest.raises(PacTimeout):
        await doc.cancel()
    assert await doc.status() == status('valid', 'with_acceptance', 'pending')


async def test_configured_outcomes_on_a_cancelled_document(stamped: Any) -> None:
    doc = await stamped(1)
    await doc.cancel()
    await doc.configure(Out.PENDING)
    assert await doc.cancel() == A.ACCEPTED
    await doc.configure(Out.TIMEOUT)
    with pytest.raises(PacTimeout):
        await doc.cancel()
    assert await doc.status() == status('cancelled', 'without_acceptance', 'accepted')


@pytest.mark.parametrize(
    ('options', 'expected'),
    [({}, ('CFDI40999', 'Rechazo simulado')), ({'code': 'X', 'message': 'Y'}, ('X', 'Y'))],
)
async def test_rejected(stamped: Any, options: dict[str, str], expected: tuple[str, str]) -> None:
    doc = await stamped(1)
    await doc.configure(Out.REJECTED, **options)
    with pytest.raises(PacRejected) as caught:
        await doc.cancel()
    assert (caught.value.code, caught.value.message) == expected
    assert await doc.status() == status('valid', 'without_acceptance', 'none')
    assert await doc.cancel() == A.ACCEPTED


async def test_unavailable(stamped: Any) -> None:
    doc = await stamped(1)
    await doc.configure(Out.UNAVAILABLE)
    with pytest.raises(PacUnavailable):
        await doc.cancel()
    assert await doc.status() == status('valid', 'without_acceptance', 'none')
    assert await doc.cancel() == A.ACCEPTED


async def test_a_uuid_never_stamped(pac: SimulatedPac, credentials: CsdCredentials) -> None:
    query = await pac.query_status('AAA010101AAA', 'XAXX010101000', NEVER_STAMPED, Decimal('1'))
    assert query == status('valid', 'with_acceptance', 'none')
    request = CancellationRequest(
        issuer_rfc='AAA010101AAA',
        recipient_rfc='XAXX010101000',
        uuid=NEVER_STAMPED,
        total=Decimal('1'),
        reason='02',
        csd=credentials,
    )
    assert await pac.request_cancellation(request) == A.PENDING
    await pac.answer_as_receiver(NEVER_STAMPED, ReceiverAnswer.ACCEPT)
    assert await pac.query_status('X', 'Y', NEVER_STAMPED, Decimal('9')) == status(
        'cancelled', 'with_acceptance', 'accepted'
    )


async def test_mismatches(stamped: Any) -> None:
    doc = await stamped(1)
    not_found = status('not_found', 'not_cancellable', 'none')
    assert await doc.status(issuer_rfc='AAA010101AAA') == not_found
    assert await doc.status(recipient_rfc='AAA010101AAA') == not_found
    assert await doc.status(total=doc.total + 1) == not_found
    assert await doc.status(total=Decimal('116.0')) == status('valid', 'without_acceptance', 'none')
    with pytest.raises(PacRejected) as caught:
        await doc.cancel(total=doc.total + 1)
    assert caught.value.code == '205'
    await doc.configure(Out.TIMEOUT)
    with pytest.raises(PacRejected) as caught:
        await doc.cancel(recipient_rfc='AAA010101AAA')
    assert caught.value.code == '205'
    with pytest.raises(PacTimeout):
        await doc.cancel()


async def test_a_malformed_uuid_is_not_found(pac: SimulatedPac) -> None:
    assert await pac.query_status('A', 'B', 'nope', Decimal('1')) == status(
        'not_found', 'not_cancellable', 'none'
    )


async def test_a_timeout_stamped_document_has_its_record(stamped: Any) -> None:
    doc = await stamped(1, timeout_stamped=True)
    with pytest.raises(PacRejected) as caught:
        await doc.cancel(total=doc.total + 1)
    assert caught.value.code == '205'
    assert await doc.cancel() == A.ACCEPTED


async def test_configuring_a_uuid_never_stamped(pac: SimulatedPac) -> None:
    await pac.configure_cancellation(NEVER_STAMPED, Out.PENDING)
    assert await pac.query_status('X', 'Y', NEVER_STAMPED, Decimal('3')) == status(
        'valid', 'with_acceptance', 'none'
    )


async def test_not_cancellable_on_a_uuid_never_stamped(
    pac: SimulatedPac, credentials: CsdCredentials
) -> None:
    await pac.configure_cancellation(NEVER_STAMPED, Out.NOT_CANCELLABLE)
    request = CancellationRequest(
        issuer_rfc='A',
        recipient_rfc='B',
        uuid=NEVER_STAMPED,
        total=Decimal('1'),
        reason='02',
        csd=credentials,
    )
    assert await pac.request_cancellation(request) == A.NOT_CANCELLABLE
    assert await pac.query_status('X', 'Y', NEVER_STAMPED, Decimal('3')) == status(
        'valid', 'not_cancellable', 'none'
    )


async def test_configuring_by_uuid(stamped: Any) -> None:
    doc = await stamped(1)
    await doc.pac.configure_cancellation(doc.uuid.lower(), Out.PENDING)
    await doc.pac.configure_cancellation('not-a-uuid', Out.UNAVAILABLE)
    await doc.status()
    assert await doc.cancel() == A.PENDING


async def test_not_cancellable_after_a_rejection_keeps_the_status(stamped: Any) -> None:
    doc = await stamped(25)
    await doc.cancel()
    await doc.receiver(ReceiverAnswer.REJECT)
    await doc.configure(Out.NOT_CANCELLABLE)
    assert await doc.cancel() == A.NOT_CANCELLABLE
    assert await doc.status() == status('valid', 'not_cancellable', 'rejected')


async def test_a_lower_case_uuid_finds_the_stamp(stamped: Any) -> None:
    doc = await stamped(1)
    assert await doc.status(uuid=doc.uuid.lower()) == status('valid', 'without_acceptance', 'none')
    assert await doc.cancel(uuid=doc.uuid.lower()) == A.ACCEPTED


async def test_nothing_pending_for_the_receiver(stamped: Any) -> None:
    doc = await stamped(1)
    with pytest.raises(PacRejected) as caught:
        await doc.receiver(ReceiverAnswer.ACCEPT)
    assert caught.value.code == 'SIM01'


async def test_credentials_and_substitute_are_not_checked(stamped: Any) -> None:
    doc = await stamped(1)
    doc.credentials = CsdCredentials(certificate=b'x', private_key=b'y', password='z')
    answer = await doc.cancel(reason='01', substitute_uuid=NEVER_STAMPED)
    assert answer == A.ACCEPTED


async def test_no_error_shows_credentials(stamped: Any, csd_files: CsdFiles) -> None:
    doc = await stamped(1)
    errors: list[Exception] = []
    for outcome in (Out.REJECTED, Out.UNAVAILABLE, Out.TIMEOUT):
        await doc.configure(outcome)
        with pytest.raises((PacRejected, PacUnavailable, PacTimeout)) as caught:
            await doc.cancel()
        errors.append(caught.value)
    with pytest.raises(PacRejected) as mismatch:
        await doc.cancel(total=doc.total + 1)
    errors.append(mismatch.value)
    for error in errors:
        for text in (str(error), repr(error)):
            assert csd_files.password not in text
            assert repr(csd_files.private_key)[:40] not in text
            assert repr(csd_files.certificate)[:40] not in text
