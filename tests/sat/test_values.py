"""The SAT status values, enums and errors: immutable, exact, nothing to parse."""

import inspect
from dataclasses import FrozenInstanceError
from typing import Any

import pytest

from mictlanix.cfdi import CfdiError
from mictlanix.cfdi.pac import PacError
from mictlanix.cfdi.sat import (
    Cancellability,
    CancellationStatus,
    SatError,
    SatRejected,
    SatState,
    SatStatus,
    SatStatusClient,
    SatTimeout,
    SatUnavailable,
)

STATUS = SatStatus(
    state=SatState.VALID,
    cancellability=Cancellability.WITH_ACCEPTANCE,
    cancellation=CancellationStatus.PENDING,
)


def test_status_is_frozen_and_keyword_only() -> None:
    with pytest.raises(FrozenInstanceError):
        STATUS.state = SatState.CANCELLED  # type: ignore[misc]
    with pytest.raises(TypeError):
        SatStatus(SatState.VALID, Cancellability.WITH_ACCEPTANCE, CancellationStatus.NONE)  # type: ignore[misc]
    assert STATUS == SatStatus(
        state=SatState('valid'),
        cancellability=Cancellability('with_acceptance'),
        cancellation=CancellationStatus('pending'),
    )


@pytest.mark.parametrize(
    ('enum', 'members'),
    [
        (SatState, {'VALID': 'valid', 'CANCELLED': 'cancelled', 'NOT_FOUND': 'not_found'}),
        (
            Cancellability,
            {
                'WITHOUT_ACCEPTANCE': 'without_acceptance',
                'WITH_ACCEPTANCE': 'with_acceptance',
                'NOT_CANCELLABLE': 'not_cancellable',
            },
        ),
        (
            CancellationStatus,
            {
                'NONE': 'none',
                'PENDING': 'pending',
                'ACCEPTED': 'accepted',
                'REJECTED': 'rejected',
                'EXPIRED': 'expired',
            },
        ),
    ],
)
def test_enums_have_exactly_their_values(enum: Any, members: dict[str, str]) -> None:
    assert {member.name: member.value for member in enum} == members


def test_query_status_is_a_coroutine_function() -> None:
    assert inspect.iscoroutinefunction(SatStatusClient.query_status)


def test_every_sat_error_shares_one_base_under_the_library_base_not_the_pac_one() -> None:
    assert issubclass(SatError, CfdiError)
    assert not issubclass(SatError, PacError)
    for kind in (SatRejected, SatUnavailable, SatTimeout):
        assert issubclass(kind, SatError)


def test_rejected_carries_the_code_and_message() -> None:
    error = SatRejected('SAT-ANSWER', 'unexpected SAT status')
    assert (error.code, error.message) == ('SAT-ANSWER', 'unexpected SAT status')
    assert str(error) == 'SAT-ANSWER: unexpected SAT status'


def test_unavailable_and_timeout_take_no_arguments_and_name_the_sat() -> None:
    for kind in (SatUnavailable, SatTimeout):
        assert str(kind()) == str(kind())
        assert 'SAT' in str(kind())
    assert str(SatUnavailable()) != str(SatTimeout())
