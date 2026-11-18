"""The Anexo 20 rules this library checks, and its own rules on complement placement.

Every rule listed as implemented in ``contracts/validation-rules.md`` is one function here,
registered under its SAT code. Rules run on the document after its derived values are computed.
A rule never raises: when a value it needs is missing or not finite, it reports nothing and
leaves the problem to the XSD. Violations point at the element and attribute the SAT's error
matrix names for the rule.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable, Iterator
from decimal import ROUND_CEILING, ROUND_DOWN, Decimal, localcontext
from typing import Any

from mictlanix.cfdi import _catalogs
from mictlanix.cfdi._compute import EXENTO, local_taxes, round_amount, sum_amounts
from mictlanix.cfdi._errors import Violation
from mictlanix.cfdi._xml import ConceptComplement, DocumentComplement, RawXml
from mictlanix.cfdi.cfdi40 import Comprobante, Concepto

COMPLEMENT_DOCUMENT_TYPE = 'complement-document-type'
COMPLEMENT_LEVEL = 'complement-level'

# Complement root (namespace, element) to the document types its standard allows. A complement
# whose standard does not restrict the document type has no entry.
ALLOWED_DOCUMENT_TYPES: dict[tuple[str, str], frozenset[str]] = {
    ('http://www.sat.gob.mx/Pagos20', 'Pagos'): frozenset({'P'}),
    ('http://www.sat.gob.mx/nomina12', 'Nomina'): frozenset({'N'}),
    ('http://www.sat.gob.mx/CartaPorte31', 'CartaPorte'): frozenset({'I', 'T'}),
    ('http://www.sat.gob.mx/ComercioExterior20', 'ComercioExterior'): frozenset({'I', 'T'}),
    ('http://www.sat.gob.mx/EstadoDeCuentaCombustible12', 'EstadoDeCuentaCombustible'): frozenset(
        {'I'}
    ),
    ('http://www.sat.gob.mx/hidrocarburospetroliferos', 'HidroYPetro'): frozenset({'I', 'E'}),
}

DOC = '/cfdi:Comprobante'
GENERIC_NATIONAL = 'XAXX010101000'
GENERIC_FOREIGN = 'XEXX010101000'
GENERIC = (GENERIC_NATIONAL, GENERIC_FOREIGN)
PUBLICO = 'PUBLICO EN GENERAL'
EXT = 'EXT990101NI1'
EXT_NOMBRE = (
    'EXPEDICIÓN DE CFDI POR RESIDENTES EN MÉXICO QUE PRESTAN SERVICIOS DE INTERMEDIACIÓN '
    'ENTRE TERCEROS A OFERENTES DE BIENES Y SERVICIOS RESIDENTES EN EL EXTRANJERO'
)
HIDROCARBUROS_KEYS = frozenset({'15101505', '15101514', '15101515'})
HIDROCARBUROS = ('http://www.sat.gob.mx/hidrocarburospetroliferos', 'HidroYPetro')
TINY = Decimal('1E-12')
_PEDIMENTO = re.compile(r'(\d{2})  (\d{2})  (\d{4})  \d(\d{6})')

Check = Callable[[Comprobante], Iterator[Violation]]
_RULES: dict[str, Check] = {}


def rule(code: str, message: str) -> Callable[[Callable[[Comprobante], Iterator[Any]]], Check]:
    """Register a rule. The function yields (node, attribute) for each offending value."""

    def register(function: Callable[[Comprobante], Iterator[Any]]) -> Check:
        def check(comprobante: Comprobante) -> Iterator[Violation]:
            for node, attribute in function(comprobante):
                yield Violation(node=node, attribute=attribute, rule=code, message=message)

        _RULES[code] = check
        return check

    return register


def implemented_codes() -> set[str]:
    """The SAT codes of every implemented Anexo 20 rule."""
    return set(_RULES)


def violations(comprobante: Comprobante) -> list[Violation]:
    found: list[Violation] = []
    for check in _RULES.values():
        found.extend(check(comprobante))
    found.extend(_complement_document_type(comprobante))
    found.extend(_complement_level(comprobante))
    return found


# Helpers ------------------------------------------------------------------------------------


def _finite(*values: Decimal | None) -> bool:
    return all(value is not None and value.is_finite() for value in values)


def _places(value: Decimal) -> int:
    exponent = value.as_tuple().exponent
    return -exponent if isinstance(exponent, int) and exponent < 0 else 0


def _too_many_decimals(value: Decimal | None, places: int | None) -> bool:
    return places is not None and _finite(value) and _places(value) > places  # type: ignore[arg-type]


def _currency(comprobante: Comprobante) -> int | None:
    return _catalogs.currency_decimals().get(comprobante.Moneda)


def _persona(rfc: str) -> str | None:
    return {12: 'moral', 13: 'fisica'}.get(len(rfc))


def _indexed(path: str, index: int, count: int) -> str:
    return f'{path}[{index + 1}]' if count > 1 else path


def _numbered[T](base: str, items: list[T]) -> Iterator[tuple[str, T]]:
    for index, item in enumerate(items):
        yield _indexed(base, index, len(items)), item


def _conceptos(comprobante: Comprobante) -> Iterator[tuple[str, Concepto]]:
    yield from _numbered(f'{DOC}/cfdi:Conceptos/cfdi:Concepto', comprobante.Conceptos)


def _concept_traslados(comprobante: Comprobante) -> Iterator[tuple[str, Any]]:
    for path, concepto in _conceptos(comprobante):
        if concepto.Impuestos is not None:
            base = f'{path}/cfdi:Impuestos/cfdi:Traslados/cfdi:Traslado'
            yield from _numbered(base, concepto.Impuestos.Traslados)


def _concept_retenciones(comprobante: Comprobante) -> Iterator[tuple[str, Any]]:
    for path, concepto in _conceptos(comprobante):
        if concepto.Impuestos is not None:
            base = f'{path}/cfdi:Impuestos/cfdi:Retenciones/cfdi:Retencion'
            yield from _numbered(base, concepto.Impuestos.Retenciones)


def _within_limits(amount: Decimal, lower: Decimal, upper: Decimal, places: int) -> bool:
    """Anexo 20: the lower limit is truncated and the upper rounded up, to the amount's decimals."""
    step = Decimal(1).scaleb(-places)
    with localcontext() as context:
        context.prec = 60
        low = lower.quantize(step, rounding=ROUND_DOWN)
        high = upper.quantize(step, rounding=ROUND_CEILING)
    return low <= amount <= high


