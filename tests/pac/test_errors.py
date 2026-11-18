"""The PAC errors: one base, three kinds, nothing to parse."""

from mictlanix.cfdi import CfdiError
from mictlanix.cfdi.pac import PacError, PacRejected, PacTimeout, PacUnavailable


def test_every_pac_error_shares_one_base_under_the_library_base() -> None:
    assert issubclass(PacError, CfdiError)
    for kind in (PacRejected, PacUnavailable, PacTimeout):
        assert issubclass(kind, PacError)


def test_rejected_carries_the_pac_code_and_message() -> None:
    error = PacRejected('CFDI40102', 'Sello inválido')
    assert error.code == 'CFDI40102'
    assert error.message == 'Sello inválido'
    assert str(error) == 'CFDI40102: Sello inválido'


def test_unavailable_and_timeout_take_no_arguments_and_have_fixed_messages() -> None:
    assert str(PacUnavailable()) == str(PacUnavailable())
    assert str(PacTimeout()) == str(PacTimeout())
    assert str(PacUnavailable())
    assert str(PacTimeout())
    assert str(PacUnavailable()) != str(PacTimeout())
