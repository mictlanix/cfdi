"""User Story 1: stamping through Multifacturas, replaying recorded and synthetic answers."""

import base64
from dataclasses import replace
from typing import Any

import pytest
from lxml import etree

from mictlanix.cfdi import read, tfd11, timbre, to_xml
from mictlanix.cfdi.pac import (
    MultifacturasPac,
    MultifacturasSettings,
    PacRejected,
    PacTimeout,
    PacUnavailable,
)
from tests.conftest import invoice
from tests.pac.conftest import CFDI, MULTIFACTURAS, MakeSealed, Replay

SETTINGS = MultifacturasSettings(user='USER', password='PASSWORD', production=False)
TFD = f'{{{tfd11.NAMESPACE}}}TimbreFiscalDigital'


def _fields(name: str) -> dict[str, str]:
    root = etree.fromstring((MULTIFACTURAS / name).read_bytes())
    return {
        etree.QName(n).localname: n.text or ''
        for n in root.iter()
        if isinstance(n.tag, str) and len(n) == 0
    }


def _recorded_stamp() -> bytes:
    return base64.b64decode(_fields('timbrar33b64_ok.xml')['cfdi'])


def _sealed_from(stamped: bytes) -> bytes:
    """The sealed document a stamped one came from: the same document without its TFD."""
    root = etree.fromstring(stamped)
    complemento = root.find(f'{CFDI}Complemento')
    assert complemento is not None
    for tfd in complemento.findall(TFD):
        complemento.remove(tfd)
    if len(complemento) == 0:
        root.remove(complemento)
    return etree.tostring(root, xml_declaration=True, encoding='UTF-8')


SEALED = _sealed_from(_recorded_stamp())


def _answer(name: str, **changes: str) -> bytes:
    """A fixture with some return fields changed."""
    root = etree.fromstring((MULTIFACTURAS / name).read_bytes())
    for node in root.iter():
        if isinstance(node.tag, str) and etree.QName(node).localname in changes:
            node.text = changes[etree.QName(node).localname]
    return etree.tostring(root)


def _pac(production: bool = False) -> MultifacturasPac:
    return MultifacturasPac(
        MultifacturasSettings(user='USER', password='PASSWORD', production=production)
    )


def _assert_clean(error: Exception, *secrets: str) -> None:
    assert error.__cause__ is None
    for text in (str(error), repr(error)):
        assert 'PASSWORD' not in text
        for secret in secrets:
            assert secret not in text


@pytest.mark.parametrize(('production', 'flag'), [(False, 'NO'), (True, 'SI')])
async def test_stamp_sends_timbrar33b64(replay: Replay, production: bool, flag: str) -> None:
    sent = replay('timbrar33b64_ok.xml')
    await _pac(production).stamp(SEALED)
    assert len(sent) == 1
    assert sent[0].url == 'https://ws.multifacturas.com/pac/index.php'
    assert sent[0].action == 'timbrar33b64'
    assert sent[0].params == {
        'rfc': 'USER',
        'clave': 'PASSWORD',
        'xml': base64.b64encode(SEALED).decode(),
        'produccion': flag,
    }


async def test_a_recorded_stamp(replay: Replay) -> None:
    replay('timbrar33b64_ok.xml')
    stamp = await _pac().stamp(SEALED)
    uuid = _fields('timbrar33b64_ok.xml')['uuid']
    assert stamp.timbre.UUID == uuid.upper() != uuid
    assert stamp.timbre.SelloCFD == etree.fromstring(SEALED).get('Sello')
    read_back = timbre(read(stamp.xml))
    assert replace(read_back, UUID=read_back.UUID.upper()) == stamp.timbre


async def test_the_recorded_duplicate_gives_the_same_uuid(replay: Replay) -> None:
    replay('timbrar33b64_ok.xml', 'timbrar33b64_duplicate.xml')
    first = await _pac().stamp(SEALED)
    second = await _pac().stamp(SEALED)
    assert first.timbre.UUID == second.timbre.UUID


async def test_307_with_the_cfdi(replay: Replay) -> None:
    replay('timbrar33b64_307_cfdi.xml')
    stamp = await _pac().stamp(SEALED)
    assert stamp.timbre.SelloCFD == etree.fromstring(SEALED).get('Sello')


