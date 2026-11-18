"""Anexo 20 rules (contracts/validation-rules.md) and the library's own rules."""

from __future__ import annotations

import re
from collections.abc import Callable, Iterator
from dataclasses import dataclass, replace
from decimal import Decimal
from pathlib import Path
from typing import Any, ClassVar

import pytest

from mictlanix.cfdi import (
    ACuentaTerceros,
    Comprobante,
    ConceptComplement,
    Concepto,
    ConceptoImpuestos,
    ConceptoRetencion,
    ConceptoTraslado,
    DocumentComplement,
    Impuestos,
    InformacionAduanera,
    InformacionGlobal,
    Parte,
    ParteInformacionAduanera,
    Receptor,
    Retencion,
    Traslado,
    _rules,
    validate,
)
from mictlanix.cfdi._xml import XmlClass, attr

D = Decimal
MakeInvoice = Callable[..., Comprobante]
RULES_CONTRACT = (
    Path(__file__).resolve().parent.parent
    / 'specs'
    / '001-cfdi40-complements-sealing'
    / 'contracts'
    / 'validation-rules.md'
)

DOC = '/cfdi:Comprobante'
RECEPTOR = f'{DOC}/cfdi:Receptor'
CONCEPTO = f'{DOC}/cfdi:Conceptos/cfdi:Concepto'
C_TRASLADO = f'{CONCEPTO}/cfdi:Impuestos/cfdi:Traslados/cfdi:Traslado'
C_RETENCION = f'{CONCEPTO}/cfdi:Impuestos/cfdi:Retenciones/cfdi:Retencion'
IMPUESTOS = f'{DOC}/cfdi:Impuestos'
D_TRASLADO = f'{IMPUESTOS}/cfdi:Traslados/cfdi:Traslado'
D_RETENCION = f'{IMPUESTOS}/cfdi:Retenciones/cfdi:Retencion'
PUBLICO = 'PUBLICO EN GENERAL'
EXT = 'EXT990101NI1'
EXT_NOMBRE = (
    'EXPEDICIÓN DE CFDI POR RESIDENTES EN MÉXICO QUE PRESTAN SERVICIOS DE INTERMEDIACIÓN '
    'ENTRE TERCEROS A OFERENTES DE BIENES Y SERVICIOS RESIDENTES EN EL EXTRANJERO'
)


# Builders ------------------------------------------------------------------------------------


def iva(base: str = '100.00', importe: str | None = '16.00', **changes: Any) -> ConceptoTraslado:
    values: dict[str, Any] = {
        'Base': D(base),
        'Impuesto': '002',
        'TipoFactor': 'Tasa',
        'TasaOCuota': D('0.160000'),
        'Importe': None if importe is None else D(importe),
    }
    values.update(changes)
    return ConceptoTraslado(**values)


def exento(base: str = '100.00', **changes: Any) -> ConceptoTraslado:
    values: dict[str, Any] = {'Base': D(base), 'Impuesto': '002', 'TipoFactor': 'Exento'}
    values.update(changes)
    return ConceptoTraslado(**values)


def isr(base: str = '100.00', tasa: str = '0.100000', importe: str = '10.00') -> ConceptoRetencion:
    return ConceptoRetencion(
        Base=D(base), Impuesto='001', TipoFactor='Tasa', TasaOCuota=D(tasa), Importe=D(importe)
    )


def concepto(
    *,
    traslados: list[ConceptoTraslado] | None = None,
    retenciones: list[ConceptoRetencion] | None = None,
    **changes: Any,
) -> Concepto:
    values: dict[str, Any] = {
        'ClaveProdServ': '01010101',
        'Cantidad': D('1'),
        'ClaveUnidad': 'ACT',
        'Descripcion': 'Venta',
        'ValorUnitario': D('100.00'),
        'Importe': D('100.00'),
        'ObjetoImp': '02',
        'Impuestos': ConceptoImpuestos(
            Traslados=[iva()] if traslados is None else traslados,
            Retenciones=retenciones or [],
        ),
    }
    values.update(changes)
    if values['ObjetoImp'] != '02' and 'Impuestos' not in changes:
        values['Impuestos'] = None
    return Concepto(**values)


