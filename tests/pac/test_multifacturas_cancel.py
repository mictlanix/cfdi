"""User Story 2: cancelling through Multifacturas."""

import base64
from decimal import Decimal
from typing import Any

import pytest

from mictlanix.cfdi.pac import (
    CancellationAnswer,
    CancellationRequest,
    CsdCredentials,
    MultifacturasPac,
    MultifacturasSettings,
    PacRejected,
    PacTimeout,
    PacUnavailable,
)
from tests.conftest import CsdFiles
from tests.pac.conftest import Replay

UUID = '939513ef-ceaa-4e44-9ad9-6224778d9a9d'
SUBSTITUTE = '6A1B2C3D-4E5F-4061-8293-A4B5C6D7E8F9'


def _pac(production: bool = False) -> MultifacturasPac:
    return MultifacturasPac(
        MultifacturasSettings(user='USER', password='PASSWORD', production=production)
    )


def _request(credentials: CsdCredentials, **changes: Any) -> CancellationRequest:
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


@pytest.mark.parametrize(
    ('production', 'reason', 'substitute', 'flag'),
    [(False, '02', None, 'NO'), (True, '01', SUBSTITUTE, 'SI')],
)
async def test_the_request_sends_only_what_the_pac_needs(
    replay: Replay,
    credentials: CsdCredentials,
    csd_files: CsdFiles,
    production: bool,
    reason: str,
    substitute: str | None,
    flag: str,
) -> None:
    sent = replay('cancelarCfdi_205.xml')
    request = _request(credentials, reason=reason, substitute_uuid=substitute)
    with pytest.raises(PacRejected):
        await _pac(production).request_cancellation(request)
    assert sent[0].url == 'https://ws.multifacturas.com/cancelacion2022/index.php'
    assert sent[0].action == 'cancelarCfdi'
    assert sent[0].params == {
        'usuario': 'USER',
        'pass': 'PASSWORD',
        'accion': 'cancelar',
        'produccion': flag,
        'uuid': UUID.upper(),
        'rfc': 'EKU9003173C9',
        'password': csd_files.password,
        'motivo': reason,
        'folioSustitucion': substitute or '',
        'b64Cer': base64.b64encode(csd_files.certificate).decode(),
        'b64Key': base64.b64encode(csd_files.private_key).decode(),
    }


@pytest.mark.parametrize(
    ('answer', 'expected'),
    [
        ('cancelarCfdi_201.xml', CancellationAnswer.PENDING),
        ('cancelarCfdi_202.xml', CancellationAnswer.ACCEPTED),
    ],
)
async def test_the_sat_code_decides_the_answer(
    replay: Replay, credentials: CsdCredentials, answer: str, expected: CancellationAnswer
) -> None:
    sent = replay(answer)
    assert await _pac().request_cancellation(_request(credentials)) == expected
    assert len(sent) == 1


async def test_the_sat_refusal_is_rejected(replay: Replay, credentials: CsdCredentials) -> None:
    sent = replay('cancelarCfdi_205.xml')
    with pytest.raises(PacRejected) as caught:
        await _pac().request_cancellation(_request(credentials))
    assert (caught.value.code, caught.value.message) == ('205', 'No Existe')
    assert len(sent) == 1


async def test_the_pac_refusal_is_rejected(
    replay: Replay, credentials: CsdCredentials, csd_files: CsdFiles
) -> None:
    replay('cancelarCfdi_CACFDI33.xml')
    with pytest.raises(PacRejected) as caught:
        await _pac().request_cancellation(_request(credentials))
    assert (caught.value.code, caught.value.message) == ('CACFDI33', 'Problemas con los campos.')
    secrets = [
        'PASSWORD',
        csd_files.password,
        base64.b64encode(csd_files.certificate).decode()[:40],
        base64.b64encode(csd_files.private_key).decode()[:40],
    ]
    for text in (str(caught.value), repr(caught.value)):
        for secret in secrets:
            assert secret not in text


@pytest.mark.parametrize('error', [PacUnavailable(), PacTimeout()])
async def test_transport_errors_reach_the_caller(
    replay: Replay, credentials: CsdCredentials, error: Exception
) -> None:
    replay(error)
    with pytest.raises(type(error)):
        await _pac().request_cancellation(_request(credentials))
