"""Reading sealed and stamped CFDI 4.0 documents."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from lxml import etree

from mictlanix.cfdi import _sat, tfd11
from mictlanix.cfdi._errors import NotStampedError
from mictlanix.cfdi._xml import CFDI40, deserialize, parse_document
from mictlanix.cfdi.cfdi40 import Comprobante

CADENA_TFD = _sat.SAT_BASE + 'cfd/TimbreFiscalDigital/cadenaoriginal_TFD_1_1.xslt'
VERIFICATION_URL = 'https://verificacfdi.facturaelectronica.sat.gob.mx/default.aspx'


@dataclass(frozen=True)
class QrData:
    """The data of the SAT verification QR; ``url`` is the full verification address."""

    url: str
    UUID: str
    RfcEmisor: str
    RfcReceptor: str
    Total: Decimal
    SelloUltimos8: str


def read(xml: bytes) -> Comprobante:
    """A CFDI 4.0 document, sealed or stamped, as models.

    Complements the library models become typed objects; other elements under ``Complemento``,
    ``ComplementoConcepto`` and ``Addenda`` become ``RawXml``. Does not validate and does not
    verify seals. Raises ``NotCfdi40Error``, or ``ParseError`` when the input is not well-formed
    or cannot be turned into the models.
    """
    return deserialize(Comprobante, parse_document(xml))


def timbre(comprobante: Comprobante) -> tfd11.TimbreFiscalDigital:
    """The document's TimbreFiscalDigital 1.1. Raises ``NotStampedError``."""
    for item in comprobante.Complemento:
        if isinstance(item, tfd11.TimbreFiscalDigital):
            return item
    raise NotStampedError()


def tfd_original_string(xml: bytes) -> str:
    """The TFD's original string, by the SAT's ``cadenaoriginal_TFD_1_1.xslt``.

    Raises ``ParseError``, ``NotCfdi40Error`` or ``NotStampedError``.
    """
    root = parse_document(xml)
    stamp = root.find(f'{{{CFDI40}}}Complemento/{{{tfd11.NAMESPACE}}}TimbreFiscalDigital')
    if stamp is None:
        raise NotStampedError()
    alone = etree.fromstring(etree.tostring(stamp, with_tail=False))
    return str(_sat.stylesheet(CADENA_TFD)(alone))


def _qr_total(total: Decimal) -> str:
    """The total without non-significant zeros, keeping one decimal (research.md R9)."""
    whole, _, decimals = format(total, 'f').partition('.')
    return f'{whole.lstrip("0") or "0"}.{decimals.rstrip("0") or "0"}'


def qr_data(comprobante: Comprobante) -> QrData:
    """The data for the SAT verification QR of a stamped document.

    Raises ``NotStampedError`` if the document has no TimbreFiscalDigital, no ``Sello`` or no
    ``Total``.
    """
    stamp = timbre(comprobante)
    if comprobante.Sello is None or comprobante.Total is None:
        raise NotStampedError('a stamped document needs Sello and Total')
    last8 = comprobante.Sello[-8:]
    emisor, receptor = comprobante.Emisor.Rfc, comprobante.Receptor.Rfc
    url = (
        f'{VERIFICATION_URL}?id={stamp.UUID}&re={emisor}&rr={receptor}'
        f'&tt={_qr_total(comprobante.Total)}&fe={last8}'
    )
    return QrData(
        url=url,
        UUID=stamp.UUID,
        RfcEmisor=emisor,
        RfcReceptor=receptor,
        Total=comprobante.Total,
        SelloUltimos8=last8,
    )
