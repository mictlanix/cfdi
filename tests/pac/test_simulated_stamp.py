"""User Story 1: stamping through the simulated PAC, safely."""

import asyncio
import base64
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from lxml import etree

from mictlanix.cfdi import _mexico, read, to_xml
from mictlanix.cfdi.pac import (
    SIMULATED_PAC_RFC,
    PacRejected,
    PacTimeout,
    PacUnavailable,
    SimulatedPac,
    StampOutcome,
)
from mictlanix.cfdi.pac._interface import stamp_of
from tests.conftest import invoice
from tests.pac.conftest import CFDI, Clock, MakeSealed, assert_valid_stamp

STAMPED = Path(__file__).resolve().parent.parent / 'fixtures' / 'stamped' / 'ingreso_timbrado.xml'


def edited(xml: bytes, receptor_rfc: bool = True, **attributes: str | None) -> bytes:
    """The document with root attributes changed (None removes one), seal left as it was."""
    root = etree.fromstring(xml)
    for name, value in attributes.items():
        if value is None:
            del root.attrib[name]
        else:
            root.set(name, value)
    if not receptor_rfc:
        receptor = root.find(f'{CFDI}Receptor')
        assert receptor is not None
        del receptor.attrib['Rfc']
    return etree.tostring(root, xml_declaration=True, encoding='UTF-8')


@pytest.fixture
def pac(clock: Clock) -> SimulatedPac:
    return SimulatedPac(clock=clock)


async def test_a_stamp(pac: SimulatedPac, make_sealed: MakeSealed, clock: Clock) -> None:
    sealed, other = make_sealed(), make_sealed()
    stamp = await pac.stamp(sealed)
    assert_valid_stamp(stamp, sealed, clock.now)
    assert stamp.timbre.UUID == stamp.timbre.UUID.upper()
    assert len(stamp.timbre.UUID) == 36
    assert len(base64.b64decode(stamp.timbre.SelloSAT, validate=True)) == 256
    assert SIMULATED_PAC_RFC == 'SIM010101SI0'
    second = await pac.stamp(other)
    assert_valid_stamp(second, other, clock.now)
    assert second.timbre.UUID != stamp.timbre.UUID


async def test_the_stamp_date_has_no_microseconds(make_sealed: MakeSealed) -> None:
    clock = Clock(datetime(2026, 11, 17, 12, 0, 0, 123456))
    sealed = make_sealed()
    stamp = await SimulatedPac(clock=clock).stamp(sealed)
    assert stamp.timbre.FechaTimbrado == datetime(2026, 11, 17, 12, 0, 0)
    assert_valid_stamp(stamp, sealed)


def test_stamp_of_upper_cases_the_uuid() -> None:
    xml = STAMPED.read_bytes()
    uuid = read(xml).Complemento[0].UUID  # type: ignore[union-attr]
    lowered = xml.replace(uuid.encode(), uuid.lower().encode())
    assert uuid.lower() != uuid
    assert stamp_of(lowered).timbre.UUID == uuid.upper()


async def test_the_default_clock_is_mexico_city_time(make_sealed: MakeSealed) -> None:
    sealed = make_sealed()
    stamp = await SimulatedPac().stamp(sealed)
    assert abs(stamp.timbre.FechaTimbrado - _mexico.now()) < timedelta(seconds=2)
    assert_valid_stamp(stamp, sealed)


async def test_stamping_is_idempotent(pac: SimulatedPac, make_sealed: MakeSealed) -> None:
    sealed = make_sealed()
    stamp = await pac.stamp(sealed)
    assert await pac.stamp(sealed) == stamp
    assert await pac.stamp(stamp.xml) == stamp
    assert await pac.find_stamp(sealed) == stamp
    assert_valid_stamp(stamp, sealed)


async def test_find_stamp_never_stamps(pac: SimulatedPac, make_sealed: MakeSealed) -> None:
    sealed = make_sealed()
    assert await pac.find_stamp(sealed) is None
    stamp = await pac.stamp(sealed)
    assert_valid_stamp(stamp, sealed)
    assert await pac.find_stamp(sealed) == stamp


