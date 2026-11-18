"""The values the standard derives from a document (data-model.md section 3).

Sums are over unrounded values and rounded once, half up, to the decimals of the document's
currency in the SAT's ``c_Moneda`` catalog. A derived field the caller set is kept. Any value
that makes the arithmetic impossible (an unknown currency, a non-finite or unroundable amount)
leaves the fields it feeds unset, for validation to report.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import replace
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from mictlanix.cfdi import implocal10, pagos20
from mictlanix.cfdi._catalogs import currency_decimals
from mictlanix.cfdi.cfdi40 import (
    CfdiRelacionados,
    Comprobante,
    Concepto,
    Emisor,
    Impuestos,
    Receptor,
    Retencion,
    Traslado,
)

EXENTO = 'Exento'
SCHEMA_PLACES = 6


def round_amount(value: Decimal | None, places: int) -> Decimal | None:
    """Half-up rounding to ``places`` decimals; None if the value cannot be rounded."""
    return _round(value, places)


def _round(value: Decimal | None, places: int) -> Decimal | None:
    if value is None or not value.is_finite():
        return None
    try:
        return value.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)
    except InvalidOperation:
        return None


def sum_amounts(values: Iterable[Decimal | None]) -> Decimal | None:
    """The sum, or None if any value is missing or not finite."""
    return _sum(values)


def _sum(values: Iterable[Decimal | None]) -> Decimal | None:
    total = Decimal(0)
    for value in values:
        if value is None or not value.is_finite():
            return None
        total += value
    return total


def _impuestos(conceptos: list[Concepto], places: int) -> Impuestos | None:
    """The document's tax summary, or None if there are no taxes or it cannot be derived."""
    traslados: dict[tuple[str, str, Decimal | None], list[Decimal | None]] = {}
    traslado_bases: dict[tuple[str, str, Decimal | None], list[Decimal | None]] = {}
    retenciones: dict[str, list[Decimal | None]] = {}
    for concepto in conceptos:
        if concepto.Impuestos is None:
            continue
        for traslado in concepto.Impuestos.Traslados:
            key = (traslado.Impuesto, traslado.TipoFactor, traslado.TasaOCuota)
            traslado_bases.setdefault(key, []).append(traslado.Base)
            traslados.setdefault(key, []).append(traslado.Importe)
        for retencion in concepto.Impuestos.Retenciones:
            retenciones.setdefault(retencion.Impuesto, []).append(retencion.Importe)
    if not traslados and not retenciones:
        return None

    summary_traslados = []
    for (impuesto, factor, tasa), importes in traslados.items():
        base = _round(_sum(traslado_bases[(impuesto, factor, tasa)]), places)
        importe = None if factor == EXENTO else _round(_sum(importes), places)
        if base is None or (factor != EXENTO and importe is None):
            return None
        summary_traslados.append(
            Traslado(
                Base=base,
                Impuesto=impuesto,
                TipoFactor=factor,
                TasaOCuota=None if factor == EXENTO else tasa,
                Importe=importe,
            )
        )
    summary_retenciones = []
    for impuesto, importes in retenciones.items():
        importe = _round(_sum(importes), places)
        if importe is None:
            return None
        summary_retenciones.append(Retencion(Impuesto=impuesto, Importe=importe))

    transferred = [t.Importe for t in summary_traslados if t.TipoFactor != EXENTO]
    return Impuestos(
        TotalImpuestosRetenidos=_sum(r.Importe for r in summary_retenciones)
        if summary_retenciones
        else None,
        TotalImpuestosTrasladados=_sum(transferred) if transferred else None,
        Retenciones=summary_retenciones,
        Traslados=summary_traslados,
    )


def local_taxes(comprobante: Comprobante) -> Decimal | None:
    """Net local taxes (transferred minus withheld) of the Impuestos Locales complements.

    None when an amount is not finite.
    """
    parts: list[Decimal | None] = []
    for item in comprobante.Complemento:
        if isinstance(item, implocal10.ImpuestosLocales):
            parts.append(item.TotaldeTraslados)
            parts.append(-item.TotaldeRetenciones if item.TotaldeRetenciones.is_finite() else None)
    return _sum(parts)


def _total(
    subtotal: Decimal | None,
    descuento: Decimal | None,
    impuestos: Impuestos | None,
    taxed: bool,
    places: int,
    local: Decimal | None = Decimal(0),
) -> Decimal | None:
    """SubTotal - Descuento + transferred taxes - withheld taxes + net local taxes."""
    if subtotal is None or local is None or (taxed and impuestos is None):
        return None
    parts = [subtotal, local]
    if descuento is not None:
        parts.append(-descuento)
    if impuestos is not None:
        if impuestos.TotalImpuestosTrasladados is not None:
            parts.append(impuestos.TotalImpuestosTrasladados)
        if impuestos.TotalImpuestosRetenidos is not None:
            parts.append(-impuestos.TotalImpuestosRetenidos)
    return _round(_sum(parts), places)


