"""User Story 1: income, expense and payment documents, built, validated and sealed."""

from collections.abc import Callable
from dataclasses import replace
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from lxml import etree

from mictlanix.cfdi import (
    CSD,
    ACuentaTerceros,
    CfdiRelacionado,
    CfdiRelacionados,
    Comprobante,
    Concepto,
    ConceptoImpuestos,
    ConceptoTraslado,
    CuentaPredial,
    InformacionAduanera,
    InformacionGlobal,
    Parte,
    ParteInformacionAduanera,
    Receptor,
    pagos20,
    payment_comprobante,
    seal,
)

D = Decimal
EXPECTED = Path(__file__).resolve().parent.parent / 'fixtures' / 'expected'
MakeInvoice = Callable[..., Comprobante]
Check = Callable[[Comprobante], str]
RELATED_UUID = '5FB2822E-396D-4725-8521-CDC4BDD20CCF'


def _expected(name: str) -> str:
    return (EXPECTED / name).read_text(encoding='utf-8')


def _iva(base: str, importe: str) -> ConceptoTraslado:
    return ConceptoTraslado(
        Base=D(base),
        Impuesto='002',
        TipoFactor='Tasa',
        TasaOCuota=D('0.160000'),
        Importe=D(importe),
    )


def credit_note(make_invoice: MakeInvoice) -> Comprobante:
    invoice = make_invoice(totals=False)
    return make_invoice(
        totals=False,
        TipoDeComprobante='E',
        CfdiRelacionados=[
            CfdiRelacionados(
                TipoRelacion='01', CfdiRelacionado=[CfdiRelacionado(UUID=RELATED_UUID)]
            )
        ],
        Receptor=replace(invoice.Receptor, UsoCFDI='G02'),
        Conceptos=[
            Concepto(
                ClaveProdServ='84111506',
                Cantidad=D('1'),
                ClaveUnidad='ACT',
                Descripcion='Devolucion',
                ValorUnitario=D('50.00'),
                Importe=D('50.00'),
                ObjetoImp='02',
                Impuestos=ConceptoImpuestos(Traslados=[_iva('50.00', '8.00')]),
            )
        ],
    )


def payment(make_invoice: MakeInvoice) -> Comprobante:
    invoice = make_invoice(totals=False)
    pagos = pagos20.Pagos(
        Pago=[
            pagos20.Pago(
                FechaPago=datetime(2026, 11, 17, 10, 0, 0),
                FormaDePagoP='03',
                MonedaP='MXN',
                TipoCambioP=D('1'),
                Monto=D('116.00'),
                DoctoRelacionado=[
                    pagos20.DoctoRelacionado(
                        IdDocumento=RELATED_UUID,
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
    return payment_comprobante(
        Emisor=invoice.Emisor,
        Receptor=replace(invoice.Receptor, UsoCFDI='CP01'),
        Fecha=datetime(2026, 11, 17, 12, 0, 0),
        LugarExpedicion='42501',
        Pagos=pagos,
    )


def test_an_income_document(make_invoice: MakeInvoice, builds_validates_seals: Check) -> None:
    cadena = builds_validates_seals(make_invoice(totals=False))
    assert cadena == _expected('ingreso.sellado.cadena.txt')


def test_an_expense_document_related_to_an_earlier_one(
    make_invoice: MakeInvoice, builds_validates_seals: Check, csd: CSD
) -> None:
    document = credit_note(make_invoice)
    assert builds_validates_seals(document) == _expected('egreso.cadena.txt')
    sello = etree.fromstring(seal(document, csd)).get('Sello')
    assert sello == _expected('egreso.sello.txt')


def test_a_payment_document_with_pagos_20(
    make_invoice: MakeInvoice, builds_validates_seals: Check, csd: CSD
) -> None:
    document = payment(make_invoice)
    cadena = builds_validates_seals(document)
    assert cadena == _expected('pago.cadena.txt')
    assert '|2.0|100.00|16.00|116.00|2026-11-17T10:00:00|03|MXN|1|116.00|' in cadena
    sello = etree.fromstring(seal(document, csd)).get('Sello')
    assert sello == _expected('pago.sello.txt')


def test_a_global_invoice_to_the_general_public(
    make_invoice: MakeInvoice, builds_validates_seals: Check
) -> None:
    document = make_invoice(
        totals=False,
        Receptor=Receptor(
            Rfc='XAXX010101000',
            Nombre='PUBLICO EN GENERAL',
            DomicilioFiscalReceptor='42501',
            RegimenFiscalReceptor='616',
            UsoCFDI='S01',
        ),
        InformacionGlobal=InformacionGlobal(Periodicidad='01', Meses='11', Año=2026),
    )
    assert '|01|11|2026|' in builds_validates_seals(document)


def test_a_concept_on_behalf_of_a_third_party(
    make_invoice: MakeInvoice, builds_validates_seals: Check
) -> None:
    invoice = make_invoice(totals=False)
    concepto = replace(
        invoice.Conceptos[0],
        ACuentaTerceros=ACuentaTerceros(
            RfcACuentaTerceros='AAA010101AAA',
            NombreACuentaTerceros='TERCERO DE PRUEBA',
            RegimenFiscalACuentaTerceros='601',
            DomicilioFiscalACuentaTerceros='01000',
        ),
    )
    cadena = builds_validates_seals(replace(invoice, Conceptos=[concepto]))
    assert '|AAA010101AAA|TERCERO DE PRUEBA|601|01000|' in cadena


def test_a_concept_with_customs_property_and_parts(
    make_invoice: MakeInvoice, builds_validates_seals: Check
) -> None:
    invoice = make_invoice(totals=False)
    concepto = replace(
        invoice.Conceptos[0],
        InformacionAduanera=[InformacionAduanera(NumeroPedimento='25  01  3173  5000001')],
        CuentaPredial=[CuentaPredial(Numero='12345678')],
        Parte=[
            Parte(
                ClaveProdServ='01010101',
                Cantidad=D('1'),
                Descripcion='Pieza',
                ValorUnitario=D('10.00'),
                Importe=D('10.00'),
                InformacionAduanera=[
                    ParteInformacionAduanera(NumeroPedimento='25  01  3173  5000002')
                ],
            )
        ],
    )
    cadena = builds_validates_seals(replace(invoice, Conceptos=[concepto]))
    assert (
        # The SAT's stylesheet normalizes spaces, so the pedimento's double spaces become single.
        '|25 01 3173 5000001|12345678|01010101|1|Pieza|10.00|10.00|25 01 3173 5000002|'
    ) in cadena


def test_an_income_document_in_usd(
    make_invoice: MakeInvoice, builds_validates_seals: Check
) -> None:
    cadena = builds_validates_seals(make_invoice(totals=False, Moneda='USD', TipoCambio=D('17.5')))
    assert '|100.00|USD|17.5|116.00|I|' in cadena