def _amount_ok(cantidad: Decimal, valor: Decimal, importe: Decimal) -> bool:
    """Importe within the limits Cantidad and ValorUnitario allow (CFDI40167, CFDI40198)."""
    with localcontext() as context:
        context.prec = 60
        half_cantidad = Decimal(1).scaleb(-_places(cantidad)) / 2
        half_valor = Decimal(1).scaleb(-_places(valor)) / 2
        lower = (cantidad - half_cantidad) * (valor - half_valor)
        upper = (cantidad + half_cantidad - TINY) * (valor + half_valor - TINY)
    return _within_limits(importe, lower, upper, _places(importe))


def _tax_ok(base: Decimal, rate: Decimal, importe: Decimal) -> bool:
    """A tax Importe within the limits Base and TasaOCuota allow (CFDI40180, CFDI40186)."""
    with localcontext() as context:
        context.prec = 60
        half_base = Decimal(1).scaleb(-_places(base)) / 2
        lower = (base - half_base) * rate
        upper = (base + half_base - TINY) * rate
    return _within_limits(importe, lower, upper, _places(importe))


def _pedimento_ok(numero: str) -> bool:
    """Customs office, broker licence and consecutive number of a NumeroPedimento.

    A value that does not match the XSD pattern is left to the XSD. The year bound needs the
    stamping time and is not checked.
    """
    match = _PEDIMENTO.fullmatch(numero)
    if match is None:
        return True
    year, aduana, patente, consecutive = match.groups()
    count = _catalogs.pedimento_counts().get(f'{aduana}|{patente}|20{year}')
    return (
        aduana in _catalogs.aduanas()
        and patente in _catalogs.patentes()
        and count is not None
        and 1 <= int(consecutive) <= count
    )


def _taxes(concepto: Concepto) -> Iterable[Any]:
    if concepto.Impuestos is None:
        return []
    return [*concepto.Impuestos.Traslados, *concepto.Impuestos.Retenciones]


# Comprobante --------------------------------------------------------------------------------


@rule('CFDI40103', 'FormaPago must be absent for types T, N and P')
def _40103(c: Comprobante) -> Iterator[Any]:
    if c.TipoDeComprobante in ('T', 'N', 'P') and c.FormaPago is not None:
        yield DOC, 'FormaPago'


@rule('CFDI40105', 'FormaPago must be 99 when MetodoPago is PPD')
def _40105(c: Comprobante) -> Iterator[Any]:
    if c.MetodoPago == 'PPD' and c.TipoDeComprobante not in ('T', 'N', 'P') and c.FormaPago != '99':
        yield DOC, 'FormaPago'


@rule('CFDI40107', "SubTotal has more decimals than the currency's")
def _40107(c: Comprobante) -> Iterator[Any]:
    if _too_many_decimals(c.SubTotal, _currency(c)):
        yield DOC, 'SubTotal'


@rule('CFDI40108', 'SubTotal is not the rounded sum of the concept amounts')
def _40108(c: Comprobante) -> Iterator[Any]:
    places = _currency(c)
    if c.TipoDeComprobante not in ('I', 'E', 'N') or places is None:
        return
    expected = round_amount(sum_amounts(x.Importe for x in c.Conceptos), places)
    if expected is not None and _finite(c.SubTotal) and c.SubTotal != expected:
        yield DOC, 'SubTotal'


@rule('CFDI40109', 'SubTotal must be zero for types T and P')
def _40109(c: Comprobante) -> Iterator[Any]:
    if c.TipoDeComprobante in ('T', 'P') and _finite(c.SubTotal) and c.SubTotal != 0:
        yield DOC, 'SubTotal'


@rule('CFDI40110', 'Descuento is greater than SubTotal')
def _40110(c: Comprobante) -> Iterator[Any]:
    if _finite(c.Descuento, c.SubTotal) and c.Descuento > c.SubTotal:  # type: ignore[operator]
        yield DOC, 'Descuento'


@rule('CFDI40111', 'Descuento does not match the concept discounts')
def _40111(c: Comprobante) -> Iterator[Any]:
    discounts = [x.Descuento for x in c.Conceptos if x.Descuento is not None]
    if c.TipoDeComprobante not in ('I', 'E', 'N'):
        if discounts:
            yield DOC, 'Descuento'
        return
    if not discounts:
        if c.Descuento is not None:
            yield DOC, 'Descuento'
        return
    places = _currency(c)
    expected = None if places is None else round_amount(sum_amounts(discounts), places)
    if c.Descuento is None or (
        expected is not None and _finite(c.Descuento) and c.Descuento != expected
    ):
        yield DOC, 'Descuento'


