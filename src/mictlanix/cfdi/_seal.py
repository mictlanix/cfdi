"""Original strings and sealing."""

from __future__ import annotations

import base64
from dataclasses import replace
from typing import TYPE_CHECKING

from mictlanix.cfdi import _sat
from mictlanix.cfdi._compute import compute
from mictlanix.cfdi._errors import CertificateValidityError, ValidationError
from mictlanix.cfdi._validate import validate
from mictlanix.cfdi._xml import parse_document, to_xml

if TYPE_CHECKING:
    from mictlanix.cfdi._csd import CSD
    from mictlanix.cfdi.cfdi40 import Comprobante

CADENA_ORIGINAL = _sat.SAT_BASE + 'cfd/4/cadenaoriginal_4_0/cadenaoriginal_4_0.xslt'


def original_string(xml: bytes) -> str:
    """The original string of a CFDI 4.0 document, by the SAT's ``cadenaoriginal_4_0.xslt``.

    Raises ``ParseError`` or ``NotCfdi40Error``.
    """
    root = parse_document(xml)
    return str(_sat.stylesheet(CADENA_ORIGINAL)(root))


def seal(comprobante: Comprobante, csd: CSD) -> bytes:
    """The sealed document as XML, ready for a PAC.

    Computes the derived values, sets ``NoCertificado`` and ``Certificado``, validates, checks
    that ``Fecha`` is inside the certificate's validity period, and signs the original string
    with RSA-SHA256. Raises ``ValidationError`` (nothing is signed), ``CertificateValidityError``
    or ``ParseError``.
    """
    document = replace(
        compute(comprobante),
        Sello=None,
        NoCertificado=csd.NoCertificado,
        Certificado=base64.b64encode(csd.certificate_der()).decode('ascii'),
    )
    violations = validate(document)
    if violations:
        raise ValidationError(violations)
    if not csd.valid_from <= document.Fecha <= csd.valid_to:
        raise CertificateValidityError(document.Fecha, csd.valid_from, csd.valid_to)
    signature = csd.sign(original_string(to_xml(document)).encode('utf-8'))
    return to_xml(replace(document, Sello=base64.b64encode(signature).decode('ascii')))
