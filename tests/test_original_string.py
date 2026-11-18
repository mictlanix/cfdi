from pathlib import Path

import pytest

from mictlanix.cfdi import NotCfdi40Error, ParseError, original_string

EXPECTED = Path(__file__).parent / 'fixtures' / 'expected'


def test_the_original_string_matches_the_one_written_by_hand() -> None:
    xml = (EXPECTED / 'ingreso.xml').read_bytes()
    expected = (EXPECTED / 'ingreso.cadena.txt').read_text(encoding='utf-8')
    assert expected.startswith('||4.0|')
    assert original_string(xml) == expected


def test_xml_that_is_not_well_formed_is_a_parse_error() -> None:
    with pytest.raises(ParseError) as caught:
        original_string(b'<cfdi:Comprobante xmlns:cfdi="http://www.sat.gob.mx/cfd/4">')
    assert caught.value.line is not None


def test_xml_that_is_not_a_cfdi_40_is_refused() -> None:
    with pytest.raises(NotCfdi40Error) as caught:
        original_string(
            b'<cfdi:Comprobante xmlns:cfdi="http://www.sat.gob.mx/cfd/3" Version="3.3"/>'
        )
    assert caught.value.version == '3.3'
    with pytest.raises(NotCfdi40Error):
        original_string(b'<x/>')
