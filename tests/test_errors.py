import dataclasses
from datetime import datetime

import pytest

import mictlanix.cfdi as cfdi
from mictlanix.cfdi import (
    CertificateValidityError,
    CfdiError,
    CsdError,
    NotCfdi40Error,
    NotStampedError,
    ParseError,
    ValidationError,
    Violation,
)


def test_every_error_is_a_cfdi_error() -> None:
    for error in (
        ValidationError,
        CsdError,
        CertificateValidityError,
        ParseError,
        NotCfdi40Error,
        NotStampedError,
    ):
        assert issubclass(error, CfdiError)
    assert issubclass(CfdiError, Exception)


def test_violation_is_a_frozen_value() -> None:
    violation = Violation(
        node='/cfdi:Comprobante/cfdi:Receptor',
        attribute='Rfc',
        rule='cvc-pattern-valid',
        message='bad RFC',
    )
    assert violation == Violation(
        '/cfdi:Comprobante/cfdi:Receptor', 'Rfc', 'cvc-pattern-valid', 'bad RFC'
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        violation.rule = 'other'  # type: ignore[misc]


def test_validation_error_carries_every_violation() -> None:
    violations = [
        Violation('/cfdi:Comprobante', 'TipoDeComprobante', 'cvc-enumeration-valid', 'a'),
        Violation('/cfdi:Comprobante/cfdi:Receptor', 'Rfc', 'cvc-pattern-valid', 'b'),
    ]
    error = ValidationError(violations)
    assert error.violations == violations
    assert 'cvc-enumeration-valid' in str(error)
    assert 'cvc-pattern-valid' in str(error)


def test_csd_error_reason_is_a_closed_set_of_names() -> None:
    assert {reason.value for reason in CsdError.Reason} == {
        'invalid_certificate',
        'invalid_key',
        'wrong_password',
        'key_mismatch',
    }
    error = CsdError(CsdError.Reason.WRONG_PASSWORD)
    assert error.reason == 'wrong_password'
    assert error.reason is CsdError.Reason.WRONG_PASSWORD


def test_certificate_validity_error_carries_the_dates() -> None:
    error = CertificateValidityError(
        fecha=datetime(2031, 1, 1),
        valid_from=datetime(2023, 5, 18),
        valid_to=datetime(2027, 5, 18),
    )
    assert error.fecha == datetime(2031, 1, 1)
    assert error.valid_from == datetime(2023, 5, 18)
    assert error.valid_to == datetime(2027, 5, 18)


def test_parse_error_carries_a_position_or_a_node_and_attribute() -> None:
    at_position = ParseError('not well-formed', line=3, column=7)
    assert (at_position.line, at_position.column) == (3, 7)
    assert at_position.node is None and at_position.attribute is None

    at_value = ParseError('not a decimal', node='/cfdi:Comprobante', attribute='SubTotal')
    assert (at_value.node, at_value.attribute) == ('/cfdi:Comprobante', 'SubTotal')
    assert at_value.line is None and at_value.column is None


def test_not_cfdi40_error_carries_what_was_found() -> None:
    error = NotCfdi40Error(root='{http://www.sat.gob.mx/cfd/3}Comprobante', version='3.3')
    assert error.root == '{http://www.sat.gob.mx/cfd/3}Comprobante'
    assert error.version == '3.3'


def test_not_stamped_error_needs_no_data() -> None:
    assert isinstance(NotStampedError(), CfdiError)


def test_errors_and_violation_are_exported() -> None:
    for name in (
        'CfdiError',
        'ValidationError',
        'CsdError',
        'CertificateValidityError',
        'ParseError',
        'NotCfdi40Error',
        'NotStampedError',
        'Violation',
    ):
        assert name in cfdi.__all__