def receptor(**changes: Any) -> Receptor:
    values: dict[str, Any] = {
        'Rfc': 'URE180429TM6',
        'Nombre': 'UNIVERSIDAD ROBOTICA ESPAÑOLA',
        'DomicilioFiscalReceptor': '86991',
        'RegimenFiscalReceptor': '601',
        'UsoCFDI': 'G03',
    }
    values.update(changes)
    return Receptor(**values)


def generic(rfc: str = 'XAXX010101000', **changes: Any) -> Receptor:
    values: dict[str, Any] = {
        'Rfc': rfc,
        'Nombre': PUBLICO if rfc == 'XAXX010101000' else 'EXTRANJERO',
        'DomicilioFiscalReceptor': '42501',
        'RegimenFiscalReceptor': '616',
        'UsoCFDI': 'S01',
    }
    values.update(changes)
    return Receptor(**values)


def terceros(**changes: Any) -> ACuentaTerceros:
    values: dict[str, Any] = {
        'RfcACuentaTerceros': 'AAA010101AAA',
        'NombreACuentaTerceros': 'TERCERO',
        'RegimenFiscalACuentaTerceros': '601',
        'DomicilioFiscalACuentaTerceros': '01000',
    }
    values.update(changes)
    return ACuentaTerceros(**values)


def doc_impuestos(**changes: Any) -> Impuestos:
    values: dict[str, Any] = {
        'TotalImpuestosTrasladados': D('16.00'),
        'Traslados': [
            Traslado(
                Base=D('100.00'),
                Impuesto='002',
                TipoFactor='Tasa',
                TasaOCuota=D('0.160000'),
                Importe=D('16.00'),
            )
        ],
    }
    values.update(changes)
    return Impuestos(**values)


PRECISE = {'Cantidad': D('1.000000')}

Case = tuple[Callable[[MakeInvoice], Comprobante], str, str | None]


def _conceptos(*items: Concepto) -> dict[str, Any]:
    return {'Conceptos': list(items)}


