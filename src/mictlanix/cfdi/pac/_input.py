"""The input checks every PAC client applies: a sealed CFDI 4.0 the library can read."""

from __future__ import annotations

import hashlib
from typing import NoReturn

from lxml import etree

from mictlanix.cfdi import tfd11
from mictlanix.cfdi._errors import CfdiError
from mictlanix.cfdi._read import read
from mictlanix.cfdi._xml import CFDI40, parse_document
from mictlanix.cfdi.cfdi40 import Comprobante
from mictlanix.cfdi.pac._errors import PacRejected


def reject(code: str, message: str) -> NoReturn:
    raise PacRejected(code, message) from None


class Sealed:
    """A sealed document that passed the input checks."""

    def __init__(self, root: etree._Element, seal: str, comprobante: Comprobante) -> None:
        self.root = root
        self.seal = seal
        self.comprobante = comprobante
        self.key = 'seal:' + hashlib.sha256(seal.encode('utf-8')).hexdigest()

    def has_timbre(self) -> bool:
        path = f'{{{CFDI40}}}Complemento/{{{tfd11.NAMESPACE}}}TimbreFiscalDigital'
        return self.root.find(path) is not None


def check(sealed_xml: object) -> Sealed:
    """The input checks of research.md R11, steps 1 to 3."""
    if not isinstance(sealed_xml, bytes):
        reject('301', 'the input is not XML bytes')
    try:
        root = parse_document(sealed_xml)
    except CfdiError:
        reject('301', 'the input is not a well-formed CFDI 4.0 document')
    seal = root.get('Sello')
    if seal is None or not seal.strip():
        reject('302', 'the document is not sealed')
    try:
        comprobante = read(sealed_xml)
    except CfdiError:
        reject('301', 'the document cannot be read')
    if comprobante.Total is None:
        reject('301', 'the document has no Total')
    return Sealed(root, seal, comprobante)