class _Unusable(Exception):
    """An input makes the Pagos 2.0 arithmetic impossible; nothing is derived."""


def _exact(value: Decimal) -> Decimal:
    """A converted amount, rounded half up only beyond the schema's 6 decimals."""
    exponent = value.as_tuple().exponent
    if isinstance(exponent, int) and exponent < -SCHEMA_PLACES:
        rounded = _round(value, SCHEMA_PLACES)
        if rounded is None:
            raise _Unusable
        return rounded
    return value


def _divide(amount: Decimal | None, equivalencia: Decimal) -> Decimal:
    if amount is None or not amount.is_finite():
        raise _Unusable
    try:
        return amount / equivalencia
    except ArithmeticError:
        raise _Unusable from None


def _exact_sum(values: list[Decimal]) -> Decimal:
    total = _sum(values)
    if total is None:
        raise _Unusable
    return _exact(total)


def _impuestos_p(pago: pagos20.Pago) -> pagos20.ImpuestosP | None:
    """A payment's tax summary, converted to the payment currency (data-model.md 3.2)."""
    traslados: dict[tuple[str, str, Decimal | None], tuple[list[Decimal], list[Decimal]]] = {}
    retenciones: dict[str, list[Decimal]] = {}
    for docto in pago.DoctoRelacionado:
        if docto.ImpuestosDR is None:
            continue
        equivalencia = docto.EquivalenciaDR
        assert equivalencia is not None
        for traslado in docto.ImpuestosDR.TrasladosDR:
            key = (traslado.ImpuestoDR, traslado.TipoFactorDR, traslado.TasaOCuotaDR)
            bases, importes = traslados.setdefault(key, ([], []))
            bases.append(_divide(traslado.BaseDR, equivalencia))
            if traslado.TipoFactorDR != EXENTO:
                importes.append(_divide(traslado.ImporteDR, equivalencia))
        for retencion in docto.ImpuestosDR.RetencionesDR:
            importe = _divide(retencion.ImporteDR, equivalencia)
            retenciones.setdefault(retencion.ImpuestoDR, []).append(importe)
    if not traslados and not retenciones:
        return None
    return pagos20.ImpuestosP(
        RetencionesP=[
            pagos20.RetencionP(ImpuestoP=impuesto, ImporteP=_exact_sum(importes))
            for impuesto, importes in retenciones.items()
        ],
        TrasladosP=[
            pagos20.TrasladoP(
                BaseP=_exact_sum(bases),
                ImpuestoP=impuesto,
                TipoFactorP=factor,
                TasaOCuotaP=None if factor == EXENTO else tasa,
                ImporteP=None if factor == EXENTO else _exact_sum(importes),
            )
            for (impuesto, factor, tasa), (bases, importes) in traslados.items()
        ],
    )


def _usable(pagos: pagos20.Pagos) -> bool:
    for pago in pagos.Pago:
        if (
            pago.MonedaP not in currency_decimals()
            or pago.TipoCambioP is None
            or not pago.TipoCambioP.is_finite()
            or not pago.Monto.is_finite()
        ):
            return False
        for docto in pago.DoctoRelacionado:
            equivalencia = docto.EquivalenciaDR
            if equivalencia is None or not equivalencia.is_finite() or equivalencia == 0:
                return False
    return True


_IVA_RATES = {
    Decimal('0.16'): ('TotalTrasladosBaseIVA16', 'TotalTrasladosImpuestoIVA16'),
    Decimal('0.08'): ('TotalTrasladosBaseIVA8', 'TotalTrasladosImpuestoIVA8'),
    Decimal('0'): ('TotalTrasladosBaseIVA0', 'TotalTrasladosImpuestoIVA0'),
}
_RETENCIONES = {
    '002': 'TotalRetencionesIVA',
    '001': 'TotalRetencionesISR',
    '003': 'TotalRetencionesIEPS',
}


