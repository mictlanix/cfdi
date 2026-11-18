"""Retired complement versions cannot be emitted (FR-023, SC-001, SC-008)."""

import importlib
import json
from importlib.resources import files

import pytest

import mictlanix.cfdi as cfdi
from tests.test_generated_models import GENERATOR

RETIRED_MODULES = (
    'cartaporte20',
    'cartaporte30',
    'comercioexterior11',
    'pagos10',
    'ecc11',
    'terceros11',
)
RETIRED_SCHEMAS = (
    'CartaPorte20.xsd',
    'CartaPorte30.xsd',
    'ComercioExterior11.xsd',
    'Pagos10.xsd',
    'ecc11.xsd',
    'terceros11.xsd',
)
MODEL_MODULES = {
    'cfdi40', 'tfd11', 'pagos20', 'nomina12', 'cartaporte31', 'comercioexterior20', 'implocal10',
    'divisas10', 'donat11', 'leyendasfiscales10', 'ine11', 'aerolineas10', 'detallista', 'tpe10',
    'ecc12', 'consumodecombustibles11', 'gastoshidrocarburos10', 'ingresoshidrocarburos10',
    'notariospublicos10', 'arteantiguedades10', 'pagoenespecie10', 'valesdedespensa10',
    'vehiculousado10', 'renovacionysustitucionvehiculos10', 'certificadodestruccion10',
    'servicioparcialconstruccion10', 'registrofiscal10', 'pfic10', 'iedu10', 'ventavehiculos11',
    'hidrocarburospetroliferos10',
}  # fmt: skip


@pytest.mark.parametrize('name', RETIRED_MODULES)
def test_no_module_for_a_retired_version(name: str) -> None:
    assert not hasattr(cfdi, name)
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(f'mictlanix.cfdi.{name}')


def test_no_schema_for_a_retired_version_is_vendored() -> None:
    manifest = json.loads(
        files('mictlanix.cfdi').joinpath('sat', 'manifest.json').read_text('utf-8')
    )
    vendored = {path.rsplit('/', 1)[-1] for path in manifest}
    assert vendored.isdisjoint(RETIRED_SCHEMAS)


def test_the_generator_covers_exactly_the_31_model_modules() -> None:
    assert set(GENERATOR.SCHEMAS) == MODEL_MODULES
    for name in MODEL_MODULES:
        assert importlib.import_module(f'mictlanix.cfdi.{name}')
        assert hasattr(cfdi, name) or name == 'cfdi40'