@rule('CFDI40112', "Descuento has more decimals than the currency's")
def _40112(c: Comprobante) -> Iterator[Any]:
    if _too_many_decimals(c.Descuento, _currency(c)):
        yield DOC, 'Descuento'


@rule('CFDI40114', 'TipoCambio must be 1 when Moneda is MXN')
def _40114(c: Comprobante) -> Iterator[Any]:
    if c.Moneda == 'MXN' and _finite(c.TipoCambio) and c.TipoCambio != 1:
        yield DOC, 'TipoCambio'


@rule('CFDI40115', 'TipoCambio is required when Moneda is neither MXN nor XXX')
def _40115(c: Comprobante) -> Iterator[Any]:
    if c.Moneda not in ('MXN', 'XXX') and c.TipoCambio is None:
        yield DOC, 'TipoCambio'


@rule('CFDI40116', 'TipoCambio must be absent when Moneda is XXX')
def _40116(c: Comprobante) -> Iterator[Any]:
    if c.Moneda == 'XXX' and c.TipoCambio is not None:
        yield DOC, 'TipoCambio'


@rule('CFDI40119', 'Total is not SubTotal - Descuento + transferred - withheld taxes')
def _40119(c: Comprobante) -> Iterator[Any]:
    impuestos = c.Impuestos
    parts = [
        c.SubTotal,
        -(c.Descuento or Decimal(0)),
        impuestos.TotalImpuestosTrasladados or Decimal(0) if impuestos else Decimal(0),
        -(impuestos.TotalImpuestosRetenidos or Decimal(0)) if impuestos else Decimal(0),
        local_taxes(c),
    ]
    expected = sum_amounts(parts)
    if expected is not None and _finite(c.Total) and c.Total != expected:
        yield DOC, 'Total'


@rule('CFDI40125', 'MetodoPago must be absent for types T and P')
def _40125(c: Comprobante) -> Iterator[Any]:
    if c.TipoDeComprobante in ('T', 'P') and c.MetodoPago is not None:
        yield DOC, 'MetodoPago'


@rule('CFDI40130', 'InformacionGlobal is required for an invoice to the general public')
def _40130(c: Comprobante) -> Iterator[Any]:
    receptor = c.Receptor
    if (
        c.TipoDeComprobante == 'I'
        and receptor.Rfc == GENERIC_NATIONAL
        and receptor.Nombre == PUBLICO
        and c.InformacionGlobal is None
    ):
        yield DOC, None


@rule('CFDI40132', 'Periodicidad 05 requires the issuer regime 621')
def _40132(c: Comprobante) -> Iterator[Any]:
    if (
        c.InformacionGlobal
        and c.InformacionGlobal.Periodicidad == '05'
        and c.Emisor.RegimenFiscal != '621'
    ):
        yield f'{DOC}/cfdi:InformacionGlobal', 'Periodicidad'


@rule('CFDI40134', 'Meses must be 01 to 12 unless Periodicidad is 05')
def _40134(c: Comprobante) -> Iterator[Any]:
    info = c.InformacionGlobal
    if info and info.Periodicidad != '05' and info.Meses not in {f'{m:02}' for m in range(1, 13)}:
        yield f'{DOC}/cfdi:InformacionGlobal', 'Meses'


@rule('CFDI40135', 'Meses must be 13 to 18 when Periodicidad is 05')
def _40135(c: Comprobante) -> Iterator[Any]:
    info = c.InformacionGlobal
    if info and info.Periodicidad == '05' and info.Meses not in {str(m) for m in range(13, 19)}:
        yield f'{DOC}/cfdi:InformacionGlobal', 'Meses'


# Emisor and Receptor ------------------------------------------------------------------------


@rule('CFDI40141', "The issuer regime does not fit the persona type of the issuer's Rfc")
def _40141(c: Comprobante) -> Iterator[Any]:
    persona = _persona(c.Emisor.Rfc)
    entry = _catalogs.regimen_persona().get(c.Emisor.RegimenFiscal)
    if persona and entry and not entry[persona]:
        yield f'{DOC}/cfdi:Emisor', 'RegimenFiscal'


RECEPTOR = f'{DOC}/cfdi:Receptor'


@rule('CFDI40146', 'A recipient named PUBLICO EN GENERAL must have Rfc XAXX010101000')
def _40146(c: Comprobante) -> Iterator[Any]:
    if c.Receptor.Nombre == PUBLICO and c.Receptor.Rfc != GENERIC_NATIONAL:
        yield RECEPTOR, 'Nombre'


@rule('CFDI40149', 'With a generic Rfc, DomicilioFiscalReceptor must equal LugarExpedicion')
def _40149(c: Comprobante) -> Iterator[Any]:
    if c.Receptor.Rfc in GENERIC and c.Receptor.DomicilioFiscalReceptor != c.LugarExpedicion:
        yield RECEPTOR, 'DomicilioFiscalReceptor'


@rule('CFDI40151', 'ResidenciaFiscal must be absent unless the Rfc is XEXX010101000')
def _40151(c: Comprobante) -> Iterator[Any]:
    if c.Receptor.ResidenciaFiscal is not None and c.Receptor.Rfc != GENERIC_FOREIGN:
        yield RECEPTOR, 'ResidenciaFiscal'


