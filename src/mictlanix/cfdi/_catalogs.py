"""The SAT catalog data vendored under ``sat/catalogs/``, loaded once per process."""

import json
from decimal import Decimal
from functools import cache
from importlib.resources import files
from typing import Any


@cache
def load(name: str) -> Any:
    text = (
        files('mictlanix.cfdi')
        .joinpath('_sat_files', 'catalogs', f'{name}.json')
        .read_text('utf-8')
    )
    return json.loads(text)


def currency_decimals() -> dict[str, int]:
    """Currency key to its number of decimals (``c_Moneda``)."""
    decimals: dict[str, int] = load('c_Moneda')
    return decimals


def regimen_persona() -> dict[str, dict[str, bool]]:
    """Tax regime to the persona types it applies to (``c_RegimenFiscal``)."""
    regimen: dict[str, dict[str, bool]] = load('c_RegimenFiscal')
    return regimen


def uso_cfdi() -> dict[str, dict[str, Any]]:
    """CFDI use to the persona types and recipient regimes it applies to (``c_UsoCFDI``)."""
    uso: dict[str, dict[str, Any]] = load('c_UsoCFDI')
    return uso


def rate_allowed(impuesto: str, factor: str, rate: Decimal, direction: str) -> bool:
    """Whether ``c_TasaOCuota`` allows the rate for the tax and factor, transferred or withheld."""
    for entry in load('c_TasaOCuota'):
        if entry['impuesto'] != impuesto or entry['factor'] != factor or not entry[direction]:
            continue
        if entry['rango']:
            if Decimal(entry['minimo']) <= rate <= Decimal(entry['maximo']):
                return True
        elif rate == Decimal(entry['maximo']):
            return True
    return False


def tax_id_formats() -> dict[str, str]:
    """Country to its tax-ID pattern, for countries without an online register (``c_Pais``)."""
    formats: dict[str, str] = load('c_Pais')
    return formats


def required_taxes() -> dict[str, dict[str, bool]]:
    """Product keys that require a transferred tax (``c_ClaveProdServ``)."""
    required: dict[str, dict[str, bool]] = load('c_ClaveProdServ')
    return required


@cache
def aduanas() -> frozenset[str]:
    return frozenset(load('c_Aduana'))


@cache
def patentes() -> frozenset[str]:
    return frozenset(load('c_PatenteAduanal'))


def pedimento_counts() -> dict[str, int]:
    """'aduana|patente|ejercicio' to the highest consecutive number in use."""
    counts: dict[str, int] = load('c_NumPedimentoAduana')
    return counts