CASES: dict[str, Case] = {
    'CFDI40103': (lambda m: m(totals=False, TipoDeComprobante='T'), DOC, 'FormaPago'),
    'CFDI40105': (lambda m: m(totals=False, MetodoPago='PPD'), DOC, 'FormaPago'),
    'CFDI40107': (lambda m: m(totals=False, SubTotal=D('100.001')), DOC, 'SubTotal'),
    'CFDI40108': (lambda m: m(totals=False, SubTotal=D('90.00')), DOC, 'SubTotal'),
    'CFDI40109': (
        lambda m: m(totals=False, TipoDeComprobante='T', FormaPago=None, MetodoPago=None),
        DOC,
        'SubTotal',
    ),
    'CFDI40110': (lambda m: m(totals=False, Descuento=D('200.00')), DOC, 'Descuento'),
    'CFDI40111': (
        lambda m: m(
            totals=False, Descuento=D('5.00'), **_conceptos(concepto(Descuento=D('10.00')))
        ),
        DOC,
        'Descuento',
    ),
    'CFDI40112': (lambda m: m(totals=False, Descuento=D('10.001')), DOC, 'Descuento'),
    'CFDI40114': (lambda m: m(totals=False, TipoCambio=D('2')), DOC, 'TipoCambio'),
    'CFDI40115': (lambda m: m(totals=False, Moneda='USD'), DOC, 'TipoCambio'),
    'CFDI40116': (
        lambda m: m(totals=False, Moneda='XXX', TipoCambio=D('1')),
        DOC,
        'TipoCambio',
    ),
    'CFDI40119': (lambda m: m(totals=False, Total=D('200.00')), DOC, 'Total'),
    'CFDI40125': (
        lambda m: m(totals=False, TipoDeComprobante='P', FormaPago=None),
        DOC,
        'MetodoPago',
    ),
    'CFDI40130': (lambda m: m(totals=False, Receptor=generic()), DOC, None),
    'CFDI40132': (
        lambda m: m(
            totals=False,
            Receptor=generic(),
            InformacionGlobal=InformacionGlobal(Periodicidad='05', Meses='13', Año=2026),
        ),
        f'{DOC}/cfdi:InformacionGlobal',
        'Periodicidad',
    ),
    'CFDI40134': (
        lambda m: m(
            totals=False,
            Receptor=generic(),
            InformacionGlobal=InformacionGlobal(Periodicidad='01', Meses='13', Año=2026),
        ),
        f'{DOC}/cfdi:InformacionGlobal',
        'Meses',
    ),
    'CFDI40135': (
        lambda m: m(
            totals=False,
            Receptor=generic(),
            InformacionGlobal=InformacionGlobal(Periodicidad='05', Meses='01', Año=2026),
        ),
        f'{DOC}/cfdi:InformacionGlobal',
        'Meses',
    ),
    'CFDI40141': (
        lambda m: m(totals=False, Emisor=replace(m().Emisor, RegimenFiscal='605')),
        f'{DOC}/cfdi:Emisor',
        'RegimenFiscal',
    ),
    'CFDI40146': (
        lambda m: m(totals=False, Receptor=receptor(Nombre=PUBLICO)),
        f'{DOC}/cfdi:Receptor',
        'Nombre',
    ),
    'CFDI40149': (
        lambda m: m(totals=False, Receptor=generic(DomicilioFiscalReceptor='86991')),
        f'{DOC}/cfdi:Receptor',
        'DomicilioFiscalReceptor',
    ),
    'CFDI40151': (
        lambda m: m(totals=False, Receptor=receptor(ResidenciaFiscal='USA')),
        f'{DOC}/cfdi:Receptor',
        'ResidenciaFiscal',
    ),
    'CFDI40152': (
        lambda m: m(totals=False, Receptor=generic('XEXX010101000', ResidenciaFiscal='MEX')),
        f'{DOC}/cfdi:Receptor',
        'ResidenciaFiscal',
    ),
    'CFDI40154': (
        lambda m: m(totals=False, Receptor=receptor(NumRegIdTrib='123456789')),
        f'{DOC}/cfdi:Receptor',
        'NumRegIdTrib',
    ),
    'CFDI40156': (
        lambda m: m(
            totals=False,
            Receptor=generic('XEXX010101000', ResidenciaFiscal='USA', NumRegIdTrib='ABC'),
        ),
        f'{DOC}/cfdi:Receptor',
        'NumRegIdTrib',
    ),
    'CFDI40158': (
        lambda m: m(totals=False, Receptor=receptor(RegimenFiscalReceptor='605', UsoCFDI='S01')),
        f'{DOC}/cfdi:Receptor',
        'RegimenFiscalReceptor',
    ),
    'CFDI40159': (
        lambda m: m(totals=False, Receptor=generic(RegimenFiscalReceptor='601')),
        f'{DOC}/cfdi:Receptor',
        'RegimenFiscalReceptor',
    ),
    'CFDI40161': (
        lambda m: m(totals=False, Receptor=receptor(UsoCFDI='D01')),
        f'{DOC}/cfdi:Receptor',
        'UsoCFDI',
    ),
    'CFDI40164': (
        lambda m: m(totals=False, **_conceptos(concepto(ClaveProdServ='80111700', ObjetoImp='01'))),
        CONCEPTO,
        'ClaveProdServ',
    ),
    'CFDI40166': (
        lambda m: m(
            totals=False,
            **_conceptos(concepto(ValorUnitario=D('0.00'), Importe=D('0.00'), ObjetoImp='01')),
        ),
        CONCEPTO,
        'ValorUnitario',
    ),
    'CFDI40167': (
        lambda m: m(totals=False, **_conceptos(concepto(Importe=D('101.00'), **PRECISE))),
        CONCEPTO,
        'Importe',
    ),
    'CFDI40168': (
        lambda m: m(totals=False, **_conceptos(concepto(Descuento=D('1.001')))),
        CONCEPTO,
        'Descuento',
    ),
    'CFDI40169': (
        lambda m: m(totals=False, **_conceptos(concepto(Descuento=D('200.00')))),
        CONCEPTO,
        'Descuento',
    ),
    'CFDI40171': (
        lambda m: m(totals=False, **_conceptos(concepto(Impuestos=None))),
        CONCEPTO,
        'ObjetoImp',
    ),
    'CFDI40172': (
        lambda m: m(
            totals=False,
            **_conceptos(concepto(ObjetoImp='01', Impuestos=ConceptoImpuestos(Traslados=[iva()]))),
        ),
        CONCEPTO,
        'ObjetoImp',
    ),
    'CFDI40173': (
        lambda m: m(totals=False, **_conceptos(concepto(Impuestos=ConceptoImpuestos()))),
        f'{CONCEPTO}/cfdi:Impuestos',
        None,
    ),
    'CFDI40177': (
        lambda m: m(
            totals=False, **_conceptos(concepto(traslados=[exento(TasaOCuota=D('0.160000'))]))
        ),
        C_TRASLADO,
        'TipoFactor',
    ),
    'CFDI40178': (
        lambda m: m(totals=False, **_conceptos(concepto(traslados=[iva(importe=None)]))),
        C_TRASLADO,
        'TipoFactor',
    ),
    'CFDI40179': (
        lambda m: m(
            totals=False,
            **_conceptos(concepto(traslados=[iva(TasaOCuota=D('0.150000'), Importe=D('15.00'))])),
        ),
        C_TRASLADO,
        'TasaOCuota',
    ),
    'CFDI40180': (
        lambda m: m(totals=False, **_conceptos(concepto(traslados=[iva(importe='20.00')]))),
        C_TRASLADO,
        'Importe',
    ),
    'CFDI40184': (
        lambda m: m(
            totals=False,
            **_conceptos(
                concepto(
                    retenciones=[
                        ConceptoRetencion(
                            Base=D('100.00'),
                            Impuesto='001',
                            TipoFactor='Exento',
                            TasaOCuota=D('0.100000'),
                            Importe=D('10.00'),
                        )
                    ]
                )
            ),
        ),
        C_RETENCION,
        'TipoFactor',
    ),
    'CFDI40185': (
        lambda m: m(
            totals=False,
            **_conceptos(concepto(retenciones=[isr(tasa='0.400000', importe='40.00')])),
        ),
        C_RETENCION,
        'TasaOCuota',
    ),
    'CFDI40186': (
        lambda m: m(totals=False, **_conceptos(concepto(retenciones=[isr(importe='50.00')]))),
        C_RETENCION,
        'Importe',
    ),
    'CFDI40188': (
        lambda m: m(
            totals=False,
            **_conceptos(concepto(ACuentaTerceros=terceros(RfcACuentaTerceros='EKU9003173C9'))),
        ),
        f'{CONCEPTO}/cfdi:ACuentaTerceros',
        'RfcACuentaTerceros',
    ),
    'CFDI40189': (
        lambda m: m(
            totals=False,
            **_conceptos(
                concepto(
                    ACuentaTerceros=terceros(
                        RfcACuentaTerceros=EXT,
                        RegimenFiscalACuentaTerceros='616',
                        DomicilioFiscalACuentaTerceros='42501',
                    )
                )
            ),
        ),
        f'{CONCEPTO}/cfdi:ACuentaTerceros',
        'NombreACuentaTerceros',
    ),
    'CFDI40193': (
        lambda m: m(
            totals=False,
            **_conceptos(
                concepto(
                    ACuentaTerceros=terceros(
                        RfcACuentaTerceros=EXT,
                        NombreACuentaTerceros=EXT_NOMBRE,
                        RegimenFiscalACuentaTerceros='616',
                    )
                )
            ),
        ),
        f'{CONCEPTO}/cfdi:ACuentaTerceros',
        'DomicilioFiscalACuentaTerceros',
    ),
    'CFDI140223': (
        lambda m: m(
            totals=False,
            **_conceptos(
                concepto(
                    ACuentaTerceros=terceros(
                        RfcACuentaTerceros=EXT,
                        NombreACuentaTerceros=EXT_NOMBRE,
                        DomicilioFiscalACuentaTerceros='42501',
                    )
                )
            ),
        ),
        f'{CONCEPTO}/cfdi:ACuentaTerceros',
        'RegimenFiscalACuentaTerceros',
    ),
    'CFDI40194': (
        lambda m: m(
            totals=False,
            **_conceptos(
                concepto(
                    InformacionAduanera=[
                        InformacionAduanera(NumeroPedimento='25  99  3173  5000001')
                    ]
                )
            ),
        ),
        f'{CONCEPTO}/cfdi:InformacionAduanera',
        'NumeroPedimento',
    ),
    'CFDI40197': (
        lambda m: m(
            totals=False,
            **_conceptos(
                concepto(
                    Parte=[
                        Parte(
                            ClaveProdServ='01010101',
                            Cantidad=D('1'),
                            Descripcion='Pieza',
                            ValorUnitario=D('0.00'),
                            Importe=D('0.00'),
                        )
                    ]
                )
            ),
        ),
        f'{CONCEPTO}/cfdi:Parte',
        'ValorUnitario',
    ),
    'CFDI40198': (
        lambda m: m(
            totals=False,
            **_conceptos(
                concepto(
                    Parte=[
                        Parte(
                            ClaveProdServ='01010101',
                            Cantidad=D('1.000000'),
                            Descripcion='Pieza',
                            ValorUnitario=D('10.00'),
                            Importe=D('20.00'),
                        )
                    ]
                )
            ),
        ),
        f'{CONCEPTO}/cfdi:Parte',
        'Importe',
    ),
    'CFDI40199': (
        lambda m: m(
            totals=False,
            **_conceptos(
                concepto(
                    Parte=[
                        Parte(
                            ClaveProdServ='01010101',
                            Cantidad=D('1'),
                            Descripcion='Pieza',
                            InformacionAduanera=[
                                ParteInformacionAduanera(NumeroPedimento='25  01  0001  5000001')
                            ],
                        )
                    ]
                )
            ),
        ),
        f'{CONCEPTO}/cfdi:Parte/cfdi:InformacionAduanera',
        'NumeroPedimento',
    ),
    'CFDI140226': (
        lambda m: m(
            totals=False,
            **_conceptos(concepto(ObjetoImp='06', Impuestos=ConceptoImpuestos(Traslados=[iva()]))),
        ),
        CONCEPTO,
        'ObjetoImp',
    ),
    'CFDI140227': (
        lambda m: m(
            totals=False,
            **_conceptos(concepto(ObjetoImp='07', Impuestos=ConceptoImpuestos(Traslados=[iva()]))),
        ),
        CONCEPTO,
        'ObjetoImp',
    ),
    'CFDI140228': (
        lambda m: m(totals=False, **_conceptos(concepto(ClaveProdServ='15101505'))),
        CONCEPTO,
        'ClaveProdServ',
    ),
    'CFDI40201': (
        lambda m: m(totals=False, TipoDeComprobante='P', FormaPago=None, MetodoPago=None),
        IMPUESTOS,
        None,
    ),
    'CFDI40202': (
        lambda m: m(
            totals=False,
            **_conceptos(concepto(retenciones=[isr()])),
            Impuestos=doc_impuestos(
                TotalImpuestosRetenidos=D('10.001'),
                Retenciones=[Retencion(Impuesto='001', Importe=D('10.00'))],
            ),
        ),
        IMPUESTOS,
        'TotalImpuestosRetenidos',
    ),
    'CFDI40203': (
        lambda m: m(
            totals=False,
            **_conceptos(concepto(retenciones=[isr()])),
            Impuestos=doc_impuestos(
                TotalImpuestosRetenidos=D('11.00'),
                Retenciones=[Retencion(Impuesto='001', Importe=D('10.00'))],
            ),
        ),
        IMPUESTOS,
        'TotalImpuestosRetenidos',
    ),
    'CFDI40204': (
        lambda m: m(totals=False, Impuestos=doc_impuestos(TotalImpuestosTrasladados=D('16.001'))),
        IMPUESTOS,
        'TotalImpuestosTrasladados',
    ),
    'CFDI40205': (
        lambda m: m(totals=False, Impuestos=doc_impuestos(TotalImpuestosTrasladados=D('17.00'))),
        IMPUESTOS,
        'TotalImpuestosTrasladados',
    ),
    'CFDI40206': (
        lambda m: m(
            totals=False,
            **_conceptos(concepto(retenciones=[isr()])),
            Impuestos=doc_impuestos(Retenciones=[Retencion(Impuesto='001', Importe=D('10.00'))]),
        ),
        f'{IMPUESTOS}/cfdi:Retenciones',
        None,
    ),
    'CFDI40208': (
        lambda m: m(
            totals=False,
            **_conceptos(concepto(retenciones=[isr()])),
            Impuestos=doc_impuestos(
                TotalImpuestosRetenidos=D('10.00'),
                Retenciones=[
                    Retencion(Impuesto='001', Importe=D('5.00')),
                    Retencion(Impuesto='001', Importe=D('5.00')),
                ],
            ),
        ),
        f'{D_RETENCION}[2]',
        'Impuesto',
    ),
    'CFDI40209': (
        lambda m: m(
            totals=False,
            **_conceptos(concepto(retenciones=[isr()])),
            Impuestos=doc_impuestos(Retenciones=[Retencion(Impuesto='001', Importe=D('10.00'))]),
        ),
        D_RETENCION,
        'Importe',
    ),
    'CFDI40210': (
        lambda m: m(
            totals=False,
            **_conceptos(concepto(retenciones=[isr()])),
            Impuestos=doc_impuestos(
                TotalImpuestosRetenidos=D('10.001'),
                Retenciones=[Retencion(Impuesto='001', Importe=D('10.001'))],
            ),
        ),
        D_RETENCION,
        'Importe',
    ),
    'CFDI40211': (
        lambda m: m(
            totals=False,
            **_conceptos(concepto(retenciones=[isr()])),
            Impuestos=doc_impuestos(
                TotalImpuestosRetenidos=D('12.00'),
                Retenciones=[Retencion(Impuesto='001', Importe=D('12.00'))],
            ),
        ),
        D_RETENCION,
        'Importe',
    ),
    'CFDI40212': (
        lambda m: m(totals=False, Impuestos=doc_impuestos(TotalImpuestosTrasladados=None)),
        f'{IMPUESTOS}/cfdi:Traslados',
        None,
    ),
    'CFDI40213': (
        lambda m: m(
            totals=False,
            **_conceptos(concepto(traslados=[exento()])),
            Impuestos=Impuestos(
                Traslados=[
                    Traslado(
                        Base=D('100.00'),
                        Impuesto='002',
                        TipoFactor='Exento',
                        TasaOCuota=D('0.000000'),
                    )
                ]
            ),
        ),
        D_TRASLADO,
        None,
    ),
    'CFDI40214': (
        lambda m: m(
            totals=False,
            Impuestos=doc_impuestos(
                Traslados=[
                    Traslado(
                        Base=D('100.001'),
                        Impuesto='002',
                        TipoFactor='Tasa',
                        TasaOCuota=D('0.160000'),
                        Importe=D('16.00'),
                    )
                ]
            ),
        ),
        D_TRASLADO,
        'Base',
    ),
    'CFDI40215': (
        lambda m: m(
            totals=False,
            Impuestos=doc_impuestos(
                Traslados=[
                    Traslado(
                        Base=D('90.00'),
                        Impuesto='002',
                        TipoFactor='Tasa',
                        TasaOCuota=D('0.160000'),
                        Importe=D('16.00'),
                    )
                ]
            ),
        ),
        D_TRASLADO,
        'Base',
    ),
    'CFDI40216': (
        lambda m: m(
            totals=False,
            **_conceptos(concepto(traslados=[exento()])),
            Impuestos=Impuestos(
                Traslados=[Traslado(Base=D('90.00'), Impuesto='002', TipoFactor='Exento')]
            ),
        ),
        D_TRASLADO,
        'Base',
    ),
    'CFDI40218': (
        lambda m: m(
            totals=False,
            Impuestos=doc_impuestos(
                TotalImpuestosTrasladados=D('16.00'),
                Traslados=[
                    Traslado(
                        Base=D('50.00'),
                        Impuesto='002',
                        TipoFactor='Tasa',
                        TasaOCuota=D('0.160000'),
                        Importe=D('8.00'),
                    ),
                    Traslado(
                        Base=D('50.00'),
                        Impuesto='002',
                        TipoFactor='Tasa',
                        TasaOCuota=D('0.160000'),
                        Importe=D('8.00'),
                    ),
                ],
            ),
        ),
        f'{D_TRASLADO}[2]',
        'Impuesto',
    ),
    'CFDI40219': (
        lambda m: m(
            totals=False,
            Impuestos=doc_impuestos(
                Traslados=[
                    Traslado(
                        Base=D('100.00'),
                        Impuesto='002',
                        TipoFactor='Tasa',
                        TasaOCuota=D('0.150000'),
                        Importe=D('16.00'),
                    )
                ]
            ),
        ),
        D_TRASLADO,
        'TasaOCuota',
    ),
    'CFDI40220': (
        lambda m: m(
            totals=False,
            Impuestos=doc_impuestos(
                TotalImpuestosTrasladados=D('16.001'),
                Traslados=[
                    Traslado(
                        Base=D('100.00'),
                        Impuesto='002',
                        TipoFactor='Tasa',
                        TasaOCuota=D('0.160000'),
                        Importe=D('16.001'),
                    )
                ],
            ),
        ),
        D_TRASLADO,
        'Importe',
    ),
    'CFDI40221': (
        lambda m: m(
            totals=False,
            Impuestos=doc_impuestos(
                TotalImpuestosTrasladados=D('17.00'),
                Traslados=[
                    Traslado(
                        Base=D('100.00'),
                        Impuesto='002',
                        TipoFactor='Tasa',
                        TasaOCuota=D('0.160000'),
                        Importe=D('17.00'),
                    )
                ],
            ),
        ),
        D_TRASLADO,
        'Importe',
    ),
}