def test_stamp_outcome_values() -> None:
    assert {m.name: m.value for m in StampOutcome} == {
        'STAMPED': 'stamped',
        'REJECTED': 'rejected',
        'UNAVAILABLE': 'unavailable',
        'TIMEOUT_STAMPED': 'timeout_stamped',
        'TIMEOUT_NOT_STAMPED': 'timeout_not_stamped',
    }


async def test_rejected(pac: SimulatedPac, make_sealed: MakeSealed) -> None:
    sealed = make_sealed()
    await pac.configure_stamp(
        sealed, StampOutcome.REJECTED, code='CFDI40102', message='Sello inválido'
    )
    with pytest.raises(PacRejected) as caught:
        await pac.stamp(sealed)
    assert (caught.value.code, caught.value.message) == ('CFDI40102', 'Sello inválido')
    assert await pac.find_stamp(sealed) is None


@pytest.mark.parametrize(
    ('code', 'message', 'expected'),
    [
        (None, None, ('CFDI40999', 'Rechazo simulado')),
        ('X1', None, ('X1', 'Rechazo simulado')),
        (None, 'No', ('CFDI40999', 'No')),
    ],
)
async def test_rejection_defaults(
    pac: SimulatedPac,
    make_sealed: MakeSealed,
    code: str | None,
    message: str | None,
    expected: tuple[str, str],
) -> None:
    sealed = make_sealed()
    await pac.configure_stamp(sealed, StampOutcome.REJECTED, code=code, message=message)
    with pytest.raises(PacRejected) as caught:
        await pac.stamp(sealed)
    assert (caught.value.code, caught.value.message) == expected


async def test_stamped_configured_is_a_normal_stamp_and_used_up(
    pac: SimulatedPac, make_sealed: MakeSealed
) -> None:
    sealed = make_sealed()
    await pac.configure_stamp(sealed, StampOutcome.STAMPED)
    stamp = await pac.stamp(sealed)
    assert_valid_stamp(stamp, sealed)
    assert await pac.stamp(sealed) == stamp


async def test_find_stamp_neither_uses_nor_honours_an_outcome(
    pac: SimulatedPac, make_sealed: MakeSealed
) -> None:
    sealed = make_sealed()
    await pac.configure_stamp(sealed, StampOutcome.UNAVAILABLE)
    assert await pac.find_stamp(sealed) is None
    with pytest.raises(PacUnavailable):
        await pac.stamp(sealed)


@pytest.mark.parametrize(
    ('outcome', 'error'),
    [
        (StampOutcome.REJECTED, PacRejected),
        (StampOutcome.UNAVAILABLE, PacUnavailable),
        (StampOutcome.TIMEOUT_STAMPED, PacTimeout),
        (StampOutcome.TIMEOUT_NOT_STAMPED, PacTimeout),
    ],
)
async def test_errors_on_an_already_stamped_document(
    pac: SimulatedPac, make_sealed: MakeSealed, outcome: StampOutcome, error: type[Exception]
) -> None:
    sealed = make_sealed()
    stamp = await pac.stamp(sealed)
    await pac.configure_stamp(sealed, outcome)
    with pytest.raises(error):
        await pac.stamp(sealed)
    assert await pac.find_stamp(sealed) == stamp
    assert await pac.stamp(sealed) == stamp


async def test_unavailable(pac: SimulatedPac, make_sealed: MakeSealed) -> None:
    sealed = make_sealed()
    await pac.configure_stamp(sealed, StampOutcome.UNAVAILABLE)
    with pytest.raises(PacUnavailable):
        await pac.stamp(sealed)
    assert await pac.find_stamp(sealed) is None


async def test_timeout_after_stamping(pac: SimulatedPac, make_sealed: MakeSealed) -> None:
    sealed = make_sealed()
    await pac.configure_stamp(sealed, StampOutcome.TIMEOUT_STAMPED)
    with pytest.raises(PacTimeout):
        await pac.stamp(sealed)
    found = await pac.find_stamp(sealed)
    assert found is not None
    assert_valid_stamp(found, sealed)
    assert await pac.stamp(sealed) == found


