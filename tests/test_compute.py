"""Derived values of the document (data-model.md section 3.1)."""

from collections.abc import Callable
from decimal import Decimal
from typing import Any

from mictlanix.cfdi import (
    Comprobante,
    Concepto,
    ConceptoImpuestos,
    ConceptoRetencion,
    ConceptoTraslado,
    Impuestos,
    Retencion,
    Traslado,
    compute,
)

MakeInvoice = Callable[..., Comprobante]
D = Decimal


def _concepto(
    importe: str,
    *,
    descuento: str | None = None,
    traslados: list[ConceptoTraslado] | None = None,
    retenciones: list[ConceptoRetencion] | None = None,
) -> Concepto:
    taxed = bool(traslados or retenciones)
    return Concepto(
        ClaveProdServ='01010101',
        Cantidad=D('1'),
        ClaveUnidad='ACT',
        Descripcion='Venta',
        ValorUnitario=D(importe),
        Importe=D(importe),
        Descuento=None if descuento is None else D(descuento),
        ObjetoImp='02' if taxed else '01',
        Impuestos=ConceptoImpuestos(Traslados=traslados or [], Retenciones=retenciones or [])
        if taxed
        else None,
    )


def _iva(base: str, importe: str, tasa: str = '0.160000') -> ConceptoTraslado:
    return ConceptoTraslado(
        Base=D(base), Impuesto='002', TipoFactor='Tasa', TasaOCuota=D(tasa), Importe=D(importe)
    )


def _exento(base: str) -> ConceptoTraslado:
    return ConceptoTraslado(Base=D(base), Impuesto='002', TipoFactor='Exento')


def _retencion(impuesto: str, base: str, tasa: str, importe: str) -> ConceptoRetencion:
    return ConceptoRetencion(
        Base=D(base), Impuesto=impuesto, TipoFactor='Tasa', TasaOCuota=D(tasa), Importe=D(importe)
    )


def test_the_quickstart_invoice_gets_its_totals(make_invoice: MakeInvoice) -> None:
    computed = compute(make_invoice(totals=False))
    assert computed == make_invoice()


def test_subtotal_is_the_sum_of_the_concept_amounts_rounded_once(
    make_invoice: MakeInvoice,
) -> None:
    computed = compute(
        make_invoice(totals=False, Conceptos=[_concepto('0.005'), _concepto('0.005')])
    )
    assert computed.SubTotal == D('0.01')
    assert computed.Total == D('0.01')


def test_rounding_is_half_up(make_invoice: MakeInvoice) -> None:
    computed = compute(make_invoice(totals=False, Conceptos=[_concepto('10.125')]))
    assert computed.SubTotal == D('10.13')


def test_descuento_is_derived_only_when_a_concept_has_one(make_invoice: MakeInvoice) -> None:
    plain = compute(make_invoice(totals=False, Conceptos=[_concepto('100.00')]))
    assert plain.Descuento is None
    discounted = compute(
        make_invoice(
            totals=False,
            Conceptos=[_concepto('100.00', descuento='10.00'), _concepto('50.00')],
        )
    )
    assert discounted.Descuento == D('10.00')
    assert discounted.Total == D('140.00')


def test_transferred_taxes_are_grouped_by_tax_factor_and_rate(make_invoice: MakeInvoice) -> None:
    computed = compute(
        make_invoice(
            totals=False,
            Conceptos=[
                _concepto('100.00', traslados=[_iva('100.00', '16.00')]),
                _concepto('50.555', traslados=[_iva('50.555', '8.0888')]),
                _concepto('20.00', traslados=[_iva('20.00', '1.60', tasa='0.080000')]),
            ],
        )
    )
    assert computed.Impuestos == Impuestos(
        TotalImpuestosTrasladados=D('25.69'),
        Traslados=[
            Traslado(
                Base=D('150.56'),
                Impuesto='002',
                TipoFactor='Tasa',
                TasaOCuota=D('0.160000'),
                Importe=D('24.09'),
            ),
            Traslado(
                Base=D('20.00'),
                Impuesto='002',
                TipoFactor='Tasa',
                TasaOCuota=D('0.080000'),
                Importe=D('1.60'),
            ),
        ],
    )
    assert computed.SubTotal == D('170.56')
    assert computed.Total == D('196.25')


