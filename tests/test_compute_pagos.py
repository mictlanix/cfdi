"""Derived values of the Pagos 2.0 complement (data-model.md section 3.2)."""

from collections.abc import Callable
from datetime import datetime
from decimal import Decimal
from typing import Any

from mictlanix.cfdi import Comprobante, compute, pagos20

D = Decimal
MakeInvoice = Callable[..., Comprobante]
UUID = '5FB2822E-396D-4725-8521-CDC4BDD20CCF'


def iva_dr(base: str, importe: str, tasa: str = '0.160000') -> pagos20.TrasladoDR:
    return pagos20.TrasladoDR(
        BaseDR=D(base),
        ImpuestoDR='002',
        TipoFactorDR='Tasa',
        TasaOCuotaDR=D(tasa),
        ImporteDR=D(importe),
    )


def docto(
    *,
    traslados: list[pagos20.TrasladoDR] | None = None,
    retenciones: list[pagos20.RetencionDR] | None = None,
    **changes: Any,
) -> pagos20.DoctoRelacionado:
    values: dict[str, Any] = {
        'IdDocumento': UUID,
        'MonedaDR': 'MXN',
        'EquivalenciaDR': D('1'),
        'NumParcialidad': 1,
        'ImpSaldoAnt': D('116.00'),
        'ImpPagado': D('116.00'),
        'ImpSaldoInsoluto': D('0.00'),
        'ObjetoImpDR': '02' if traslados or retenciones else '01',
    }
    if traslados or retenciones:
        values['ImpuestosDR'] = pagos20.ImpuestosDR(
            TrasladosDR=traslados or [], RetencionesDR=retenciones or []
        )
    values.update(changes)
    return pagos20.DoctoRelacionado(**values)


def pago(*doctos: pagos20.DoctoRelacionado, **changes: Any) -> pagos20.Pago:
    values: dict[str, Any] = {
        'FechaPago': datetime(2026, 11, 17, 10, 0, 0),
        'FormaDePagoP': '03',
        'MonedaP': 'MXN',
        'TipoCambioP': D('1'),
        'Monto': D('116.00'),
        'DoctoRelacionado': list(doctos),
    }
    values.update(changes)
    return pagos20.Pago(**values)


def computed(make_invoice: MakeInvoice, *pagos: pagos20.Pago) -> pagos20.Pagos:
    document = make_invoice(totals=False, Complemento=[pagos20.Pagos(Pago=list(pagos))])
    result = compute(document).Complemento[0]
    assert isinstance(result, pagos20.Pagos)
    return result


def test_impuestos_p_sums_the_related_documents_by_tax_factor_and_rate(
    make_invoice: MakeInvoice,
) -> None:
    pagos = computed(
        make_invoice,
        pago(
            docto(traslados=[iva_dr('50.000000', '8.000000')]),
            docto(
                traslados=[
                    iva_dr('50.000000', '8.000000'),
                    iva_dr('10.000000', '0.800000', '0.080000'),
                ]
            ),
        ),
    )
    assert pagos.Pago[0].ImpuestosP == pagos20.ImpuestosP(
        TrasladosP=[
            pagos20.TrasladoP(
                BaseP=D('100.000000'),
                ImpuestoP='002',
                TipoFactorP='Tasa',
                TasaOCuotaP=D('0.160000'),
                ImporteP=D('16.000000'),
            ),
            pagos20.TrasladoP(
                BaseP=D('10.000000'),
                ImpuestoP='002',
                TipoFactorP='Tasa',
                TasaOCuotaP=D('0.080000'),
                ImporteP=D('0.800000'),
            ),
        ]
    )


def test_sums_are_exact_when_currencies_match(make_invoice: MakeInvoice) -> None:
    pagos = computed(
        make_invoice,
        pago(
            docto(traslados=[iva_dr('8.620690', '1.379310')]),
            docto(traslados=[iva_dr('8.620690', '1.379310')]),
        ),
    )
    assert pagos.Pago[0].ImpuestosP is not None
    assert pagos.Pago[0].ImpuestosP.TrasladosP[0].ImporteP == D('2.758620')