@rule('CFDI40152', 'ResidenciaFiscal cannot be MEX')
def _40152(c: Comprobante) -> Iterator[Any]:
    if c.Receptor.ResidenciaFiscal == 'MEX':
        yield RECEPTOR, 'ResidenciaFiscal'


@rule('CFDI40154', 'NumRegIdTrib must be absent unless the Rfc is XEXX010101000')
def _40154(c: Comprobante) -> Iterator[Any]:
    if c.Receptor.NumRegIdTrib is not None and c.Receptor.Rfc != GENERIC_FOREIGN:
        yield RECEPTOR, 'NumRegIdTrib'


@rule('CFDI40156', "NumRegIdTrib does not match the format of the recipient's country")
def _40156(c: Comprobante) -> Iterator[Any]:
    receptor = c.Receptor
    pattern = _catalogs.tax_id_formats().get(receptor.ResidenciaFiscal or '')
    if (
        receptor.NumRegIdTrib is not None
        and pattern
        and not re.fullmatch(pattern, receptor.NumRegIdTrib)
    ):
        yield RECEPTOR, 'NumRegIdTrib'


@rule('CFDI40158', "The recipient regime does not fit the persona type of the recipient's Rfc")
def _40158(c: Comprobante) -> Iterator[Any]:
    persona = _persona(c.Receptor.Rfc)
    entry = _catalogs.regimen_persona().get(c.Receptor.RegimenFiscalReceptor)
    if persona and entry and not entry[persona]:
        yield RECEPTOR, 'RegimenFiscalReceptor'


@rule('CFDI40159', 'With a generic Rfc, RegimenFiscalReceptor must be 616')
def _40159(c: Comprobante) -> Iterator[Any]:
    if c.Receptor.Rfc in GENERIC and c.Receptor.RegimenFiscalReceptor != '616':
        yield RECEPTOR, 'RegimenFiscalReceptor'


@rule('CFDI40161', 'UsoCFDI does not apply to the recipient persona type or regime')
def _40161(c: Comprobante) -> Iterator[Any]:
    entry = _catalogs.uso_cfdi().get(c.Receptor.UsoCFDI)
    if entry is None:
        return
    persona = _persona(c.Receptor.Rfc)
    if (persona and not entry[persona]) or c.Receptor.RegimenFiscalReceptor not in entry[
        'regimenes'
    ]:
        yield RECEPTOR, 'UsoCFDI'


# Conceptos ----------------------------------------------------------------------------------


@rule('CFDI40164', 'A tax the product key requires is missing')
def _40164(c: Comprobante) -> Iterator[Any]:
    for path, concepto in _conceptos(c):
        required = _catalogs.required_taxes().get(concepto.ClaveProdServ)
        if required is None:
            continue
        present = (
            {t.Impuesto for t in concepto.Impuestos.Traslados} if concepto.Impuestos else set()
        )
        if (required['iva'] and '002' not in present) or (
            required['ieps'] and '003' not in present
        ):
            yield path, 'ClaveProdServ'


@rule('CFDI40166', 'ValorUnitario must be greater than zero for types I, E and N')
def _40166(c: Comprobante) -> Iterator[Any]:
    if c.TipoDeComprobante not in ('I', 'E', 'N'):
        return
    for path, concepto in _conceptos(c):
        if _finite(concepto.ValorUnitario) and concepto.ValorUnitario <= 0:
            yield path, 'ValorUnitario'


@rule('CFDI40167', 'Importe is outside the limits Cantidad and ValorUnitario allow')
def _40167(c: Comprobante) -> Iterator[Any]:
    for path, x in _conceptos(c):
        if _finite(x.Cantidad, x.ValorUnitario, x.Importe) and not _amount_ok(
            x.Cantidad, x.ValorUnitario, x.Importe
        ):
            yield path, 'Importe'


@rule('CFDI40168', 'Descuento has more decimals than the concept Importe')
def _40168(c: Comprobante) -> Iterator[Any]:
    for path, x in _conceptos(c):
        if _finite(x.Descuento, x.Importe) and _places(x.Descuento) > _places(x.Importe):  # type: ignore[arg-type]
            yield path, 'Descuento'


@rule('CFDI40169', 'Descuento is greater than the concept Importe')
def _40169(c: Comprobante) -> Iterator[Any]:
    for path, x in _conceptos(c):
        if _finite(x.Descuento, x.Importe) and x.Descuento > x.Importe:  # type: ignore[operator]
            yield path, 'Descuento'


@rule('CFDI40171', 'ObjetoImp 02 requires the concept Impuestos node')
def _40171(c: Comprobante) -> Iterator[Any]:
    for path, x in _conceptos(c):
        if x.ObjetoImp == '02' and x.Impuestos is None:
            yield path, 'ObjetoImp'


@rule('CFDI40172', 'ObjetoImp 01, 03, 04 or 05 forbids the concept Impuestos node')
def _40172(c: Comprobante) -> Iterator[Any]:
    for path, x in _conceptos(c):
        if x.ObjetoImp in ('01', '03', '04', '05') and x.Impuestos is not None:
            yield path, 'ObjetoImp'


