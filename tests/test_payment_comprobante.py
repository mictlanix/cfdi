from collections.abc import Callable
from dataclasses import replace
from datetime import datetime
from decimal import Decimal

from mictlanix.cfdi import (
    CfdiRelacionado,
    CfdiRelacionados,
    Comprobante,
    Concepto,
    pagos20,
    payment_comprobante,
    to_xml,
    validate,
)

D = Decimal
MakeInvoice = Callable[..., Comprobante]


def _pagos() -> pagos20.Pagos:
    return pagos20.Pagos(
        Pago=[
            pagos20.Pago(
                FechaPago=datetime(2026, 11, 17, 10, 0, 0),
                FormaDePagoP='03',
                MonedaP='MXN',
                TipoCambioP=D('1'),
                Monto=D('116.00'),
                DoctoRelacionado=[
                    pagos20.DoctoRelacionado(
                        IdDocumento='5FB2822E-396D-4725-8521-CDC4BDD20CCF',
                        MonedaDR='MXN',
                        EquivalenciaDR=D('1'),
                        NumParcialidad=1,
                        ImpSaldoAnt=D('116.00'),
                        ImpPagado=D('116.00'),
                        ImpSaldoInsoluto=D('0.00'),
                        ObjetoImpDR='02',
                        ImpuestosDR=pagos20.ImpuestosDR(
                            TrasladosDR=[
                                pagos20.TrasladoDR(
                                    BaseDR=D('100.00'),
                                    ImpuestoDR='002',
                                    TipoFactorDR='Tasa',
                                    TasaOCuotaDR=D('0.160000'),
                                    ImporteDR=D('16.00'),
                                )
                            ]
                        ),
                    )
                ],
            )
        ]
    )


def _payment(make_invoice: MakeInvoice, **changes: object) -> Comprobante:
    invoice = make_invoice()
    receptor = invoice.Receptor
    return payment_comprobante(
        Emisor=invoice.Emisor,
        Receptor=replace(receptor, UsoCFDI='CP01'),
        Fecha=datetime(2026, 11, 17, 12, 0, 0),
        LugarExpedicion='42501',
        Pagos=_pagos(),
        **changes,  # type: ignore[arg-type]
    )


def test_the_fixed_values_of_a_payment_document(make_invoice: MakeInvoice) -> None:
    payment = _payment(make_invoice)
    assert payment.TipoDeComprobante == 'P'
    assert payment.Moneda == 'XXX'
    assert payment.SubTotal == 0 and payment.Total == 0
    assert payment.Exportacion == '01'
    assert payment.FormaPago is None and payment.MetodoPago is None
    assert payment.Impuestos is None and payment.TipoCambio is None
    assert payment.Conceptos == [
        Concepto(
            ClaveProdServ='84111506',
            Cantidad=D('1'),
            ClaveUnidad='ACT',
            Descripcion='Pago',
            ValorUnitario=D('0'),
            Importe=D('0'),
            ObjetoImp='01',
        )
    ]
    assert payment.Complemento == [_pagos()]


def test_serie_folio_and_related_documents_are_passed_through(make_invoice: MakeInvoice) -> None:
    related = [
        CfdiRelacionados(
            TipoRelacion='04',
            CfdiRelacionado=[CfdiRelacionado(UUID='5FB2822E-396D-4725-8521-CDC4BDD20CCF')],
        )
    ]
    payment = _payment(make_invoice, Serie='P', Folio='7', CfdiRelacionados=related)
    assert (payment.Serie, payment.Folio, payment.CfdiRelacionados) == ('P', '7', related)


def test_a_payment_document_is_valid_with_its_derived_totals(make_invoice: MakeInvoice) -> None:
    payment = _payment(make_invoice)
    assert validate(payment) == []
    xml = to_xml(payment)
    assert b'pago20:Pagos' in xml
    assert b'SubTotal="0"' in xml and b'Total="0"' in xml and b'Moneda="XXX"' in xml
