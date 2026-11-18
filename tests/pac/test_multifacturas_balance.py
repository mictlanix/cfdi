"""User Story 3: the PAC account's remaining stamps."""

import pytest
from lxml import etree

from mictlanix.cfdi.pac import (
    MultifacturasPac,
    MultifacturasSettings,
    PacRejected,
    PacTimeout,
    PacUnavailable,
)
from tests.pac.conftest import MULTIFACTURAS, Replay

PAC = MultifacturasPac(MultifacturasSettings(user='USER', password='PASSWORD', production=False))


async def test_the_balance(replay: Replay) -> None:
    sent = replay('saldo.xml')
    assert await PAC.balance() == 20
    assert sent[0].url == 'https://ws.multifacturas.com/pac/index.php'
    assert sent[0].action == 'saldo'
    assert sent[0].params == {'rfc': 'USER', 'clave': 'PASSWORD'}


async def test_an_error_answer_is_rejected(replay: Replay) -> None:
    replay('saldo_error.xml')
    with pytest.raises(PacRejected) as caught:
        await PAC.balance()
    assert caught.value.code == 'SYN01'
    assert 'PASSWORD' not in str(caught.value)


async def test_a_balance_that_is_not_an_integer_is_rejected(replay: Replay) -> None:
    root = etree.fromstring((MULTIFACTURAS / 'saldo.xml').read_bytes())
    for node in root.iter():
        if isinstance(node.tag, str) and etree.QName(node).localname == 'saldo':
            node.text = 'veinte'
    replay(etree.tostring(root))
    with pytest.raises(PacRejected) as caught:
        await PAC.balance()
    assert caught.value.code == 'MF-ANSWER'


@pytest.mark.parametrize('error', [PacUnavailable(), PacTimeout()])
async def test_transport_errors_reach_the_caller(replay: Replay, error: Exception) -> None:
    replay(error)
    with pytest.raises(type(error)):
        await PAC.balance()