async def test_307_with_the_uuid_fetches_the_stamp(replay: Replay) -> None:
    sent = replay('timbrar33b64_307_uuid.xml', 'acuseSAT_cfdi.xml')
    stamp = await _pac().stamp(SEALED)
    assert [s.action for s in sent] == ['timbrar33b64', 'acuseSAT']
    assert sent[1].params == {
        'rfc': 'USER',
        'pwd': 'PASSWORD',
        'uuid': _fields('timbrar33b64_307_uuid.xml')['uuid'],
    }
    assert stamp.timbre.SelloCFD == etree.fromstring(SEALED).get('Sello')


@pytest.mark.parametrize(
    'answers',
    [
        ('timbrar33b64_307_uuid.xml', 'acuseSAT_200.xml'),
        ('timbrar33b64_307_none.xml',),
    ],
)
async def test_307_without_a_stamp_is_a_timeout(replay: Replay, answers: tuple[str, ...]) -> None:
    replay(*answers)
    with pytest.raises(PacTimeout) as caught:
        await _pac().stamp(SEALED)
    _assert_clean(caught.value)


async def test_a_307_stamp_of_another_document_is_rejected(replay: Replay) -> None:
    other = base64.b64encode(_recorded_stamp().replace(b'SelloCFD="', b'SelloCFD="X')).decode()
    replay('timbrar33b64_307_uuid.xml', _answer('acuseSAT_cfdi.xml', acuseSATResult=other))
    with pytest.raises(PacRejected) as caught:
        await _pac().stamp(SEALED)
    assert caught.value.code == 'MF-ANSWER'


async def test_recorded_rejections(replay: Replay) -> None:
    replay('timbrar33b64_301.xml', 'timbrar33b64_CFDI40102.xml')
    with pytest.raises(PacRejected) as caught:
        await _pac().stamp(SEALED)
    assert (caught.value.code, caught.value.message) == (
        '301',
        'La estructura del comprobante es incorrecta.',
    )
    with pytest.raises(PacRejected) as caught:
        await _pac().stamp(SEALED)
    assert caught.value.code == 'CFDI40102'
    assert 'digestión' in caught.value.message and '||' not in caught.value.message
    _assert_clean(caught.value, SEALED.decode()[:80])


@pytest.mark.parametrize(
    'changes',
    [
        {'cfdi': ''},
        {'cfdi': base64.b64encode(SEALED).decode()},
        {'cfdi': base64.b64encode(b'not xml').decode()},
        {'cfdi': 'not base64!'},
    ],
)
async def test_a_success_without_a_usable_stamp_is_rejected(
    replay: Replay, changes: dict[str, str]
) -> None:
    replay(_answer('timbrar33b64_ok.xml', **changes))
    with pytest.raises(PacRejected) as caught:
        await _pac().stamp(SEALED)
    assert caught.value.code == 'MF-ANSWER'


async def test_a_success_for_another_seal_is_rejected(replay: Replay) -> None:
    other = _recorded_stamp().replace(b'SelloCFD="', b'SelloCFD="X')
    replay(_answer('timbrar33b64_ok.xml', cfdi=base64.b64encode(other).decode()))
    with pytest.raises(PacRejected) as caught:
        await _pac().stamp(SEALED)
    assert caught.value.code == 'MF-ANSWER'


async def test_bad_input_is_rejected_before_any_call(
    replay: Replay, make_sealed: MakeSealed
) -> None:
    sent = replay()
    unreadable = make_sealed().replace(b'Total="116.00"', b'Total="abc"')
    cases: list[tuple[Any, str]] = [
        (SEALED.decode(), '301'),
        (b'not xml', '301'),
        (unreadable, '301'),
        (to_xml(invoice()), '302'),
    ]
    pac = _pac()
    for given, code in cases:
        for operation in (pac.stamp, pac.find_stamp):
            with pytest.raises(PacRejected) as caught:
                await operation(given)
            assert caught.value.code == code
    assert sent == []


async def test_find_stamp_returns_none_without_calling(replay: Replay) -> None:
    sent = replay()
    assert await _pac().find_stamp(SEALED) is None
    assert sent == []


@pytest.mark.parametrize('error', [PacUnavailable(), PacTimeout()])
async def test_transport_errors_reach_the_caller(replay: Replay, error: Exception) -> None:
    replay(error)
    with pytest.raises(type(error)):
        await _pac().stamp(SEALED)
