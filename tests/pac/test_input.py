"""The input checks shared by every PAC client: a sealed CFDI 4.0 the library can read."""

import hashlib
from typing import Any

import pytest
from lxml import etree

from mictlanix.cfdi import to_xml
from mictlanix.cfdi.pac import PacRejected
from mictlanix.cfdi.pac._input import check
from tests.conftest import invoice
from tests.pac.conftest import MakeSealed


def _edited(xml: bytes, **attributes: str | None) -> bytes:
    root = etree.fromstring(xml)
    for name, value in attributes.items():
        if value is None:
            del root.attrib[name]
        else:
            root.set(name, value)
    return etree.tostring(root)


def _rejected(given: Any) -> PacRejected:
    with pytest.raises(PacRejected) as caught:
        check(given)
    assert caught.value.__cause__ is None
    assert caught.value.__suppress_context__
    return caught.value


def test_a_sealed_document_passes(make_sealed: MakeSealed) -> None:
    sealed = make_sealed()
    result = check(sealed)
    seal = etree.fromstring(sealed).get('Sello')
    assert result.seal == seal
    assert result.comprobante.Total is not None
    assert result.root.get('Sello') == seal
    assert result.key == 'seal:' + hashlib.sha256(seal.encode()).hexdigest()


def test_input_that_is_not_a_readable_cfdi_is_301(make_sealed: MakeSealed) -> None:
    sealed = make_sealed()
    for given in (
        sealed.decode(),
        None,
        b'not xml',
        b'<a/>',
        _edited(sealed, Total='abc'),
        _edited(sealed, Total=None),
    ):
        assert _rejected(given).code == '301'


def test_an_unsealed_document_is_302(make_sealed: MakeSealed) -> None:
    assert _rejected(to_xml(invoice())).code == '302'
    assert _rejected(_edited(make_sealed(), Sello='  ')).code == '302'