def _contract_codes(story: str) -> set[str]:
    text = RULES_CONTRACT.read_text(encoding='utf-8')
    return set(re.findall(rf'^\| (CFDI\d+) \|[^\n]*\| implemented in {story}', text, re.M))


def test_every_us1_rule_has_a_case_and_is_implemented() -> None:
    assert set(CASES) == _contract_codes('US1')
    assert _rules.implemented_codes() >= _contract_codes('US1')


def test_implemented_codes_equal_those_marked_implemented() -> None:
    assert _rules.implemented_codes() == _contract_codes('US1') | _contract_codes('US2')


@pytest.mark.parametrize('code', sorted(CASES))
def test_a_document_that_breaks_the_rule_is_reported(code: str, make_invoice: MakeInvoice) -> None:
    build, node, attribute = CASES[code]
    found = [v for v in validate(build(make_invoice)) if v.rule == code]
    assert found, f'{code} not reported'
    assert (found[0].node, found[0].attribute) == (node, attribute)


def test_the_quickstart_invoice_breaks_no_rule(make_invoice: MakeInvoice) -> None:
    assert validate(make_invoice(totals=False)) == []


def test_valid_pedimento_numbers_pass(make_invoice: MakeInvoice) -> None:
    item = concepto(
        InformacionAduanera=[InformacionAduanera(NumeroPedimento='25  01  3173  5000001')]
    )
    assert [
        v for v in validate(make_invoice(totals=False, Conceptos=[item])) if v.rule == 'CFDI40194'
    ] == []


