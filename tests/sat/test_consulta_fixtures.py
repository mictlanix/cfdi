"""The SAT's status answers: every listed file exists, every file is listed, no real RFC."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SAT = ROOT / 'tests' / 'fixtures' / 'sat'
RFC = re.compile(r'\b[A-ZÑ&]{3,4}[0-9]{6}[A-Z0-9]{3}\b')
TEST_RFCS = {'EKU9003173C9', 'URE180429TM6'}


def _listed() -> set[str]:
    readme = (SAT / 'README.md').read_text(encoding='utf-8')
    return set(re.findall(r'^\| `([^`]+)` \|', readme, re.M))


def test_every_listed_fixture_exists_and_every_fixture_is_listed() -> None:
    files = {path.name for path in SAT.glob('consulta_*.xml')}
    assert files
    assert _listed() == files


def test_no_fixture_carries_a_real_rfc() -> None:
    for path in SAT.glob('*.xml'):
        found = set(RFC.findall(path.read_text(encoding='utf-8')))
        assert found <= TEST_RFCS, path.name