def test_withholdings_are_grouped_by_tax(make_invoice: MakeInvoice) -> None:
    retencion = pagos20.RetencionDR(
        BaseDR=D('100.00'),
        ImpuestoDR='001',
        TipoFactorDR='Tasa',
        TasaOCuotaDR=D('0.100000'),
        ImporteDR=D('10.00'),
    )
    pagos = computed(
        make_invoice, pago(docto(retenciones=[retencion]), docto(retenciones=[retencion]))
    )
    assert pagos.Pago[0].ImpuestosP == pagos20.ImpuestosP(
        RetencionesP=[pagos20.RetencionP(ImpuestoP='001', ImporteP=D('20.00'))]
    )
    assert pagos.Totales is not None
    assert pagos.Totales.TotalRetencionesISR == D('20.00')
    assert pagos.Totales.TotalRetencionesIVA is None


def test_exempt_groups_carry_only_the_base(make_invoice: MakeInvoice) -> None:
    exento = pagos20.TrasladoDR(BaseDR=D('100.00'), ImpuestoDR='002', TipoFactorDR='Exento')
    pagos = computed(make_invoice, pago(docto(traslados=[exento]), Monto=D('100.00')))
    assert pagos.Pago[0].ImpuestosP == pagos20.ImpuestosP(
        TrasladosP=[pagos20.TrasladoP(BaseP=D('100.00'), ImpuestoP='002', TipoFactorP='Exento')]
    )
    assert pagos.Totales == pagos20.Totales(
        TotalTrasladosBaseIVAExento=D('100.00'), MontoTotalPagos=D('100.00')
    )


def test_totales_fill_each_attribute_that_has_contributions(make_invoice: MakeInvoice) -> None:
    pagos = computed(
        make_invoice,
        pago(docto(traslados=[iva_dr('100.000000', '16.000000')])),
        pago(docto(traslados=[iva_dr('50.00', '4.00', '0.080000')]), Monto=D('54.00')),
        pago(docto(traslados=[iva_dr('20.00', '0.00', '0.000000')]), Monto=D('20.00')),
    )
    assert pagos.Totales == pagos20.Totales(
        TotalTrasladosBaseIVA16=D('100.00'),
        TotalTrasladosImpuestoIVA16=D('16.00'),
        TotalTrasladosBaseIVA8=D('50.00'),
        TotalTrasladosImpuestoIVA8=D('4.00'),
        TotalTrasladosBaseIVA0=D('20.00'),
        TotalTrasladosImpuestoIVA0=D('0.00'),
        MontoTotalPagos=D('190.00'),
    )


def test_a_payment_in_usd_settling_an_mxn_document(make_invoice: MakeInvoice) -> None:
    usd = pago(
        docto(
            traslados=[iva_dr('10000.00', '1600.00')],
            EquivalenciaDR=D('17.5'),
            ImpSaldoAnt=D('11600.00'),
            ImpPagado=D('11600.00'),
        ),
        MonedaP='USD',
        TipoCambioP=D('17.5'),
        Monto=D('662.86'),
    )
    pagos = computed(make_invoice, usd)
    impuestos = pagos.Pago[0].ImpuestosP
    assert impuestos is not None
    assert impuestos.TrasladosP[0].BaseP == D('571.428571')
    assert impuestos.TrasladosP[0].ImporteP == D('91.428571')
    assert pagos.Totales == pagos20.Totales(
        TotalTrasladosBaseIVA16=D('10000.00'),
        TotalTrasladosImpuestoIVA16=D('1600.00'),
        MontoTotalPagos=D('11600.05'),
    )


def test_values_the_caller_set_are_kept(make_invoice: MakeInvoice) -> None:
    mine = pagos20.Totales(MontoTotalPagos=D('1.00'))
    document = make_invoice(
        totals=False,
        Complemento=[
            pagos20.Pagos(Totales=mine, Pago=[pago(docto(traslados=[iva_dr('100.00', '16.00')]))])
        ],
    )
    result = compute(document).Complemento[0]
    assert isinstance(result, pagos20.Pagos)
    assert result.Totales == mine
    assert result.Pago[0].ImpuestosP is not None


def test_unusable_inputs_leave_the_derived_values_unset(make_invoice: MakeInvoice) -> None:
    cases = [
        pago(docto(traslados=[iva_dr('100.00', '16.00')], EquivalenciaDR=D('0'))),
        pago(docto(traslados=[iva_dr('100.00', '16.00')], EquivalenciaDR=None)),
        pago(docto(traslados=[iva_dr('100.00', '16.00')]), TipoCambioP=None),
        pago(docto(traslados=[iva_dr('100.00', '16.00')]), MonedaP='ZZZ'),
        pago(docto(traslados=[iva_dr('100.00', '16.00')]), Monto=D('NaN')),
    ]
    for case in cases:
        pagos = computed(make_invoice, case)
        assert pagos.Totales is None
        assert pagos.Pago[0].ImpuestosP is None