def test_a_generic_receptor_with_global_information_breaks_no_rule(
    make_invoice: MakeInvoice,
) -> None:
    invoice = make_invoice(
        totals=False,
        Receptor=generic(),
        InformacionGlobal=InformacionGlobal(Periodicidad='01', Meses='11', Año=2026),
    )
    assert validate(invoice) == []


def test_xsd_and_rule_violations_are_reported_together(make_invoice: MakeInvoice) -> None:
    invoice = make_invoice(totals=False, MetodoPago='PPD', Receptor=receptor(Rfc='x'))
    rules = {v.rule for v in validate(invoice)}
    assert 'CFDI40105' in rules
    assert 'cvc-pattern-valid' in rules


def test_the_violations_of_one_rule_name_every_offending_node(make_invoice: MakeInvoice) -> None:
    invoice = make_invoice(
        totals=False,
        Conceptos=[concepto(Descuento=D('200.00')), concepto(Descuento=D('300.00'))],
    )
    nodes = [v.node for v in validate(invoice) if v.rule == 'CFDI40169']
    assert nodes == [f'{CONCEPTO}[1]', f'{CONCEPTO}[2]']


# Library rules -------------------------------------------------------------------------------


@dataclass(frozen=True, kw_only=True)
class SoloPagos(DocumentComplement):
    __xml__: ClassVar[XmlClass] = XmlClass('SoloPagos', 'urn:test:solopagos', 't')
    Clave: str = attr()


