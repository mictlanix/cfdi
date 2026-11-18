"""Comercio Exterior 2.0 on an export invoice."""

from collections.abc import Callable
from decimal import Decimal

from mictlanix.cfdi import (
    Comprobante,
    Concepto,
    ConceptoImpuestos,
    ConceptoTraslado,
    Receptor,
    comercioexterior20,
    validate,
)

D = Decimal
MakeInvoice = Callable[..., Comprobante]
Check = Callable[[Comprobante], str]
CCE = '/cfdi:Comprobante/cfdi:Complemento/cce20:ComercioExterior'


def comercio_exterior() -> comercioexterior20.ComercioExterior:
    return comercioexterior20.ComercioExterior(
        ClaveDePedimento='A1',
        CertificadoOrigen=0,
        TipoCambioUSD=D('17.5'),
        TotalUSD=D('100.00'),
        Emisor=comercioexterior20.Emisor(
            Domicilio=comercioexterior20.EmisorDomicilio(
                Calle='Principal', Estado='HID', Pais='MEX', CodigoPostal='42501'
            )
        ),
        Receptor=comercioexterior20.Receptor(
            Domicilio=comercioexterior20.ReceptorDomicilio(
                Calle='Main St', Estado='CA', Pais='USA', CodigoPostal='90210'
            )
        ),
        Mercancias=[
            comercioexterior20.Mercancia(NoIdentificacion='SKU-1', ValorDolares=D('100.00'))
        ],
    )


def export(make_invoice: MakeInvoice, **changes: object) -> Comprobante:
    values: dict[str, object] = {
        'totals': False,
        'Exportacion': '02',
        'Moneda': 'USD',
        'TipoCambio': D('17.5'),
        'Receptor': Receptor(
            Rfc='XEXX010101000',
            Nombre='FOREIGN BUYER',
            DomicilioFiscalReceptor='42501',
            ResidenciaFiscal='USA',
            NumRegIdTrib='123456789',
            RegimenFiscalReceptor='616',
            UsoCFDI='S01',
        ),
        'Conceptos': [
            Concepto(
                ClaveProdServ='01010101',
                NoIdentificacion='SKU-1',
                Cantidad=D('1'),
                ClaveUnidad='H87',
                Descripcion='Mercancia',
                ValorUnitario=D('100.00'),
                Importe=D('100.00'),
                ObjetoImp='02',
                Impuestos=ConceptoImpuestos(
                    Traslados=[
                        ConceptoTraslado(
                            Base=D('100.00'),
                            Impuesto='002',
                            TipoFactor='Tasa',
                            TasaOCuota=D('0.000000'),
                            Importe=D('0.00'),
                        )
                    ]
                ),
            )
        ],
        'Complemento': [comercio_exterior()],
    }
    values.update(changes)
    return make_invoice(**values)


def test_an_export_invoice(make_invoice: MakeInvoice, builds_validates_seals: Check) -> None:
    assert '|2.0|A1|0|17.5|100.00|' in builds_validates_seals(export(make_invoice))


def test_comercio_exterior_is_not_allowed_on_an_expense_document(make_invoice: MakeInvoice) -> None:
    found = [
        v.node
        for v in validate(export(make_invoice, TipoDeComprobante='E'))
        if v.rule == 'complement-document-type'
    ]
    assert found == [CCE]
