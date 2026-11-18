"""User Story 1: asking the SAT the status of a CFDI, replaying recorded and synthetic answers."""

import os
from decimal import Decimal
from typing import Any

import pytest

from mictlanix.cfdi import _soap
from mictlanix.cfdi.sat import (
    Cancellability,
    CancellationStatus,
    SatConsultaClient,
    SatConsultaSettings,
    SatRejected,
    SatState,
    SatStatus,
    SatTimeout,
    SatUnavailable,
)
from tests.sat.conftest import Replay

UUID = '939513EF-CEAA-4E44-9AD9-6224778D9A9D'
ACTION = 'http://tempuri.org/IConsultaCFDIService/Consulta'
V, C, NF = SatState.VALID, SatState.CANCELLED, SatState.NOT_FOUND
SIN, CON, NO = (
    Cancellability.WITHOUT_ACCEPTANCE,
    Cancellability.WITH_ACCEPTANCE,
    Cancellability.NOT_CANCELLABLE,
)
S = CancellationStatus


def _status(state: SatState, cancellability: Cancellability, cancellation: S) -> SatStatus:
    return SatStatus(state=state, cancellability=cancellability, cancellation=cancellation)


NOT_FOUND = _status(NF, NO, S.NONE)


async def _ask(**changes: Any) -> SatStatus:
    values: dict[str, Any] = {
        'issuer_rfc': 'EKU9003173C9',
        'recipient_rfc': 'URE180429TM6',
        'uuid': UUID,
        'total': Decimal('116.00'),
    }
    values.update(changes)
    return await SatConsultaClient().query_status(**values)


def _clean(error: BaseException, *answer_texts: str) -> None:
    assert error.__cause__ is None
    for text in (str(error), repr(error)):
        for answer_text in answer_texts:
            assert answer_text not in text


async def test_the_request(replay: Replay) -> None:
    sent = replay('consulta_no_encontrado.xml', 'consulta_no_encontrado.xml')
    settings = SatConsultaSettings(url='https://sat.example.test/consulta.svc')
    await SatConsultaClient(settings).query_status(
        'EKU9003173C9', 'URE180429TM6', UUID, Decimal('116.00')
    )
    assert len(sent) == 1  # one request per status (SC-003)
    assert sent[0].url == 'https://sat.example.test/consulta.svc'
    assert sent[0].action == ACTION
    assert sent[0].timeouts is settings
    assert sent[0].expression == f'?re=EKU9003173C9&rr=URE180429TM6&tt=116.0&id={UUID}'
    await _ask(total=Decimal('642.20'), uuid=UUID.lower(), issuer_rfc='A&B010101AAA')
    assert sent[1].expression == f'?re=A&B010101AAA&rr=URE180429TM6&tt=642.2&id={UUID.lower()}'


async def test_the_default_endpoint(replay: Replay) -> None:
    sent = replay('consulta_no_encontrado.xml')
    await _ask()
    assert sent[0].url == SatConsultaSettings().url


@pytest.mark.parametrize(
    ('fixture', 'expected'),
    [
        ('consulta_no_encontrado.xml', NOT_FOUND),
        ('consulta_codigo_n.xml', NOT_FOUND),
        ('consulta_vigente_sin_aceptacion.xml', _status(V, SIN, S.NONE)),
        ('consulta_vigente_con_aceptacion.xml', _status(V, CON, S.NONE)),
        ('consulta_vigente_no_cancelable.xml', _status(V, NO, S.NONE)),
        ('consulta_vigente_en_proceso.xml', _status(V, CON, S.PENDING)),
        ('consulta_vigente_rechazada.xml', _status(V, CON, S.REJECTED)),
        ('consulta_cancelado_sin_aceptacion.xml', _status(C, SIN, S.ACCEPTED)),
        ('consulta_cancelado_con_aceptacion.xml', _status(C, CON, S.ACCEPTED)),
        ('consulta_cancelado_plazo_vencido.xml', _status(C, CON, S.EXPIRED)),
        ('consulta_cancelado_sin_estatus.xml', _status(C, SIN, S.NONE)),
    ],
)
async def test_every_row_of_the_mapping(replay: Replay, fixture: str, expected: SatStatus) -> None:
    replay(fixture)
    assert await _ask() == expected


@pytest.mark.parametrize(
    'fixture',
    [
        'consulta_estado_desconocido.xml',
        'consulta_cancelable_desconocido.xml',
        'consulta_estatus_desconocido.xml',
    ],
)
async def test_a_value_outside_the_mapping_is_rejected(replay: Replay, fixture: str) -> None:
    replay(fixture)
    with pytest.raises(SatRejected) as caught:
        await _ask()
    assert (caught.value.code, caught.value.message) == ('SAT-ANSWER', 'unexpected SAT status')
    _clean(caught.value, 'Suspendido', 'Desconocido')


async def test_a_fault_is_rejected_without_its_text(replay: Replay) -> None:
    fault = (
        b'<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"><s:Body><s:Fault>'
        b'<faultcode>s:Client</faultcode><faultstring>secret detail</faultstring>'
        b'</s:Fault></s:Body></s:Envelope>'
    )
    replay(fault)
    with pytest.raises(SatRejected) as caught:
        await _ask()
    assert caught.value.code == 'SOAP-FAULT'
    _clean(caught.value, 'secret detail')


@pytest.mark.parametrize(
    ('answer', 'expected'),
    [
        (_soap.Unreachable(), SatUnavailable),
        (_soap.NoAnswer(), SatTimeout),
        (b'<html>busy</html>', SatTimeout),
        (b'', SatTimeout),
    ],
)
async def test_transport_outcomes(
    replay: Replay, answer: bytes | Exception, expected: type[Exception]
) -> None:
    replay(answer)
    with pytest.raises(expected) as caught:
        await _ask()
    _clean(caught.value, 'busy')


async def test_a_malformed_uuid_is_not_found_without_a_request(replay: Replay) -> None:
    sent = replay()
    assert await _ask(uuid='nope') == NOT_FOUND
    assert sent == []


async def test_nothing_is_read_from_the_environment(
    replay: Replay, monkeypatch: pytest.MonkeyPatch
) -> None:
    def refuse(*args: object) -> None:
        raise AssertionError('the environment was read')

    for name in list(os.environ):
        monkeypatch.delenv(name)
    monkeypatch.setattr(os, 'getenv', refuse)
    monkeypatch.setattr(os.environ, 'get', refuse)
    replay('consulta_vigente_en_proceso.xml')
    assert await _ask() == _status(V, CON, S.PENDING)
