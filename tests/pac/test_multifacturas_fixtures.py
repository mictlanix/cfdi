"""The recorded Multifacturas answers are scrubbed: no credentials, real RFCs or PAC payloads."""

import base64
import binascii
import re
from pathlib import Path

from lxml import etree

FIXTURES = Path(__file__).resolve().parent.parent / 'fixtures' / 'multifacturas'
ALLOWED_RFCS = {'EKU9003173C9', 'URE180429TM6', 'XAXX010101000', 'AAA010101AAA'}
RFC = re.compile(rb'\b[A-Z&\xc3\x91]{3,4}[0-9]{6}[A-Z0-9]{3}\b')
CREDENTIALS = {'rfc', 'clave', 'usuario', 'pass', 'pwd'}
BLANK = {'png', 'mensaje_original', 'mensaje_original_pac_json'}
DOCUMENTS = {'cfdi', 'acuse', 'acuseSATResult'}  # fields holding a Base64 document


def _listed() -> list[str]:
    readme = (FIXTURES / 'README.md').read_text(encoding='utf-8')
    return re.findall(r'^\| `([^`]+\.xml)` \|', readme, re.M)


def _leaves(path: Path) -> dict[str, str]:
    root = etree.fromstring(path.read_bytes())
    return {
        etree.QName(node).localname: node.text or ''
        for node in root.iter()
        if isinstance(node.tag, str) and len(node) == 0
    }


def _decoded(text: str) -> bytes:
    try:
        return base64.b64decode(text, validate=True)
    except (binascii.Error, ValueError):
        return b''


def test_every_listed_fixture_exists() -> None:
    names = _listed()
    assert names
    for name in names:
        assert (FIXTURES / name).is_file(), name
    assert sorted(names) == sorted(p.name for p in FIXTURES.glob('*.xml'))


def test_fixtures_hold_no_credentials_payloads_or_real_rfcs() -> None:
    for path in FIXTURES.glob('*.xml'):
        raw = path.read_bytes()
        fields = _leaves(path)
        for name in CREDENTIALS & fields.keys():
            assert fields[name] in ('', 'USER', 'PASSWORD'), (path.name, name)
        for name in BLANK & fields.keys():
            assert fields[name] == '', (path.name, name)
        texts = [raw] + [_decoded(fields[name]) for name in DOCUMENTS & fields.keys()]
        for text in texts:
            assert b'||' not in text, path.name
            assert set(m.decode() for m in RFC.findall(text)) <= ALLOWED_RFCS, path.name