@rule('CFDI40173', 'A concept Impuestos node must hold transferred or withheld taxes')
def _40173(c: Comprobante) -> Iterator[Any]:
    for path, x in _conceptos(c):
        if x.Impuestos is not None and not x.Impuestos.Traslados and not x.Impuestos.Retenciones:
            yield f'{path}/cfdi:Impuestos', None


@rule('CFDI40177', 'An Exento transferred tax cannot have TasaOCuota or Importe')
def _40177(c: Comprobante) -> Iterator[Any]:
    for path, t in _concept_traslados(c):
        if t.TipoFactor == EXENTO and (t.TasaOCuota is not None or t.Importe is not None):
            yield path, 'TipoFactor'


@rule('CFDI40178', 'A Tasa or Cuota transferred tax needs TasaOCuota and Importe')
def _40178(c: Comprobante) -> Iterator[Any]:
    for path, t in _concept_traslados(c):
        if t.TipoFactor in ('Tasa', 'Cuota') and (t.TasaOCuota is None or t.Importe is None):
            yield path, 'TipoFactor'


@rule('CFDI40179', 'TasaOCuota is not in c_TasaOCuota for this tax and factor')
def _40179(c: Comprobante) -> Iterator[Any]:
    for path, t in _concept_traslados(c):
        if (
            t.TipoFactor != EXENTO
            and _finite(t.TasaOCuota)
            and not _catalogs.rate_allowed(t.Impuesto, t.TipoFactor, t.TasaOCuota, 'traslado')
        ):
            yield path, 'TasaOCuota'


@rule('CFDI40180', 'Importe is outside the limits Base and TasaOCuota allow')
def _40180(c: Comprobante) -> Iterator[Any]:
    for path, t in _concept_traslados(c):
        if (
            t.TipoFactor != EXENTO
            and _finite(t.Base, t.TasaOCuota, t.Importe)
            and not _tax_ok(t.Base, t.TasaOCuota, t.Importe)
        ):
            yield path, 'Importe'


@rule('CFDI40184', 'A withheld tax cannot be Exento')
def _40184(c: Comprobante) -> Iterator[Any]:
    for path, r in _concept_retenciones(c):
        if r.TipoFactor == EXENTO:
            yield path, 'TipoFactor'


@rule('CFDI40185', 'TasaOCuota is not in c_TasaOCuota for this withheld tax and factor')
def _40185(c: Comprobante) -> Iterator[Any]:
    for path, r in _concept_retenciones(c):
        if (
            r.TipoFactor != EXENTO
            and _finite(r.TasaOCuota)
            and not _catalogs.rate_allowed(r.Impuesto, r.TipoFactor, r.TasaOCuota, 'retencion')
        ):
            yield path, 'TasaOCuota'


@rule('CFDI40186', 'Importe is outside the limits Base and TasaOCuota allow')
def _40186(c: Comprobante) -> Iterator[Any]:
    for path, r in _concept_retenciones(c):
        if _finite(r.Base, r.TasaOCuota, r.Importe) and not _tax_ok(
            r.Base, r.TasaOCuota, r.Importe
        ):
            yield path, 'Importe'


def _terceros(c: Comprobante) -> Iterator[tuple[str, Any]]:
    for path, x in _conceptos(c):
        if x.ACuentaTerceros is not None:
            yield f'{path}/cfdi:ACuentaTerceros', x.ACuentaTerceros


@rule('CFDI40188', 'RfcACuentaTerceros must differ from the issuer and recipient Rfc')
def _40188(c: Comprobante) -> Iterator[Any]:
    for path, t in _terceros(c):
        if t.RfcACuentaTerceros in (c.Emisor.Rfc, c.Receptor.Rfc):
            yield path, 'RfcACuentaTerceros'


@rule('CFDI40189', 'NombreACuentaTerceros must be the fixed description for EXT990101NI1')
def _40189(c: Comprobante) -> Iterator[Any]:
    for path, t in _terceros(c):
        if t.RfcACuentaTerceros == EXT and t.NombreACuentaTerceros != EXT_NOMBRE:
            yield path, 'NombreACuentaTerceros'


@rule('CFDI40193', 'DomicilioFiscalACuentaTerceros must equal LugarExpedicion for EXT990101NI1')
def _40193(c: Comprobante) -> Iterator[Any]:
    for path, t in _terceros(c):
        if t.RfcACuentaTerceros == EXT and t.DomicilioFiscalACuentaTerceros != c.LugarExpedicion:
            yield path, 'DomicilioFiscalACuentaTerceros'


@rule('CFDI140223', 'RegimenFiscalACuentaTerceros must be 616 for EXT990101NI1')
def _140223(c: Comprobante) -> Iterator[Any]:
    for path, t in _terceros(c):
        if t.RfcACuentaTerceros == EXT and t.RegimenFiscalACuentaTerceros != '616':
            yield path, 'RegimenFiscalACuentaTerceros'


@rule('CFDI40194', 'NumeroPedimento does not follow the customs catalogs')
def _40194(c: Comprobante) -> Iterator[Any]:
    for path, x in _conceptos(c):
        for node, info in _numbered(f'{path}/cfdi:InformacionAduanera', x.InformacionAduanera):
            if not _pedimento_ok(info.NumeroPedimento):
                yield node, 'NumeroPedimento'


def _partes(c: Comprobante) -> Iterator[tuple[str, Any]]:
    for path, x in _conceptos(c):
        yield from _numbered(f'{path}/cfdi:Parte', x.Parte)


