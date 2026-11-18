"""Impuestos Locales 1.0 on an invoice."""

from collections.abc import Callable
from decimal import Decimal

from mictlanix.cfdi import Comprobante, compute, implocal10

D = Decimal
MakeInvoice = Callable[..., Comprobante]
Check = Callable[[Comprobante], str]


def impuestos_locales() -> implocal10.ImpuestosLocales:
    return implocal10.ImpuestosLocales(
        TotaldeRetenciones=D('2.00'),
        TotaldeTraslados=D('3.00'),
        RetencionesLocales=[
            implocal10.RetencionesLocales(
                ImpLocRetenido='ISN', TasadeRetencion=D('2.00'), Importe=D('2.00')
            )
        ],
        TrasladosLocales=[
            implocal10.TrasladosLocales(
                ImpLocTrasladado='ISH', TasadeTraslado=D('3.00'), Importe=D('3.00')
            )
        ],
    )


def test_an_invoice_with_local_taxes(
    make_invoice: MakeInvoice, builds_validates_seals: Check
) -> None:
    document = make_invoice(totals=False, Complemento=[impuestos_locales()])
    assert compute(document).Total == D('117.00')
    cadena = builds_validates_seals(document)
    assert '|1.0|2.00|3.00|ISN|2.00|2.00|ISH|3.00|3.00|' in cadena
