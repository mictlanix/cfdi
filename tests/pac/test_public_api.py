"""mictlanix.cfdi.pac exports exactly what its contract lists, and depends on no caller's code."""

import ast
import importlib
import re
import sys
from pathlib import Path

import mictlanix.cfdi as cfdi
import mictlanix.cfdi.pac as pac

ROOT = Path(__file__).resolve().parent.parent.parent
CONTRACT = ROOT / 'specs' / '002-pac-interface-simulator' / 'contracts' / 'public-api.md'
PACKAGE = ROOT / 'src' / 'mictlanix' / 'cfdi' / 'pac'


def _contract_exports() -> set[str]:
    text = CONTRACT.read_text(encoding='utf-8')
    block = re.search(r'## Exports\n\n```python\n(.*?)```', text, re.S)
    assert block is not None
    code = re.sub(r'#[^\n]*', '', block.group(1))
    return set(re.findall(r'[A-Za-z_][A-Za-z0-9_]*', code))


def test_exports_equal_the_contract_exactly() -> None:
    assert set(pac.__all__) == _contract_exports()


def test_exports_have_no_duplicates() -> None:
    assert len(pac.__all__) == len(set(pac.__all__))


def test_every_export_is_importable() -> None:
    module = importlib.import_module('mictlanix.cfdi.pac')
    for name in pac.__all__:
        assert hasattr(module, name), name


def test_the_root_namespace_exports_none_of_them() -> None:
    assert set(cfdi.__all__) & _contract_exports() == set()


def _imported_modules(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding='utf-8'))
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            assert node.level == 0, f'{path.name}: relative import'
            assert node.module is not None
            names.append(node.module)
    return names


def test_the_package_imports_only_the_standard_library_lxml_and_the_library() -> None:
    files = sorted(PACKAGE.glob('*.py'))
    assert files
    for path in files:
        for name in _imported_modules(path):
            top = name.split('.')[0]
            allowed = (
                top in sys.stdlib_module_names
                or top == 'lxml'
                or name == 'mictlanix.cfdi'
                or name.startswith('mictlanix.cfdi.')
            )
            assert allowed, f'{path.name} imports {name}'
