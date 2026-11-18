"""A cancellation request is valid by construction: reason, substitute UUID and UUID format."""

from decimal import Decimal
from typing import Any

import pytest

from mictlanix.cfdi import ValidationError
from mictlanix.cfdi.pac import CancellationRequest, CsdCredentials

UUID = '5FB2822E-396D-4725-8521-CDC4BDD20CCF'
SUBSTITUTE = '6A1B2C3D-4E5F-4061-8293-A4B5C6D7E8F9'


def _build(credentials: CsdCredentials, **changes: Any) -> CancellationRequest:
    values: dict[str, Any] = {
        'issuer_rfc': 'EKU9003173C9',
        'recipient_rfc': 'URE180429TM6',
        'uuid': UUID,
        'total': Decimal('116.00'),
        'reason': '02',
        'csd': credentials,
    }
    values.update(changes)
    return CancellationRequest(**values)


def _rules(caught: pytest.ExceptionInfo[ValidationError]) -> set[tuple[str, str | None]]:
    for violation in caught.value.violations:
        assert violation.node == 'CancellationRequest'
    return {(v.rule, v.attribute) for v in caught.value.violations}


@pytest.mark.parametrize('reason', ['02', '03', '04'])
def test_reasons_02_to_04_without_a_substitute_build(
    credentials: CsdCredentials, reason: str
) -> None:
    assert _build(credentials, reason=reason).reason == reason


def test_reason_01_with_a_substitute_builds(credentials: CsdCredentials) -> None:
    request = _build(credentials, reason='01', substitute_uuid=SUBSTITUTE)
    assert request.substitute_uuid == SUBSTITUTE


@pytest.mark.parametrize('reason', ['02', '03', '04'])
def test_reasons_02_to_04_forbid_a_substitute(credentials: CsdCredentials, reason: str) -> None:
    with pytest.raises(ValidationError) as caught:
        _build(credentials, reason=reason, substitute_uuid=SUBSTITUTE)
    assert _rules(caught) == {('cancellation-substitute-forbidden', 'substitute_uuid')}


def test_reason_01_requires_a_substitute(credentials: CsdCredentials) -> None:
    with pytest.raises(ValidationError) as caught:
        _build(credentials, reason='01')
    assert _rules(caught) == {('cancellation-substitute-required', 'substitute_uuid')}


@pytest.mark.parametrize('reason', ['05', ''])
def test_a_reason_outside_01_to_04_is_refused(credentials: CsdCredentials, reason: str) -> None:
    with pytest.raises(ValidationError) as caught:
        _build(credentials, reason=reason)
    assert _rules(caught) == {('cancellation-reason', 'reason')}


def test_a_malformed_uuid_is_refused(credentials: CsdCredentials) -> None:
    with pytest.raises(ValidationError) as caught:
        _build(credentials, uuid='not-a-uuid')
    assert _rules(caught) == {('uuid-format', 'uuid')}


def test_a_malformed_substitute_is_refused(credentials: CsdCredentials) -> None:
    with pytest.raises(ValidationError) as caught:
        _build(credentials, reason='01', substitute_uuid='nope')
    assert _rules(caught) == {('uuid-format', 'substitute_uuid')}


def test_a_lower_case_uuid_is_accepted_and_kept(credentials: CsdCredentials) -> None:
    assert _build(credentials, uuid=UUID.lower()).uuid == UUID.lower()


def test_several_problems_come_together(credentials: CsdCredentials) -> None:
    with pytest.raises(ValidationError) as caught:
        _build(credentials, uuid='bad', reason='01')
    assert _rules(caught) == {
        ('uuid-format', 'uuid'),
        ('cancellation-substitute-required', 'substitute_uuid'),
    }
