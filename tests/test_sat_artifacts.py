import hashlib
import json
from datetime import date
from importlib.resources import files
from importlib.resources.abc import Traversable

import pytest
from lxml import etree

from mictlanix.cfdi import _sat

SAT_DIR = files('mictlanix.cfdi').joinpath('sat')

CFDV40 = _sat.SAT_BASE + 'cfd/4/cfdv40.xsd'
CADENA_40 = _sat.SAT_BASE + 'cfd/4/cadenaoriginal_4_0/cadenaoriginal_4_0.xslt'
TFD_XSD = _sat.SAT_BASE + 'cfd/TimbreFiscalDigital/TimbreFiscalDigitalv11.xsd'
CADENA_TFD = _sat.SAT_BASE + 'cfd/TimbreFiscalDigital/cadenaoriginal_TFD_1_1.xslt'


def _manifest() -> dict[str, dict[str, str]]:
    data: dict[str, dict[str, str]] = json.loads(
        SAT_DIR.joinpath('manifest.json').read_text(encoding='utf-8')
    )
    return data


def _walk(node: Traversable, prefix: str) -> list[str]:
    paths = []
    for child in node.iterdir():
        name = f'{prefix}/{child.name}' if prefix else child.name
        if child.is_dir():
            paths.extend(_walk(child, name))
        else:
            paths.append(name)
    return paths


def test_every_manifest_entry_is_vendored_unmodified_and_dated() -> None:
    manifest = _manifest()
    assert manifest
    for path, entry in manifest.items():
        content = SAT_DIR.joinpath(*path.split('/')).read_bytes()
        assert hashlib.sha256(content).hexdigest() == entry['sha256'], path
        assert entry['url'].startswith('http://'), path
        date.fromisoformat(entry['published'])
        date.fromisoformat(entry['retrieved'])


def test_every_vendored_file_is_in_the_manifest() -> None:
    vendored = set(_walk(SAT_DIR.joinpath('sitio_internet'), 'sitio_internet'))
    assert vendored
    assert vendored <= set(_manifest())


def test_sitio_internet_files_mirror_their_sat_url() -> None:
    for path, entry in _manifest().items():
        if path.startswith('sitio_internet/'):
            assert entry['url'] == 'http://www.sat.gob.mx/' + path


def test_original_string_stylesheets_compile_offline() -> None:
    assert isinstance(_sat.stylesheet(CADENA_40), etree.XSLT)
    assert isinstance(_sat.stylesheet(CADENA_TFD), etree.XSLT)


def test_cfdi_and_tfd_schemas_compile_offline() -> None:
    assert isinstance(_sat.schema((CFDV40,)), etree.XMLSchema)
    assert isinstance(_sat.schema((CFDV40, TFD_XSD)), etree.XMLSchema)


def test_parser_never_requests_an_external_dtd() -> None:
    # The resolver raises for any URL outside the SAT, so a request would fail the parse.
    root = etree.fromstring(b'<!DOCTYPE x SYSTEM "http://192.0.2.1/x.dtd"><x/>', _sat.parser())
    assert root.tag == 'x'


def test_an_import_outside_the_sat_raises() -> None:
    xsd = (
        b'<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">'
        b'<xs:import namespace="urn:x" schemaLocation="http://example.com/x.xsd"/>'
        b'</xs:schema>'
    )
    # lxml reports a resolver's refusal as a schema parse error; either way nothing is fetched.
    with pytest.raises((_sat.SatArtifactError, etree.XMLSchemaParseError), match='example.com'):
        etree.XMLSchema(etree.fromstring(xsd, _sat.parser()))


def test_a_sat_url_that_is_not_vendored_raises() -> None:
    with pytest.raises(_sat.SatArtifactError, match='not vendored'):
        _sat.load(_sat.SAT_BASE + 'cfd/no/such/file.xsd')


def test_a_url_outside_the_sat_raises() -> None:
    with pytest.raises(_sat.SatArtifactError, match='outside'):
        _sat.load('http://example.com/schema.xsd')


def test_catalog_data_is_vendored_with_its_source() -> None:
    manifest = _manifest()
    entry = manifest['catalogs/c_Moneda.json']
    assert entry['url'].startswith('http://omawww.sat.gob.mx/')
    assert entry['url'].endswith('.xls')
    vendored = set(_walk(SAT_DIR.joinpath('catalogs'), 'catalogs'))
    assert vendored <= set(manifest)


def test_currency_decimals_come_from_the_sat_catalog() -> None:
    decimals = json.loads(SAT_DIR.joinpath('catalogs', 'c_Moneda.json').read_text('utf-8'))
    assert decimals['MXN'] == 2
    assert decimals['USD'] == 2
    assert decimals['JPY'] == 0
    assert decimals['XXX'] == 0


def _catalog(name: str) -> object:
    return json.loads(SAT_DIR.joinpath('catalogs', f'{name}.json').read_text('utf-8'))


def test_every_catalog_the_rules_need_is_vendored() -> None:
    manifest = _manifest()
    for name in (
        'c_RegimenFiscal',
        'c_UsoCFDI',
        'c_TasaOCuota',
        'c_Pais',
        'c_ClaveProdServ',
        'c_Aduana',
        'c_PatenteAduanal',
        'c_NumPedimentoAduana',
    ):
        assert f'catalogs/{name}.json' in manifest, name


def test_catalog_contents_have_the_expected_shape() -> None:
    regimen = _catalog('c_RegimenFiscal')
    assert regimen['601'] == {'fisica': False, 'moral': True}  # type: ignore[index]
    assert regimen['605'] == {'fisica': True, 'moral': False}  # type: ignore[index]
    uso = _catalog('c_UsoCFDI')
    assert '601' in uso['G03']['regimenes']  # type: ignore[index]
    tasas = _catalog('c_TasaOCuota')
    assert {
        'impuesto': '002',
        'factor': 'Tasa',
        'rango': False,
        'minimo': None,
        'maximo': '0.16',
        'traslado': True,
        'retencion': False,
    } in tasas  # type: ignore[operator]
    assert _catalog('c_Pais') == {'CAN': '[0-9]{9}', 'USA': '[0-9]{9}'}
    assert all(v == {'iva': True, 'ieps': False} for v in _catalog('c_ClaveProdServ').values())  # type: ignore[attr-defined]
    assert '01' in _catalog('c_Aduana')  # type: ignore[operator]
    assert '3173' in _catalog('c_PatenteAduanal')  # type: ignore[operator]
    assert _catalog('c_NumPedimentoAduana')['01|3173|2007'] == 999999  # type: ignore[index]
