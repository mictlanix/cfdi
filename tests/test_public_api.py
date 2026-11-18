"""The public API is exactly what contracts/public-api.md lists, and nothing else."""

import importlib
import re
from pathlib import Path

import mictlanix.cfdi as cfdi

CONTRACT = (
    Path(__file__).resolve().parent.parent
    / 'specs'
    / '001-cfdi40-complements-sealing'
    / 'contracts'
    / 'public-api.md'
)


def _contract_exports() -> set[str]:
    text = CONTRACT.read_text(encoding='utf-8')
    block = re.search(r'## Exports\n\n```python\n(.*?)```', text, re.S)
    assert block is not None
    code = re.sub(r'#[^\n]*', '', block.group(1))
    return set(re.findall(r'[A-Za-z_][A-Za-z0-9_]*', code))


def test_every_export_is_listed_in_the_contract() -> None:
    unlisted = set(cfdi.__all__) - _contract_exports()
    assert unlisted == set()


def test_exports_have_no_duplicates() -> None:
    assert len(cfdi.__all__) == len(set(cfdi.__all__))


def test_every_export_is_importable() -> None:
    module = importlib.import_module('mictlanix.cfdi')
    for name in cfdi.__all__:
        assert hasattr(module, name), name


def test_exports_equal_the_contract_exactly() -> None:
    assert set(cfdi.__all__) == _contract_exports()
