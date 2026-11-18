"""Validation of a document against the SAT's XSDs."""

from __future__ import annotations

import re
from dataclasses import replace
from typing import TYPE_CHECKING, Any

from mictlanix.cfdi import _rules, _sat
from mictlanix.cfdi._compute import compute
from mictlanix.cfdi._errors import Violation
from mictlanix.cfdi._xml import COMPLEMENT_NOT_MODELLED, RawXml, build

if TYPE_CHECKING:
    from mictlanix.cfdi.cfdi40 import Comprobante

# Format-valid stand-ins for the seal attributes, which the XSD requires but sealing writes.
_SEAL_PLACEHOLDERS = {
    'Sello': 'AA==',
    'NoCertificado': '0' * 20,
    'Certificado': 'AA==',
}

_FACET_WORDS = {
    'MINLENGTH': 'minLength',
    'MAXLENGTH': 'maxLength',
    'MININCLUSIVE': 'minInclusive',
    'MAXINCLUSIVE': 'maxInclusive',
    'MINEXCLUSIVE': 'minExclusive',
    'MAXEXCLUSIVE': 'maxExclusive',
    'TOTALDIGITS': 'totalDigits',
    'FRACTIONDIGITS': 'fractionDigits',
}
_ATTRIBUTE = re.compile(r"attribute '([^']+)'")


def xsd_rule(type_name: str) -> str:
    """The XML Schema name of a libxml2 validity error, such as ``cvc-complex-type.2.4``."""
    parts = type_name.removeprefix('SCHEMAV_').split('_')
    numbers: list[str] = []
    while parts and parts[-1].isdigit():
        numbers.insert(0, parts.pop())
    words = [_FACET_WORDS.get(part, part.lower()) for part in parts]
    return '-'.join(words) + ''.join(f'.{number}' for number in numbers)


def _schema_urls(comprobante: Comprobante) -> tuple[str, ...]:
    models: list[Any] = [comprobante, *comprobante.Complemento]
    for concepto in comprobante.Conceptos:
        models.extend(concepto.ComplementoConcepto)
    urls = {
        model.__xml__.schema_location
        for model in models
        if not isinstance(model, RawXml) and model.__xml__.schema_location
    }
    return tuple(sorted(urls))


def xsd_violations(comprobante: Comprobante) -> list[Violation]:
    """Every violation of the SAT's XSDs, plus values and complements that cannot be emitted.

    A document holding a complement the library does not model is reported for that alone.
    """
    document = replace(comprobante, Addenda=[]) if comprobante.Addenda else comprobante
    root, violations = build(document)
    if any(v.rule == COMPLEMENT_NOT_MODELLED for v in violations):
        return [v for v in violations if v.rule == COMPLEMENT_NOT_MODELLED]
    for attribute, placeholder in _SEAL_PLACEHOLDERS.items():
        if root.get(attribute) is None:
            root.set(attribute, placeholder)
    schema = _sat.schema(_schema_urls(comprobante))
    schema.validate(root)
    for error in schema.error_log:
        match = _ATTRIBUTE.search(error.message)
        violations.append(
            Violation(
                node=error.path or '/',
                attribute=match.group(1) if match else None,
                rule=xsd_rule(error.type_name),
                message=error.message,
            )
        )
    return violations


def validate(comprobante: Comprobante) -> list[Violation]:
    """Every violation found in the document; an empty list means it is valid.

    Computes the derived values first, then checks the XSDs and the implemented Anexo 20
    rules; the rules run whether or not the XSD check found violations. Does not raise for an
    invalid document.
    """
    computed = compute(comprobante)
    found = xsd_violations(computed)
    if any(v.rule == COMPLEMENT_NOT_MODELLED for v in found):
        return found
    return found + _rules.violations(computed)
