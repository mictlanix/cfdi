"""Carta Porte 3.1 on transfer (T) and income (I) documents."""

from collections.abc import Callable
from datetime import datetime
from decimal import Decimal

from mictlanix.cfdi import (
    Comprobante,
    Concepto,
    ConceptoImpuestos,
    ConceptoTraslado,
    Receptor,
    cartaporte31,
    validate,
)

D = Decimal
MakeInvoice = Callable[..., Comprobante]
Check = Callable[[Comprobante], str]
CARTA_PORTE = '/cfdi:Comprobante/cfdi:Complemento/cartaporte31:CartaPorte'


def carta_porte() -> cartaporte31.CartaPorte:
    domicilio = cartaporte31.UbicacionDomicilio
    return cartaporte31.CartaPorte(
        IdCCP='CCC5D24E-0D1F-4A5B-8C9D-0E1F2A3B4C5D',
        TranspInternac='No',
        TotalDistRec=D('120'),
        Ubicaciones=[
            cartaporte31.Ubicacion(
                TipoUbicacion='Origen',
                IDUbicacion='OR000001',
                RFCRemitenteDestinatario='EKU9003173C9',
                FechaHoraSalidaLlegada=datetime(2026, 11, 17, 8, 0, 0),
                Domicilio=domicilio(Estado='HID', Pais='MEX', CodigoPostal='42501'),
            ),
            cartaporte31.Ubicacion(
                TipoUbicacion='Destino',
                IDUbicacion='DE000001',
                RFCRemitenteDestinatario='URE180429TM6',
                FechaHoraSalidaLlegada=datetime(2026, 11, 17, 11, 0, 0),
                DistanciaRecorrida=D('120'),
                Domicilio=domicilio(Estado='HID', Pais='MEX', CodigoPostal='42000'),
            ),
        ],
        Mercancias=cartaporte31.Mercancias(
            PesoBrutoTotal=D('100.000'),
            UnidadPeso='KGM',
            NumTotalMercancias=1,
            Mercancia=[
                cartaporte31.Mercancia(
                    BienesTransp='10101500',
                    Descripcion='Animales vivos de granja',
                    Cantidad=D('1'),
                    ClaveUnidad='H87',
                    PesoEnKg=D('100.000'),
                )
            ],
            Autotransporte=cartaporte31.Autotransporte(
                PermSCT='TPAF01',
                NumPermisoSCT='0X1234567',
                IdentificacionVehicular=cartaporte31.IdentificacionVehicular(
                    ConfigVehicular='C2',
                    PesoBrutoVehicular=D('12.00'),
                    PlacaVM='ABC1234',
                    AnioModeloVM=2020,
                ),
                Seguros=cartaporte31.Seguros(
                    AseguraRespCivil='ASEGURADORA', PolizaRespCivil='POL-1'
                ),
            ),
        ),
        FiguraTransporte=[
            cartaporte31.TiposFigura(
                TipoFigura='01',
                RFCFigura='CACX7605101P8',
                NumLicencia='LIC000001',
                NombreFigura='XOCHILT CASAS CHAVEZ',
            )
        ],
    )


def transfer(make_invoice: MakeInvoice, **changes: object) -> Comprobante:
    invoice = make_invoice(totals=False)
    values: dict[str, object] = {
        'totals': False,
        'TipoDeComprobante': 'T',
        'Moneda': 'XXX',
        'FormaPago': None,
        'MetodoPago': None,
        'Receptor': Receptor(
            Rfc=invoice.Emisor.Rfc,
            Nombre=invoice.Emisor.Nombre,
            DomicilioFiscalReceptor='42501',
            RegimenFiscalReceptor='601',
            UsoCFDI='S01',
        ),
        'Conceptos': [
            Concepto(
                ClaveProdServ='10101500',
                Cantidad=D('1'),
                ClaveUnidad='H87',
                Descripcion='Animales vivos de granja',
                ValorUnitario=D('0'),
                Importe=D('0'),
                ObjetoImp='01',
            )
        ],
        'Complemento': [carta_porte()],
    }
    values.update(changes)
    return make_invoice(**values)


def test_a_transfer_document_with_carta_porte(
    make_invoice: MakeInvoice, builds_validates_seals: Check
) -> None:
    cadena = builds_validates_seals(transfer(make_invoice))
    assert '|3.1|CCC5D24E-0D1F-4A5B-8C9D-0E1F2A3B4C5D|No|' in cadena


def test_an_income_document_with_carta_porte(
    make_invoice: MakeInvoice, builds_validates_seals: Check
) -> None:
    flete = Concepto(
        ClaveProdServ='78101800',
        Cantidad=D('1'),
        ClaveUnidad='E48',
        Descripcion='Flete',
        ValorUnitario=D('1000.00'),
        Importe=D('1000.00'),
        ObjetoImp='02',
        Impuestos=ConceptoImpuestos(
            Traslados=[
                ConceptoTraslado(
                    Base=D('1000.00'),
                    Impuesto='002',
                    TipoFactor='Tasa',
                    TasaOCuota=D('0.160000'),
                    Importe=D('160.00'),
                )
            ]
        ),
    )
    document = make_invoice(totals=False, Conceptos=[flete], Complemento=[carta_porte()])
    assert '|3.1|' in builds_validates_seals(document)


def test_carta_porte_is_not_allowed_on_an_expense_document(make_invoice: MakeInvoice) -> None:
    document = make_invoice(totals=False, TipoDeComprobante='E', Complemento=[carta_porte()])
    found = [v.node for v in validate(document) if v.rule == 'complement-document-type']
    assert found == [CARTA_PORTE]