@rule('CFDI40197', 'Parte ValorUnitario must be greater than zero')
def _40197(c: Comprobante) -> Iterator[Any]:
    for path, parte in _partes(c):
        if _finite(parte.ValorUnitario) and parte.ValorUnitario <= 0:
            yield path, 'ValorUnitario'


@rule('CFDI40198', 'Parte Importe is outside the limits Cantidad and ValorUnitario allow')
def _40198(c: Comprobante) -> Iterator[Any]:
    for path, p in _partes(c):
        if _finite(p.Cantidad, p.ValorUnitario, p.Importe) and not _amount_ok(
            p.Cantidad, p.ValorUnitario, p.Importe
        ):
            yield path, 'Importe'


@rule('CFDI40199', 'Parte NumeroPedimento does not follow the customs catalogs')
def _40199(c: Comprobante) -> Iterator[Any]:
    for path, parte in _partes(c):
        for node, info in _numbered(f'{path}/cfdi:InformacionAduanera', parte.InformacionAduanera):
            if not _pedimento_ok(info.NumeroPedimento):
                yield node, 'NumeroPedimento'


@rule('CFDI140226', 'ObjetoImp 06 or 08 forbids IVA and IEPS on the concept')
def _140226(c: Comprobante) -> Iterator[Any]:
    for path, x in _conceptos(c):
        if x.ObjetoImp in ('06', '08') and any(t.Impuesto in ('002', '003') for t in _taxes(x)):
            yield path, 'ObjetoImp'


@rule('CFDI140227', 'ObjetoImp 07 forbids IVA and requires a transferred IEPS')
def _140227(c: Comprobante) -> Iterator[Any]:
    for path, x in _conceptos(c):
        if x.ObjetoImp != '07':
            continue
        traslados = x.Impuestos.Traslados if x.Impuestos else []
        if any(t.Impuesto == '002' for t in _taxes(x)) or not any(
            t.Impuesto == '003' for t in traslados
        ):
            yield path, 'ObjetoImp'


@rule('CFDI140228', 'These hydrocarbon keys need the Hidrocarburos y Petrolíferos complement')
def _140228(c: Comprobante) -> Iterator[Any]:
    if c.TipoDeComprobante not in ('I', 'E'):
        return
    for path, x in _conceptos(c):
        if x.ClaveProdServ not in HIDROCARBUROS_KEYS:
            continue
        roots = {
            (item.__xml__.namespace, item.__xml__.name)
            for item in x.ComplementoConcepto
            if not isinstance(item, RawXml)
        }
        if HIDROCARBUROS not in roots:
            yield path, 'ClaveProdServ'


# Comercio Exterior (User Story 2) ----------------------------------------------------------

COMERCIO_EXTERIOR = ('http://www.sat.gob.mx/ComercioExterior20', 'ComercioExterior')


def _has_cce(c: Comprobante) -> bool:
    return any(
        not isinstance(item, RawXml)
        and (item.__xml__.namespace, item.__xml__.name) == COMERCIO_EXTERIOR
        for item in c.Complemento
    )


@rule('CFDI40122', 'Exportacion 02 requires the Comercio Exterior complement')
def _40122(c: Comprobante) -> Iterator[Any]:
    if c.Exportacion == '02' and not _has_cce(c):
        yield DOC, 'Exportacion'


@rule(
    'CFDI40153',
    'ResidenciaFiscal is required for XEXX010101000 with Comercio Exterior or NumRegIdTrib',
)
def _40153(c: Comprobante) -> Iterator[Any]:
    receptor = c.Receptor
    if (
        receptor.Rfc == GENERIC_FOREIGN
        and (_has_cce(c) or receptor.NumRegIdTrib is not None)
        and receptor.ResidenciaFiscal is None
    ):
        yield RECEPTOR, 'ResidenciaFiscal'


@rule('CFDI40155', 'NumRegIdTrib is required for XEXX010101000 with Comercio Exterior')
def _40155(c: Comprobante) -> Iterator[Any]:
    if c.Receptor.Rfc == GENERIC_FOREIGN and _has_cce(c) and c.Receptor.NumRegIdTrib is None:
        yield RECEPTOR, 'NumRegIdTrib'


@rule('CFDI40195', 'NumeroPedimento must be absent with Comercio Exterior')
def _40195(c: Comprobante) -> Iterator[Any]:
    if not _has_cce(c):
        return
    for path, x in _conceptos(c):
        for node, _ in _numbered(f'{path}/cfdi:InformacionAduanera', x.InformacionAduanera):
            yield node, 'NumeroPedimento'


@rule('CFDI40200', 'Parte NumeroPedimento must be absent with Comercio Exterior')
def _40200(c: Comprobante) -> Iterator[Any]:
    if not _has_cce(c):
        return
    for path, parte in _partes(c):
        for node, _ in _numbered(f'{path}/cfdi:InformacionAduanera', parte.InformacionAduanera):
            yield node, 'NumeroPedimento'


@rule('CFDI40222', 'Exportacion 01 or 03 forbids the Comercio Exterior complement')
def _40222(c: Comprobante) -> Iterator[Any]:
    if c.Exportacion in ('01', '03') and _has_cce(c):
        yield DOC, 'Exportacion'


# Impuestos ----------------------------------------------------------------------------------

IMPUESTOS = f'{DOC}/cfdi:Impuestos'


