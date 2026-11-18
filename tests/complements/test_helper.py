from collections.abc import Callable

from mictlanix.cfdi import Comprobante


def test_the_helper_returns_the_sealed_original_string(
    make_invoice: Callable[..., Comprobante], builds_validates_seals: Callable[[Comprobante], str]
) -> None:
    cadena = builds_validates_seals(make_invoice(totals=False))
    assert cadena.startswith('||4.0|2026-11-17T12:00:00|03|30001000000500003416|100.00|')