@dataclass(frozen=True, kw_only=True)
class DeConcepto(ConceptComplement):
    __xml__: ClassVar[XmlClass] = XmlClass('DeConcepto', 'urn:test:deconcepto', 'c')
    Clave: str = attr()


@pytest.fixture
def solo_pagos() -> Iterator[None]:
    key = ('urn:test:solopagos', 'SoloPagos')
    _rules.ALLOWED_DOCUMENT_TYPES[key] = frozenset({'P'})
    yield
    del _rules.ALLOWED_DOCUMENT_TYPES[key]


@pytest.mark.usefixtures('solo_pagos')
def test_a_complement_on_a_document_type_it_does_not_allow(make_invoice: MakeInvoice) -> None:
    invoice = make_invoice(totals=False, Complemento=[SoloPagos(Clave='x')])
    found = [
        (v.node, v.attribute) for v in validate(invoice) if v.rule == 'complement-document-type'
    ]
    assert found == [(f'{DOC}/cfdi:Complemento/t:SoloPagos', None)]


def test_a_concept_complement_under_complemento(make_invoice: MakeInvoice) -> None:
    invoice = make_invoice(totals=False, Complemento=[DeConcepto(Clave='x')])  # type: ignore[list-item]
    found = [v.node for v in validate(invoice) if v.rule == 'complement-level']
    assert found == [f'{DOC}/cfdi:Complemento/c:DeConcepto']