def _doc_retenciones(c: Comprobante) -> Iterator[tuple[str, Any]]:
    if c.Impuestos is not None:
        yield from _numbered(
            f'{IMPUESTOS}/cfdi:Retenciones/cfdi:Retencion', c.Impuestos.Retenciones
        )


def _doc_traslados(c: Comprobante) -> Iterator[tuple[str, Any]]:
    if c.Impuestos is not None:
        yield from _numbered(f'{IMPUESTOS}/cfdi:Traslados/cfdi:Traslado', c.Impuestos.Traslados)


def _all_concept_traslados(c: Comprobante) -> list[Any]:
    return [t for _, t in _concept_traslados(c)]


@rule('CFDI40201', 'The document Impuestos node must be absent for types T and P')
def _40201(c: Comprobante) -> Iterator[Any]:
    if c.TipoDeComprobante in ('T', 'P') and c.Impuestos is not None:
        yield IMPUESTOS, None


@rule('CFDI40202', "TotalImpuestosRetenidos has more decimals than the currency's")
def _40202(c: Comprobante) -> Iterator[Any]:
    if c.Impuestos and _too_many_decimals(c.Impuestos.TotalImpuestosRetenidos, _currency(c)):
        yield IMPUESTOS, 'TotalImpuestosRetenidos'


@rule('CFDI40203', 'TotalImpuestosRetenidos is not the sum of the Retencion amounts')
def _40203(c: Comprobante) -> Iterator[Any]:
    impuestos = c.Impuestos
    if impuestos is None or not _finite(impuestos.TotalImpuestosRetenidos):
        return
    expected = sum_amounts(r.Importe for r in impuestos.Retenciones)
    if expected is not None and impuestos.TotalImpuestosRetenidos != expected:
        yield IMPUESTOS, 'TotalImpuestosRetenidos'


@rule('CFDI40204', "TotalImpuestosTrasladados has more decimals than the currency's")
def _40204(c: Comprobante) -> Iterator[Any]:
    if c.Impuestos and _too_many_decimals(c.Impuestos.TotalImpuestosTrasladados, _currency(c)):
        yield IMPUESTOS, 'TotalImpuestosTrasladados'


@rule('CFDI40205', 'TotalImpuestosTrasladados is not the sum of the Traslado amounts')
def _40205(c: Comprobante) -> Iterator[Any]:
    impuestos = c.Impuestos
    if impuestos is None or not _finite(impuestos.TotalImpuestosTrasladados):
        return
    expected = sum_amounts(t.Importe for t in impuestos.Traslados if t.Importe is not None)
    if expected is not None and impuestos.TotalImpuestosTrasladados != expected:
        yield IMPUESTOS, 'TotalImpuestosTrasladados'


@rule('CFDI40206', 'Retenciones requires TotalImpuestosRetenidos')
def _40206(c: Comprobante) -> Iterator[Any]:
    if c.Impuestos and c.Impuestos.Retenciones and c.Impuestos.TotalImpuestosRetenidos is None:
        yield f'{IMPUESTOS}/cfdi:Retenciones', None


@rule('CFDI40208', 'There must be one Retencion per tax')
def _40208(c: Comprobante) -> Iterator[Any]:
    seen: set[str] = set()
    for path, r in _doc_retenciones(c):
        if r.Impuesto in seen:
            yield path, 'Impuesto'
        seen.add(r.Impuesto)


@rule('CFDI40209', 'A Retencion amount requires TotalImpuestosRetenidos')
def _40209(c: Comprobante) -> Iterator[Any]:
    if c.Impuestos and c.Impuestos.TotalImpuestosRetenidos is None:
        for path, _ in _doc_retenciones(c):
            yield path, 'Importe'


@rule('CFDI40210', "Retencion Importe has more decimals than the currency's")
def _40210(c: Comprobante) -> Iterator[Any]:
    places = _currency(c)
    for path, r in _doc_retenciones(c):
        if _too_many_decimals(r.Importe, places):
            yield path, 'Importe'


@rule('CFDI40211', 'Retencion Importe is not the rounded sum of the concept withholdings')
def _40211(c: Comprobante) -> Iterator[Any]:
    places = _currency(c)
    if places is None:
        return
    for path, r in _doc_retenciones(c):
        concept = [x.Importe for _, x in _concept_retenciones(c) if x.Impuesto == r.Impuesto]
        expected = round_amount(sum_amounts(concept), places)
        if expected is not None and _finite(r.Importe) and r.Importe != expected:
            yield path, 'Importe'


@rule('CFDI40212', 'TotalImpuestosTrasladados is required when a tax is not Exento')
def _40212(c: Comprobante) -> Iterator[Any]:
    impuestos = c.Impuestos
    if impuestos is None or impuestos.TotalImpuestosTrasladados is not None:
        return
    if any(t.TipoFactor != EXENTO for t in _all_concept_traslados(c)):
        yield f'{IMPUESTOS}/cfdi:Traslados', None


def _only_exento(c: Comprobante) -> bool:
    traslados = _all_concept_traslados(c)
    return bool(traslados) and all(t.TipoFactor == EXENTO for t in traslados)


@rule('CFDI40213', 'With only Exento concepts, Traslado holds only Base, Impuesto and TipoFactor')
def _40213(c: Comprobante) -> Iterator[Any]:
    if not _only_exento(c):
        return
    for path, t in _doc_traslados(c):
        if t.TasaOCuota is not None or t.Importe is not None:
            yield path, None