async def test_timeout_without_stamping(pac: SimulatedPac, make_sealed: MakeSealed) -> None:
    sealed = make_sealed()
    await pac.configure_stamp(sealed, StampOutcome.TIMEOUT_NOT_STAMPED)
    with pytest.raises(PacTimeout):
        await pac.stamp(sealed)
    assert await pac.find_stamp(sealed) is None
    stamp = await pac.stamp(sealed)
    assert_valid_stamp(stamp, sealed)


def _bad_inputs(make_sealed: MakeSealed) -> list[tuple[Any, str]]:
    sealed = make_sealed()
    return [
        (b'not xml', '301'),
        (b'<a/>', '301'),
        (sealed.decode(), '301'),
        (None, '301'),
        (to_xml(invoice()), '302'),
        (edited(make_sealed(), Sello=''), '302'),
        (edited(make_sealed(), Total='abc'), '301'),
        (edited(make_sealed(), Total=None), '301'),
        (edited(make_sealed(), receptor_rfc=False), '301'),
    ]


def _assert_clean(error: PacRejected, given: Any) -> None:
    assert error.__cause__ is None
    assert error.__suppress_context__
    if isinstance(given, bytes | str) and len(given) > 20:
        text = given.decode() if isinstance(given, bytes) else given
        for fragment in (text[:60], text[-60:]):
            assert fragment not in str(error)
            assert fragment not in repr(error)


async def test_bad_input_is_rejected_by_stamp_find_and_configure(
    pac: SimulatedPac, make_sealed: MakeSealed
) -> None:
    for given, code in _bad_inputs(make_sealed):
        for call in (
            pac.stamp(given),
            pac.find_stamp(given),
            pac.configure_stamp(given, StampOutcome.STAMPED),
        ):
            with pytest.raises(PacRejected) as caught:
                await call
            assert caught.value.code == code, given
            _assert_clean(caught.value, given)


async def test_a_document_edited_after_stamping_is_rejected(
    pac: SimulatedPac, make_sealed: MakeSealed
) -> None:
    sealed = make_sealed()
    await pac.stamp(sealed)
    with pytest.raises(PacRejected) as caught:
        await pac.stamp(edited(sealed, Total='abc'))
    assert caught.value.code == '301'


async def test_the_document_seal_is_not_verified(
    pac: SimulatedPac, make_sealed: MakeSealed
) -> None:
    changed = edited(make_sealed(), Folio='999999')
    stamp = await pac.stamp(changed)
    assert_valid_stamp(stamp, changed)


async def test_a_tfd_this_pac_has_no_record_of(
    pac: SimulatedPac, make_sealed: MakeSealed, clock: Clock
) -> None:
    for xml in (
        STAMPED.read_bytes(),
        (await SimulatedPac(clock=clock).stamp(make_sealed())).xml,
    ):
        with pytest.raises(PacRejected) as caught:
            await pac.stamp(xml)
        assert caught.value.code == '307'
        assert await pac.find_stamp(xml) is None


async def test_invalid_input_leaves_the_configured_outcome(
    pac: SimulatedPac, make_sealed: MakeSealed
) -> None:
    sealed = make_sealed()
    await pac.configure_stamp(sealed, StampOutcome.REJECTED, code='K')
    with pytest.raises(PacRejected) as caught:
        await pac.stamp(edited(sealed, Total='abc'))
    assert caught.value.code == '301'
    with pytest.raises(PacRejected) as caught:
        await pac.stamp(sealed)
    assert caught.value.code == 'K'


async def test_a_complement_is_created_before_the_addenda(
    pac: SimulatedPac, make_sealed: MakeSealed
) -> None:
    sealed = make_sealed(addenda=True)
    assert etree.fromstring(sealed).find(f'{CFDI}Complemento') is None
    stamp = await pac.stamp(sealed)
    assert_valid_stamp(stamp, sealed)
    tags = [child.tag for child in etree.fromstring(stamp.xml)]
    assert tags.index(f'{CFDI}Complemento') == tags.index(f'{CFDI}Addenda') - 1
    assert len(read(stamp.xml).Addenda) == 1


async def test_sequential_stamps_through_one_instance(
    pac: SimulatedPac, make_sealed: MakeSealed
) -> None:
    sealed = make_sealed()
    first, second = await asyncio.gather(pac.stamp(sealed), pac.stamp(sealed))
    assert first == second