def test_a_document_complement_under_complemento_concepto(make_invoice: MakeInvoice) -> None:
    item = concepto(ComplementoConcepto=[SoloPagos(Clave='x')])
    found = [
        v.node
        for v in validate(make_invoice(totals=False, Conceptos=[item]))
        if v.rule == 'complement-level'
    ]
    assert found == [f'{CONCEPTO}/cfdi:ComplementoConcepto/t:SoloPagos']


def test_pagos_is_allowed_only_on_payment_documents(make_invoice: MakeInvoice) -> None:
    from datetime import datetime

    from mictlanix.cfdi import pagos20

    pagos = pagos20.Pagos(
        Totales=pagos20.Totales(MontoTotalPagos=D('116.00')),
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
                        ObjetoImpDR='01',
                    )
                ],
            )
        ],
    )
    invoice = make_invoice(totals=False, Complemento=[pagos])
    found = [
        (v.node, v.attribute) for v in validate(invoice) if v.rule == 'complement-document-type'
    ]
    assert found == [(f'{DOC}/cfdi:Complemento/pago20:Pagos', None)]


# User Story 2: rules tied to Comercio Exterior ----------------------------------------------


def _cce() -> Any:
    from tests.complements.test_comercioexterior20 import comercio_exterior

    return comercio_exterior()


