"""Offline access to the SAT's vendored XSDs and XSLTs.

The SAT's files reference each other by absolute URL. A resolver maps every
``http://www.sat.gob.mx/sitio_internet/...`` URL to the copy shipped in this package and
refuses anything else, and parsers never touch the network.
"""

from __future__ import annotations

from functools import cache
from importlib.resources import files
from typing import TYPE_CHECKING

from lxml import etree

if TYPE_CHECKING:
    from lxml.etree._docloader import _InputDocument

SAT_BASE = 'http://www.sat.gob.mx/sitio_internet/'
XS = 'http://www.w3.org/2001/XMLSchema'

_PACKAGE_ROOT = files('mictlanix.cfdi').joinpath('_sat_files', 'sitio_internet')


class SatArtifactError(Exception):
    """A SAT artifact was requested that is not vendored, or a URL outside the SAT."""


def read(url: str) -> bytes:
    """The bytes of the vendored copy of a SAT URL."""
    if not url.startswith(SAT_BASE):
        raise SatArtifactError(f'{url} is outside the SAT and is never fetched')
    target = _PACKAGE_ROOT.joinpath(*url[len(SAT_BASE) :].split('/'))
    if not target.is_file():
        raise SatArtifactError(f'{url} is not vendored in this package')
    return target.read_bytes()


class _Resolver(etree.Resolver):
    def resolve(
        self, system_url: str | None, public_id: str | None, context: object
    ) -> _InputDocument | None:
        if system_url is None:
            return None
        if system_url.startswith(('http://', 'https://')):
            return self.resolve_string(read(system_url), context, base_url=system_url)
        raise SatArtifactError(f'{system_url} is outside the SAT and is never fetched')


def parser() -> etree.XMLParser:
    """A parser that resolves SAT URLs from the package and never uses the network."""
    xml_parser = etree.XMLParser(no_network=True, resolve_entities=False, load_dtd=False)
    xml_parser.resolvers.add(_Resolver())
    return xml_parser


def load(url: str) -> etree._ElementTree:
    """Parse a vendored SAT file, keeping its URL as base for the files it references."""
    root = etree.fromstring(read(url), parser(), base_url=url)
    return root.getroottree()


@cache
def stylesheet(url: str) -> etree.XSLT:
    access = etree.XSLTAccessControl.DENY_ALL
    return etree.XSLT(load(url), access_control=access)


@cache
def _target_namespace(url: str) -> str:
    namespace = load(url).getroot().get('targetNamespace')
    if namespace is None:
        raise SatArtifactError(f'{url} has no targetNamespace')
    return namespace


@cache
def schema(urls: tuple[str, ...]) -> etree.XMLSchema:
    """One compiled schema importing every XSD given, so complements validate together."""
    wrapper = etree.Element(f'{{{XS}}}schema', nsmap={'xs': XS})
    for url in sorted(set(urls)):
        etree.SubElement(
            wrapper,
            f'{{{XS}}}import',
            namespace=_target_namespace(url),
            schemaLocation=url,
        )
    document = etree.fromstring(etree.tostring(wrapper), parser(), base_url=SAT_BASE)
    return etree.XMLSchema(document)