def test_exempt_groups_carry_only_the_base(make_invoice: MakeInvoice) -> None:
    computed = compute(
        make_invoice(totals=False, Conceptos=[_concepto('100.00', traslados=[_exento('100.00')])])
    )
    assert computed.Impuestos == Impuestos(
        Traslados=[Traslado(Base=D('100.00'), Impuesto='002', TipoFactor='Exento')]
    )
    assert computed.Total == D('100.00')


def test_withheld_taxes_are_grouped_by_tax(make_invoice: MakeInvoice) -> None:
    computed = compute(
        make_invoice(
            totals=False,
            Conceptos=[
                _concepto(
                    '1000.00',
                    traslados=[_iva('1000.00', '160.00')],
                    retenciones=[
                        _retencion('001', '1000.00', '0.100000', '100.00'),
                        _retencion('002', '1000.00', '0.106667', '106.67'),
                    ],
                ),
                _concepto('500.00', retenciones=[_retencion('001', '500.00', '0.100000', '50.00')]),
            ],
        )
    )
    assert computed.Impuestos is not None
    assert computed.Impuestos.Retenciones == [
        Retencion(Impuesto='001', Importe=D('150.00')),
        Retencion(Impuesto='002', Importe=D('106.67')),
    ]
    assert computed.Impuestos.TotalImpuestosRetenidos == D('256.67')
    assert computed.Total == D('1500.00') + D('160.00') - D('256.67')


def test_no_impuestos_node_when_no_concept_carries_taxes(make_invoice: MakeInvoice) -> None:
    computed = compute(make_invoice(totals=False, Conceptos=[_concepto('100.00')]))
    assert computed.Impuestos is None
    assert computed.Total == D('100.00')


def test_a_currency_without_decimals_rounds_to_units(make_invoice: MakeInvoice) -> None:
    computed = compute(make_invoice(totals=False, Moneda='JPY', Conceptos=[_concepto('1500.5')]))
    assert computed.SubTotal == D('1501')
    assert computed.Total == D('1501')


def test_values_the_caller_set_are_kept(make_invoice: MakeInvoice) -> None:
    computed = compute(make_invoice(totals=False, SubTotal=D('99.00')))
    assert computed.SubTotal == D('99.00')
    assert computed.Total == D('115.00')


def test_the_input_is_not_mutated(make_invoice: MakeInvoice) -> None:
    original = make_invoice(totals=False)
    compute(original)
    assert original == make_invoice(totals=False)
    assert original.SubTotal is None and original.Impuestos is None


def test_an_unknown_currency_leaves_the_derived_values_unset(make_invoice: MakeInvoice) -> None:
    computed = compute(make_invoice(totals=False, Moneda='ZZZ'))
    assert computed.SubTotal is None
    assert computed.Total is None
    assert computed.Impuestos is None


def test_a_non_finite_amount_leaves_what_it_feeds_unset(make_invoice: MakeInvoice) -> None:
    computed = compute(
        make_invoice(
            totals=False,
            Conceptos=[_concepto('NaN', traslados=[_iva('100.00', '16.00')])],
        )
    )
    assert computed.SubTotal is None
    assert computed.Total is None
    assert computed.Impuestos is not None
    assert computed.Impuestos.TotalImpuestosTrasladados == D('16.00')


def test_an_unroundable_amount_leaves_what_it_feeds_unset(make_invoice: MakeInvoice) -> None:
    computed = compute(make_invoice(totals=False, Conceptos=[_concepto('1E+100000')]))
    assert computed.SubTotal is None
    assert computed.Total is None


def _locales(traslados: str, retenciones: str) -> Any:
    from mictlanix.cfdi import implocal10

    return implocal10.ImpuestosLocales(
        TotaldeRetenciones=D(retenciones), TotaldeTraslados=D(traslados)
    )


def test_local_taxes_are_added_to_the_total(make_invoice: MakeInvoice) -> None:
    computed = compute(make_invoice(totals=False, Complemento=[_locales('3.00', '2.00')]))
    assert computed.Total == D('117.00')


def test_a_non_finite_local_tax_leaves_the_total_unset(make_invoice: MakeInvoice) -> None:
    computed = compute(make_invoice(totals=False, Complemento=[_locales('NaN', '2.00')]))
    assert computed.Total is None
    assert computed.SubTotal == D('100.00')
