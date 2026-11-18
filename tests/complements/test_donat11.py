"""Donatarias 1.1 (document level), built, validated and sealed."""

from collections.abc import Callable
from datetime import date

from mictlanix.cfdi import Comprobante, donat11

MakeInvoice = Callable[..., Comprobante]
Check = Callable[[Comprobante], str]


def complement() -> donat11.Donatarias:
    return donat11.Donatarias(
        noAutorizacion='325-SAT-09-I-A-19181',
        fechaAutorizacion=date(2019, 1, 1),
        leyenda=(
            'Este comprobante ampara un donativo, el cual será destinado por la donataria '
            'a los fines propios de su objeto social.'
        ),
    )


def test_a_document_carrying_it(make_invoice: MakeInvoice, builds_validates_seals: Check) -> None:
    cadena = builds_validates_seals(make_invoice(totals=False, Complemento=[complement()]))
    assert '|1.1|325-SAT-09-I-A-19181|2019-01-01|' in cadena