def _totales(pagos: list[pagos20.Pago]) -> pagos20.Totales:
    """The complement's totals in MXN, each rounded once to 2 decimals (data-model.md 3.2)."""
    parts: dict[str, list[Decimal]] = {}
    for pago in pagos:
        rate = pago.TipoCambioP
        assert rate is not None
        parts.setdefault('MontoTotalPagos', []).append(pago.Monto * rate)
        if pago.ImpuestosP is None:
            continue
        for retencion in pago.ImpuestosP.RetencionesP:
            name = _RETENCIONES.get(retencion.ImpuestoP)
            if name is not None:
                parts.setdefault(name, []).append(retencion.ImporteP * rate)
        for traslado in pago.ImpuestosP.TrasladosP:
            if traslado.ImpuestoP != '002':
                continue
            if traslado.TipoFactorP == EXENTO:
                parts.setdefault('TotalTrasladosBaseIVAExento', []).append(traslado.BaseP * rate)
                continue
            names = (
                _IVA_RATES.get(traslado.TasaOCuotaP) if traslado.TasaOCuotaP is not None else None
            )
            if names is None or traslado.ImporteP is None:
                continue
            parts.setdefault(names[0], []).append(traslado.BaseP * rate)
            parts.setdefault(names[1], []).append(traslado.ImporteP * rate)
    totals: dict[str, Decimal] = {}
    for name, values in parts.items():
        total = _round(_sum(values), 2)
        if total is None:
            raise _Unusable
        totals[name] = total
    return pagos20.Totales(**totals)


def _compute_pagos(pagos: pagos20.Pagos) -> pagos20.Pagos:
    """Pagos 2.0 with ``ImpuestosP`` and ``Totales`` filled in; unchanged if unusable."""
    if not _usable(pagos):
        return pagos
    try:
        derived = [
            pago if pago.ImpuestosP is not None else replace(pago, ImpuestosP=_impuestos_p(pago))
            for pago in pagos.Pago
        ]
        totales = pagos.Totales if pagos.Totales is not None else _totales(derived)
    except _Unusable:
        return pagos
    return replace(pagos, Pago=derived, Totales=totales)


def compute(comprobante: Comprobante) -> Comprobante:
    """A copy of the document with the derived values filled in.

    A derived field that is ``None`` is computed; one the caller set is kept. Never raises for
    a well-typed document.
    """
    if any(isinstance(item, pagos20.Pagos) for item in comprobante.Complemento):
        complemento = [
            _compute_pagos(item) if isinstance(item, pagos20.Pagos) else item
            for item in comprobante.Complemento
        ]
        comprobante = replace(comprobante, Complemento=complemento)
    places = currency_decimals().get(comprobante.Moneda)
    if places is None:
        return comprobante
    conceptos = comprobante.Conceptos
    subtotal = comprobante.SubTotal
    if subtotal is None:
        subtotal = _round(_sum(c.Importe for c in conceptos), places)
    descuento = comprobante.Descuento
    if descuento is None and any(c.Descuento is not None for c in conceptos):
        descuento = _round(_sum(c.Descuento for c in conceptos if c.Descuento is not None), places)
    impuestos = comprobante.Impuestos
    if impuestos is None:
        impuestos = _impuestos(conceptos, places)
    total = comprobante.Total
    if total is None:
        taxed = any(c.Impuestos is not None for c in conceptos)
        total = _total(subtotal, descuento, impuestos, taxed, places, local_taxes(comprobante))
    return replace(
        comprobante, SubTotal=subtotal, Descuento=descuento, Impuestos=impuestos, Total=total
    )


# The single concept the standard imposes on a payment document (type P).
PAYMENT_CONCEPT = Concepto(
    ClaveProdServ='84111506',
    Cantidad=Decimal('1'),
    ClaveUnidad='ACT',
    Descripcion='Pago',
    ValorUnitario=Decimal('0'),
    Importe=Decimal('0'),
    ObjetoImp='01',
)


def payment_comprobante(
    *,
    Emisor: Emisor,
    Receptor: Receptor,
    Fecha: datetime,
    LugarExpedicion: str,
    Pagos: pagos20.Pagos,
    Serie: str | None = None,
    Folio: str | None = None,
    CfdiRelacionados: list[CfdiRelacionados] | None = None,
) -> Comprobante:
    """A payment document (type P) with the fixed values the standard imposes.

    Currency ``XXX``, zero amounts, ``Exportacion`` 01, the single fixed concept, and ``Pagos``
    as its complement. Every other document type is built by constructing ``Comprobante``.
    """
    return Comprobante(
        Serie=Serie,
        Folio=Folio,
        Fecha=Fecha,
        SubTotal=Decimal('0'),
        Moneda='XXX',
        Total=Decimal('0'),
        TipoDeComprobante='P',
        Exportacion='01',
        LugarExpedicion=LugarExpedicion,
        CfdiRelacionados=CfdiRelacionados or [],
        Emisor=Emisor,
        Receptor=Receptor,
        Conceptos=[PAYMENT_CONCEPT],
        Complemento=[Pagos],
    )
