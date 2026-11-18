"""mictlanix.cfdi.sat exports exactly what its contract lists, and nothing else exports them."""

import ast
import importlib
import re
from pathlib import Path

import mictlanix.cfdi as cfdi
import mictlanix.cfdi.pac as pac
import mictlanix.cfdi.sat as sat

ROOT = Path(__file__).resolve().parent.parent.parent
CONTRACT = ROOT / 'specs' / '004-sat-status-client' / 'contracts' / 'public-api.md'
PAC_PACKAGE = ROOT / 'src' / 'mictlanix' / 'cfdi' / 'pac'


def _contract_exports() -> set[str]:
    text = CONTRACT.read_text(encoding='utf-8')
    block = re.search(r'## Exports\n\n```python\n(.*?)```', text, re.S)
    assert block is not None
    code = re.sub(r'#[^\n]*', '', block.group(1))
    return set(re.findall(r'[A-Za-z_][A-Za-z0-9_]*', code))


def test_exports_equal_the_contract_exactly() -> None:
    assert set(sat.__all__) == _contract_exports()


def test_exports_have_no_duplicates_and_are_importable() -> None:
    assert len(sat.__all__) == len(set(sat.__all__))
    module = importlib.import_module('mictlanix.cfdi.sat')
    for name in sat.__all__:
        assert hasattr(module, name), name


def test_neither_the_root_nor_the_pac_namespace_exports_them() -> None:
    assert set(cfdi.__all__) & _contract_exports() == set()
    assert set(pac.__all__) & _contract_exports() == set()


def test_the_pac_package_never_imports_the_sat_package() -> None:
    for path in sorted(PAC_PACKAGE.glob('*.py')):
        for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
            if isinstance(node, ast.ImportFrom):
                assert not (node.module or '').startswith('mictlanix.cfdi.sat'), path.name
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith('mictlanix.cfdi.sat'), path.name
