"""The interface's values: immutable, keyword-only, never printing secrets or XML."""

import base64
import inspect
from dataclasses import FrozenInstanceError
from datetime import datetime
from decimal import Decimal
from typing import Any

import pytest

from mictlanix.cfdi import tfd11
from mictlanix.cfdi.pac import (
    CancellationAnswer,
    CancellationRequest,
    CsdCredentials,
    PacClient,
    Stamp,
)
from tests.conftest import CsdFiles

UUID = '5FB2822E-396D-4725-8521-CDC4BDD20CCF'


def _timbre() -> tfd11.TimbreFiscalDigital:
    return tfd11.TimbreFiscalDigital(
        UUID=UUID,
        FechaTimbrado=datetime(2026, 11, 17, 12, 0, 0),
        RfcProvCertif='SIM010101SI0',
        SelloCFD='c2VsbG8=',
        NoCertificadoSAT='00001000000000000000',
        SelloSAT='c2F0',
    )


def _request(credentials: CsdCredentials) -> CancellationRequest:
    return CancellationRequest(
        issuer_rfc='EKU9003173C9',
        recipient_rfc='URE180429TM6',
        uuid=UUID,
        total=Decimal('116.00'),
        reason='02',
        csd=credentials,
    )


def _values(credentials: CsdCredentials) -> list[Any]:
    return [
        Stamp(xml=b'<x/>', timbre=_timbre()),
        credentials,
        _request(credentials),
    ]


def test_values_are_frozen(credentials: CsdCredentials) -> None:
    for value in _values(credentials):
        field = next(iter(value.__dataclass_fields__))
        with pytest.raises(FrozenInstanceError):
            setattr(value, field, None)


def test_values_are_keyword_only(credentials: CsdCredentials) -> None:
    with pytest.raises(TypeError):
        Stamp(b'<x/>', _timbre())  # type: ignore[misc]
    with pytest.raises(TypeError):
        CsdCredentials(b'c', b'k', 'p')  # type: ignore[misc]


def test_credentials_repr_hides_the_key_and_password(csd_files: CsdFiles) -> None:
    credentials = CsdCredentials(
        certificate=csd_files.certificate,
        private_key=csd_files.private_key,
        password=csd_files.password,
    )
    assert repr(credentials) == (
        f'CsdCredentials(certificate=<{len(csd_files.certificate)} bytes>, '
        'private_key=<hidden>, password=<hidden>)'
    )


def test_no_repr_shows_secrets(csd_files: CsdFiles, credentials: CsdCredentials) -> None:
    secrets = [
        csd_files.password,
        repr(csd_files.private_key),
        repr(csd_files.certificate),
        base64.b64encode(csd_files.private_key).decode(),
        base64.b64encode(csd_files.certificate).decode(),
    ]
    for text in (repr(credentials), repr(_request(credentials))):
        for secret in secrets:
            assert secret not in text


def test_stamp_repr_never_shows_the_xml() -> None:
    timbre = _timbre()
    xml = b'<cfdi:Comprobante Certificado="MIIF"/>'
    stamp = Stamp(xml=xml, timbre=timbre)
    assert repr(stamp) == f'Stamp(xml=<{len(xml)} bytes>, timbre={timbre!r})'
    assert 'MIIF' not in repr(stamp)


@pytest.mark.parametrize(
    ('enum', 'members'),
    [
        (
            CancellationAnswer,
            {'ACCEPTED': 'accepted', 'PENDING': 'pending', 'NOT_CANCELLABLE': 'not_cancellable'},
        ),
    ],
)
def test_enums_have_exactly_their_values(enum: Any, members: dict[str, str]) -> None:
    assert {member.name: member.value for member in enum} == members
    for name, value in members.items():
        assert enum[name] == value


def test_every_interface_method_is_a_coroutine_function() -> None:
    for name in ('stamp', 'find_stamp', 'request_cancellation'):
        assert inspect.iscoroutinefunction(getattr(PacClient, name)), name
