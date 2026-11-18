"""A transfer document (type T) without complements."""

from collections.abc import Callable
from decimal import Decimal

from mictlanix.cfdi import Comprobante, Concepto, Receptor, compute

D = Decimal
MakeInvoice = Callable[..., Comprobante]
Check = Callable[[Comprobante], str]


def test_a_transfer_document(make_invoice: MakeInvoice, builds_validates_seals: Check) -> None:
    invoice = make_invoice(totals=False)
    document = make_invoice(
        totals=False,
        TipoDeComprobante='T',
        Moneda='XXX',
        FormaPago=None,
        MetodoPago=None,
        Receptor=Receptor(
            Rfc=invoice.Emisor.Rfc,
            Nombre=invoice.Emisor.Nombre,
            DomicilioFiscalReceptor='42501',
            RegimenFiscalReceptor='601',
            UsoCFDI='S01',
        ),
        Conceptos=[
            Concepto(
                ClaveProdServ='01010101',
                Cantidad=D('1'),
                ClaveUnidad='H87',
                Descripcion='Mercancia',
                ValorUnitario=D('0'),
                Importe=D('0'),
                ObjetoImp='01',
            )
        ],
    )
    computed = compute(document)
    assert computed.SubTotal == 0 and computed.Total == 0 and computed.Impuestos is None
    assert '|0|XXX|0|T|01|42501|' in builds_validates_seals(document)
