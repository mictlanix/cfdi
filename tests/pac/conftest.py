"""Fixtures for the PAC tests: sealed documents, a clock the tests control, the stamp checks."""

from __future__ import annotations

import itertools
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any

import pytest
from lxml import etree

from mictlanix.cfdi import (
    CSD,
    RawXml,
    _sat,
    original_string,
    read,
    seal,
    tfd11,
    tfd_original_string,
    timbre,
)
from tests.conftest import CsdFiles, invoice

TFD_XSD = _sat.SAT_BASE + 'cfd/TimbreFiscalDigital/TimbreFiscalDigitalv11.xsd'
CFDI = '{http://www.sat.gob.mx/cfd/4}'
_folios = itertools.count(1)

MakeSealed = Callable[..., bytes]


@pytest.fixture
def make_sealed(csd: CSD) -> MakeSealed:
    """A factory: each call seals a new income document (a new Folio, so a new seal)."""

    def make(*, addenda: bool = False, **changes: Any) -> bytes:
        values: dict[str, Any] = {'Folio': str(next(_folios))}
        if addenda:
            values['Addenda'] = [RawXml(b'<Extra xmlns="urn:example">1</Extra>')]
        values.update(changes)
        return seal(invoice(totals=False, **values), csd)

    return make


class Clock:
    """A clock the tests move by hand; calling it returns ``now``."""

    def __init__(self, now: datetime = datetime(2026, 11, 17, 12, 0, 0)) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now

    def advance(self, delta: timedelta) -> None:
        self.now += delta


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def credentials(csd_files: CsdFiles) -> Any:
    from mictlanix.cfdi.pac import CsdCredentials

    return CsdCredentials(
        certificate=csd_files.certificate,
        private_key=csd_files.private_key,
        password=csd_files.password,
    )


def seal_of(xml: bytes) -> str:
    value = etree.fromstring(xml).get('Sello')
    assert value is not None
    return value


def assert_valid_stamp(stamp: Any, sealed: bytes, clock_now: datetime | None = None) -> None:
    """The checks of spec SC-002 on any stamp the simulated PAC returns."""
    tfd = stamp.timbre
    assert tfd.RfcProvCertif == 'SIM010101SI0'
    assert tfd.NoCertificadoSAT == '00001000000000000000'
    assert tfd.SelloCFD == seal_of(sealed)
    if clock_now is not None:
        assert tfd.FechaTimbrado == clock_now
    assert timbre(read(stamp.xml)) == tfd
    element = etree.fromstring(stamp.xml).find(f'.//{{{tfd11.NAMESPACE}}}TimbreFiscalDigital')
    assert element is not None
    schema = _sat.schema((TFD_XSD,))
    assert schema.validate(element), schema.error_log
    assert tfd_original_string(stamp.xml) == (
        f'||1.1|{tfd.UUID}|{tfd.FechaTimbrado:%Y-%m-%dT%H:%M:%S}|SIM010101SI0|'
        f'{tfd.SelloCFD}|00001000000000000000||'
    )
    assert original_string(stamp.xml) == original_string(sealed)
