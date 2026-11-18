"""The committed model modules are exactly what the generator makes from the vendored XSDs."""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parent.parent
PACKAGE = ROOT / 'src' / 'mictlanix' / 'cfdi'


def _generator() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        'generate_models', ROOT / 'tools' / 'generate_models.py'
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules['generate_models'] = module
    spec.loader.exec_module(module)
    return module


GENERATOR = _generator()


@pytest.mark.parametrize('module', sorted(GENERATOR.SCHEMAS))
def test_committed_module_equals_a_fresh_generation(module: str) -> None:
    committed = (PACKAGE / f'{module}.py').read_text(encoding='utf-8')
    assert GENERATOR.generate(module) == committed


def test_a_reused_element_name_without_a_clash_entry_fails_clearly() -> None:
    with pytest.raises(GENERATOR.GeneratorError, match='Impuestos'):
        GENERATOR.generate('cfdi40', clashes={})
