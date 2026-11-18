"""Estado de Cuenta de Combustibles 1.2 (document level), built, validated and sealed."""

from collections.abc import Callable
from datetime import datetime
from decimal import Decimal as D

from mictlanix.cfdi import Comprobante, ecc12

MakeInvoice = Callable[..., Comprobante]
Check = Callable[[Comprobante], str]


def complement() -> ecc12.EstadoDeCuentaCombustible:
    return ecc12.EstadoDeCuentaCombustible(
        NumeroDeCuenta='1234',
        SubTotal=D('200.00'),
        Total=D('232.00'),
        Conceptos=[
            ecc12.ConceptoEstadoDeCuentaCombustible(
                Identificador='1',
                Fecha=datetime(2026, 11, 10, 8, 0, 0),
                Rfc='EKU9003173C9',
                ClaveEstacion='1234',
                Cantidad=D('10.000'),
                TipoCombustible='1',
                NombreCombustible='Gasolina',
                FolioOperacion='F1',
                ValorUnitario=D('20.00'),
                Importe=D('200.00'),
                Traslados=[
                    ecc12.Traslado(Impuesto='IVA', TasaOCuota=D('0.160000'), Importe=D('32.00'))
                ],
            )
        ],
    )


def test_a_document_carrying_it(make_invoice: MakeInvoice, builds_validates_seals: Check) -> None:
    cadena = builds_validates_seals(make_invoice(totals=False, Complemento=[complement()]))
    assert '|1.2|Tarjeta|1234|200.00|232.00|' in cadena


def test_it_is_allowed_only_on_income_documents(make_invoice: MakeInvoice) -> None:
    from mictlanix.cfdi import validate

    document = make_invoice(totals=False, TipoDeComprobante='E', Complemento=[complement()])
    found = [v.node for v in validate(document) if v.rule == 'complement-document-type']
    assert found == ['/cfdi:Comprobante/cfdi:Complemento/ecc12:EstadoDeCuentaCombustible']