@rule('CFDI40214', "Traslado Base has more decimals than the currency's")
def _40214(c: Comprobante) -> Iterator[Any]:
    places = _currency(c)
    for path, t in _doc_traslados(c):
        if _too_many_decimals(t.Base, places):
            yield path, 'Base'


def _matching(c: Comprobante, t: Any) -> list[Any]:
    return [
        x
        for x in _all_concept_traslados(c)
        if (x.Impuesto, x.TipoFactor, x.TasaOCuota) == (t.Impuesto, t.TipoFactor, t.TasaOCuota)
    ]


@rule('CFDI40215', 'Traslado Base is not the rounded sum of the matching concept bases')
def _40215(c: Comprobante) -> Iterator[Any]:
    places = _currency(c)
    if places is None:
        return
    for path, t in _doc_traslados(c):
        if t.TipoFactor == EXENTO:
            continue
        expected = round_amount(sum_amounts(x.Base for x in _matching(c, t)), places)
        if expected is not None and _finite(t.Base) and t.Base != expected:
            yield path, 'Base'


@rule('CFDI40216', 'With only Exento concepts, Base is not the rounded sum of the concept bases')
def _40216(c: Comprobante) -> Iterator[Any]:
    places = _currency(c)
    if places is None or not _only_exento(c) or c.Impuestos is None or not c.Impuestos.Traslados:
        return
    expected = round_amount(sum_amounts(t.Base for t in _all_concept_traslados(c)), places)
    total = sum_amounts(t.Base for t in c.Impuestos.Traslados)
    if expected is not None and total is not None and total != expected:
        yield next(_doc_traslados(c))[0], 'Base'


@rule('CFDI40218', 'There must be one Traslado per tax, factor and rate')
def _40218(c: Comprobante) -> Iterator[Any]:
    seen: set[tuple[str, str, Decimal | None]] = set()
    for path, t in _doc_traslados(c):
        key = (t.Impuesto, t.TipoFactor, t.TasaOCuota)
        if key in seen:
            yield path, 'Impuesto'
        seen.add(key)


@rule('CFDI40219', 'TasaOCuota is not in c_TasaOCuota for this tax and factor')
def _40219(c: Comprobante) -> Iterator[Any]:
    for path, t in _doc_traslados(c):
        if (
            t.TipoFactor != EXENTO
            and _finite(t.TasaOCuota)
            and not _catalogs.rate_allowed(t.Impuesto, t.TipoFactor, t.TasaOCuota, 'traslado')
        ):
            yield path, 'TasaOCuota'


@rule('CFDI40220', "Traslado Importe has more decimals than the currency's")
def _40220(c: Comprobante) -> Iterator[Any]:
    places = _currency(c)
    for path, t in _doc_traslados(c):
        if _too_many_decimals(t.Importe, places):
            yield path, 'Importe'


@rule('CFDI40221', 'Traslado Importe is not the rounded sum of the matching concept amounts')
def _40221(c: Comprobante) -> Iterator[Any]:
    places = _currency(c)
    if places is None:
        return
    for path, t in _doc_traslados(c):
        if t.TipoFactor == EXENTO:
            continue
        expected = round_amount(sum_amounts(x.Importe for x in _matching(c, t)), places)
        if expected is not None and _finite(t.Importe) and t.Importe != expected:
            yield path, 'Importe'


# Library rules ------------------------------------------------------------------------------


def _complement_path(parent: str, items: list[Any], index: int) -> str:
    info = items[index].__xml__
    same = [
        i
        for i, item in enumerate(items)
        if not isinstance(item, RawXml) and item.__xml__.name == info.name
    ]
    return _indexed(f'{parent}/{info.prefix}:{info.name}', same.index(index), len(same))


def _complement_document_type(c: Comprobante) -> Iterator[Violation]:
    """Complements, at document or concept level, on a document type their standard forbids."""
    places: list[tuple[str, list[Any]]] = [(f'{DOC}/cfdi:Complemento', c.Complemento)]
    for path, concepto in _conceptos(c):
        places.append((f'{path}/cfdi:ComplementoConcepto', concepto.ComplementoConcepto))
    message = f'this complement is not allowed on a type {c.TipoDeComprobante} document'
    for parent, items in places:
        for index, item in enumerate(items):
            if isinstance(item, RawXml):
                continue
            allowed = ALLOWED_DOCUMENT_TYPES.get((item.__xml__.namespace, item.__xml__.name))
            if allowed is not None and c.TipoDeComprobante not in allowed:
                node = _complement_path(parent, items, index)
                yield Violation(node, None, COMPLEMENT_DOCUMENT_TYPE, message)


def _complement_level(c: Comprobante) -> Iterator[Violation]:
    message = 'this complement is not allowed at this level'
    parent = f'{DOC}/cfdi:Complemento'
    for index, item in enumerate(c.Complemento):
        if isinstance(item, ConceptComplement) and not isinstance(item, DocumentComplement):
            yield Violation(
                _complement_path(parent, c.Complemento, index), None, COMPLEMENT_LEVEL, message
            )
    for path, concepto in _conceptos(c):
        items = concepto.ComplementoConcepto
        for index, complement in enumerate(items):
            if isinstance(complement, DocumentComplement) and not isinstance(
                complement, ConceptComplement
            ):
                node = _complement_path(f'{path}/cfdi:ComplementoConcepto', items, index)
                yield Violation(node, None, COMPLEMENT_LEVEL, message)