def _export(m: MakeInvoice, **changes: Any) -> Comprobante:
    from tests.complements.test_comercioexterior20 import export

    return export(m, **changes)


CASES_US2: dict[str, Case] = {
    'CFDI40122': (lambda m: _export(m, Complemento=[]), DOC, 'Exportacion'),
    'CFDI40153': (
        lambda m: _export(
            m, Receptor=replace(_export(m).Receptor, ResidenciaFiscal=None, NumRegIdTrib=None)
        ),
        RECEPTOR,
        'ResidenciaFiscal',
    ),
    'CFDI40155': (
        lambda m: _export(m, Receptor=replace(_export(m).Receptor, NumRegIdTrib=None)),
        RECEPTOR,
        'NumRegIdTrib',
    ),
    'CFDI40195': (
        lambda m: _export(
            m,
            Conceptos=[
                replace(
                    _export(m).Conceptos[0],
                    InformacionAduanera=[
                        InformacionAduanera(NumeroPedimento='25  01  3173  5000001')
                    ],
                )
            ],
        ),
        f'{CONCEPTO}/cfdi:InformacionAduanera',
        'NumeroPedimento',
    ),
    'CFDI40200': (
        lambda m: _export(
            m,
            Conceptos=[
                replace(
                    _export(m).Conceptos[0],
                    Parte=[
                        Parte(
                            ClaveProdServ='01010101',
                            Cantidad=D('1'),
                            Descripcion='Pieza',
                            InformacionAduanera=[
                                ParteInformacionAduanera(NumeroPedimento='25  01  3173  5000001')
                            ],
                        )
                    ],
                )
            ],
        ),
        f'{CONCEPTO}/cfdi:Parte/cfdi:InformacionAduanera',
        'NumeroPedimento',
    ),
    'CFDI40222': (lambda m: _export(m, Exportacion='01'), DOC, 'Exportacion'),
}


def test_every_us2_rule_has_a_case() -> None:
    assert set(CASES_US2) == _contract_codes('US2')


@pytest.mark.parametrize('code', sorted(CASES_US2))
def test_a_document_that_breaks_a_us2_rule_is_reported(
    code: str, make_invoice: MakeInvoice
) -> None:
    build, node, attribute = CASES_US2[code]
    found = [v for v in validate(build(make_invoice)) if v.rule == code]
    assert found, f'{code} not reported'
    assert (found[0].node, found[0].attribute) == (node, attribute)


def test_the_export_invoice_breaks_no_us2_rule(make_invoice: MakeInvoice) -> None:
    assert validate(_export(make_invoice)) == []
