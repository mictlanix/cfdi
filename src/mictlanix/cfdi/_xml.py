"""The generic mapper between the models and XML.

Every model is a frozen dataclass. Its ``__xml__`` class attribute names its element, and each
field carries metadata saying how it maps to XML: an attribute, a child element (optionally
inside a wrapper element that is not modelled), an element holding only text, the element's
own text, or the open content of ``Complemento``, ``ComplementoConcepto`` and ``Addenda``.
Field names are the SAT's exact names. Field order is the XSD's order, which is the order
children are written.
"""

from __future__ import annotations

import dataclasses
import re
import sys
from dataclasses import MISSING, dataclass
from datetime import date, datetime, time
from decimal import Decimal
from typing import TYPE_CHECKING, Any, ClassVar, Literal

from lxml import etree

from mictlanix.cfdi._errors import NotCfdi40Error, ParseError, ValidationError, Violation

if TYPE_CHECKING:
    from mictlanix.cfdi.cfdi40 import Comprobante

Simple = Literal['str', 'decimal', 'datetime', 'date', 'time', 'int', 'bool']
Kind = Literal['attribute', 'child', 'text_child', 'text', 'any']
Accepts = Literal['document', 'concept', 'raw']

XML_INVALID_CHARACTER = 'xml-invalid-character'
COMPLEMENT_NOT_MODELLED = 'complement-not-modelled'
DATETIME_NOT_NAIVE = 'datetime-not-naive'

_KEY = 'mictlanix.cfdi.xml'
XSI = 'http://www.w3.org/2001/XMLSchema-instance'
CFDI40 = 'http://www.sat.gob.mx/cfd/4'


@dataclass(frozen=True)
class XmlClass:
    """How a model class maps to its element."""

    name: str
    namespace: str
    prefix: str
    fixed: tuple[tuple[str, str], ...] = ()
    schema_location: str | None = None


@dataclass(frozen=True)
class XmlField:
    kind: Kind
    simple: Simple = 'str'
    cls: str | None = None
    many: bool = False
    wrapper: str | None = None
    wrapper_optional: bool = True
    accepts: Accepts | None = None


@dataclass(frozen=True)
class RawXml:
    """One XML element kept as bytes: an addenda, or a complement the library does not model."""

    xml: bytes


class DocumentComplement:
    """Base of every complement that sits under ``Comprobante/Complemento``."""

    __xml__: ClassVar[XmlClass]


class ConceptComplement:
    """Base of every complement that sits under ``Concepto/ComplementoConcepto``."""

    __xml__: ClassVar[XmlClass]


_REGISTRY: dict[tuple[str, str], type[Any]] = {}


def register[T](cls: type[T]) -> type[T]:
    """Make a complement's root class known to the reader."""
    info: XmlClass = cls.__xml__  # type: ignore[attr-defined]
    _REGISTRY[(info.namespace, info.name)] = cls
    return cls


def registered(namespace: str, name: str) -> type[Any] | None:
    return _REGISTRY.get((namespace, name))


def _field(info: XmlField, default: Any) -> Any:
    metadata = {_KEY: info}
    if info.many or info.kind == 'any':
        if default is MISSING:
            return dataclasses.field(metadata=metadata)
        return dataclasses.field(default_factory=list, metadata=metadata)
    if default is MISSING:
        return dataclasses.field(metadata=metadata)
    return dataclasses.field(default=default, metadata=metadata)


def attr(simple: Simple = 'str', *, default: Any = MISSING) -> Any:
    """An XML attribute named like the field."""
    return _field(XmlField('attribute', simple=simple), default)


def text(simple: Simple = 'str') -> Any:
    """The element's own text content."""
    return _field(XmlField('text', simple=simple), MISSING)


def text_child(simple: Simple = 'str', *, many: bool = False, default: Any = MISSING) -> Any:
    """A child element, named like the field, that holds only text."""
    return _field(XmlField('text_child', simple=simple, many=many), default)


def child(
    cls: str,
    *,
    many: bool = False,
    wrapper: str | None = None,
    wrapper_optional: bool = True,
    default: Any = MISSING,
) -> Any:
    """A child element modelled by the class named ``cls``.

    With ``wrapper``, the children sit inside a wrapper element of that name, which has no
    model of its own; the field is named like the wrapper.
    """
    info = XmlField('child', cls=cls, many=many, wrapper=wrapper, wrapper_optional=wrapper_optional)
    return _field(info, default)


def any_children(wrapper: str, accepts: Accepts) -> Any:
    """The open content of a wrapper element: complements, or raw XML for an addenda."""
    return _field(XmlField('any', wrapper=wrapper, accepts=accepts), None)


# Values -------------------------------------------------------------------------------------

_INVALID_CHARACTER = re.compile('[^\t\n\r\x20-퟿-�\U00010000-\U0010ffff]')
_DECIMAL = re.compile(r'[+-]?(\d+(\.\d*)?|\.\d+)')
_INTEGER = re.compile(r'[+-]?\d+')
_DATETIME = re.compile(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?')
_DATE = re.compile(r'\d{4}-\d{2}-\d{2}')
_TIME = re.compile(r'\d{2}:\d{2}:\d{2}(\.\d+)?')


class _Unwritable(Exception):
    def __init__(self, rule: str, message: str) -> None:
        self.rule = rule
        self.message = message
        super().__init__(message)


def _to_text(value: Any, simple: Simple) -> str:
    if simple == 'str':
        text_value = str(value)
        if _INVALID_CHARACTER.search(text_value):
            raise _Unwritable(XML_INVALID_CHARACTER, 'contains a character XML 1.0 does not allow')
        return text_value
    if simple == 'decimal':
        return format(value, 'f')
    if simple in ('datetime', 'time'):
        if value.utcoffset() is not None:
            raise _Unwritable(DATETIME_NOT_NAIVE, 'carries a time zone; the SAT format has none')
        return str(value.isoformat())
    if simple == 'date':
        return str(value.isoformat())
    if simple == 'bool':
        return 'true' if value else 'false'
    return str(int(value))


def _from_text(raw: str, simple: Simple) -> Any:
    if simple == 'str':
        return raw
    value = raw.strip()
    if simple == 'decimal' and _DECIMAL.fullmatch(value):
        return Decimal(value)
    if simple == 'int' and _INTEGER.fullmatch(value):
        return int(value)
    if simple == 'datetime' and _DATETIME.fullmatch(value):
        return datetime.fromisoformat(value)
    if simple == 'date' and _DATE.fullmatch(value):
        return date.fromisoformat(value)
    if simple == 'time' and _TIME.fullmatch(value):
        return time.fromisoformat(value)
    if simple == 'bool' and value in ('true', 'false', '1', '0'):
        return value in ('true', '1')
    raise ValueError(f'{raw!r} is not a valid {simple}')


# Helpers ------------------------------------------------------------------------------------


def _q(namespace: str, name: str) -> str:
    return f'{{{namespace}}}{name}'


def _info(obj_or_cls: Any) -> XmlClass:
    info: XmlClass = obj_or_cls.__xml__
    return info


_FIELDS: dict[type[Any], list[tuple[str, XmlField, bool]]] = {}


def _fields(cls: type[Any]) -> list[tuple[str, XmlField, bool]]:
    """(name, mapping, required) for every mapped field, in declaration order."""
    cached = _FIELDS.get(cls)
    if cached is None:
        cached = []
        for f in dataclasses.fields(cls):
            info = f.metadata.get(_KEY)
            if info is None:
                continue
            required = f.default is MISSING and f.default_factory is MISSING
            cached.append((f.name, info, required))
        _FIELDS[cls] = cached
    return cached


def _resolve(owner: type[Any], name: str) -> type[Any]:
    found: type[Any] = vars(sys.modules[owner.__module__])[name]
    return found


def _path(element: etree._Element) -> str:
    return str(element.getroottree().getpath(element))


def _safe_parser() -> etree.XMLParser:
    return etree.XMLParser(no_network=True, resolve_entities=False, load_dtd=False)


def parse_xml(xml: bytes, what: str = 'XML') -> etree._Element:
    """Parse input XML without touching the network. Raises ``ParseError``."""
    try:
        return etree.fromstring(xml, _safe_parser())
    except etree.XMLSyntaxError as error:
        line, column = error.position
        raise ParseError(
            f'{what} is not well-formed: {error.msg}', line=line, column=column
        ) from None


def parse_document(xml: bytes) -> etree._Element:
    """Parse a CFDI 4.0 document. Raises ``ParseError`` or ``NotCfdi40Error``."""
    root = parse_xml(xml)
    version = root.get('Version')
    if root.tag != _q(CFDI40, 'Comprobante') or version != '4.0':
        raise NotCfdi40Error(root=str(root.tag), version=version)
    return root


def _parse_raw(raw: RawXml) -> etree._Element:
    return parse_xml(raw.xml, 'raw XML, which must be one element,')


# Writing ------------------------------------------------------------------------------------

_Problem = tuple[etree._Element, str | None, str, str]


def _collect_namespaces(obj: Any, found: dict[str, str]) -> None:
    info = _info(obj)
    found.setdefault(info.prefix, info.namespace)
    for name, mapping, _ in _fields(type(obj)):
        if mapping.kind not in ('child', 'any'):
            continue
        value = getattr(obj, name)
        items = value if isinstance(value, list) else [] if value is None else [value]
        for item in items:
            if not isinstance(item, RawXml):
                _collect_namespaces(item, found)


def serialize(
    obj: Any, extra_namespaces: dict[str, str] | None = None
) -> tuple[etree._Element, list[Violation]]:
    """Build the element tree of a model.

    Values XML cannot carry are left out and reported as violations; everything else is
    written. Raises ``ParseError`` if a ``RawXml`` is not one well-formed element.
    """
    namespaces: dict[str, str] = {}
    _collect_namespaces(obj, namespaces)
    for prefix, namespace in (extra_namespaces or {}).items():
        namespaces.setdefault(prefix, namespace)
    info = _info(obj)
    root = etree.Element(_q(info.namespace, info.name), nsmap=namespaces)
    problems: list[_Problem] = []
    _write(obj, root, problems)
    violations = [
        Violation(node=_path(element), attribute=attribute, rule=rule, message=message)
        for element, attribute, rule, message in problems
    ]
    return root, violations


def _write_text(
    target: etree._Element,
    value: Any,
    simple: Simple,
    problems: list[_Problem],
    attribute: str | None = None,
) -> None:
    try:
        text_value = _to_text(value, simple)
    except _Unwritable as error:
        problems.append((target, attribute, error.rule, error.message))
        return
    if attribute is None:
        target.text = text_value
    else:
        target.set(attribute, text_value)


def _write(obj: Any, element: etree._Element, problems: list[_Problem]) -> None:
    info = _info(obj)
    for attribute, fixed_value in info.fixed:
        element.set(attribute, fixed_value)
    for name, mapping, _ in _fields(type(obj)):
        value = getattr(obj, name)
        if mapping.kind == 'attribute':
            if value is not None:
                _write_text(element, value, mapping.simple, problems, attribute=name)
        elif mapping.kind == 'text':
            _write_text(element, value, mapping.simple, problems)
        elif mapping.kind == 'text_child':
            values = value if mapping.many else [] if value is None else [value]
            for item in values:
                sub = etree.SubElement(element, _q(info.namespace, name))
                _write_text(sub, item, mapping.simple, problems)
        elif mapping.kind == 'child':
            items = value if mapping.many else [] if value is None else [value]
            parent = element
            if mapping.wrapper is not None:
                if not items and mapping.wrapper_optional:
                    continue
                parent = etree.SubElement(element, _q(info.namespace, mapping.wrapper))
            for item in items:
                item_info = _info(item)
                sub = etree.SubElement(parent, _q(item_info.namespace, item_info.name))
                _write(item, sub, problems)
        elif mapping.kind == 'any' and value:
            assert mapping.wrapper is not None
            parent = etree.SubElement(element, _q(info.namespace, mapping.wrapper))
            for item in value:
                if isinstance(item, RawXml):
                    parent.append(_parse_raw(item))
                else:
                    item_info = _info(item)
                    sub = etree.SubElement(parent, _q(item_info.namespace, item_info.name))
                    _write(item, sub, problems)


# Reading ------------------------------------------------------------------------------------


def _children(element: etree._Element, tag: str) -> list[etree._Element]:
    return [child_element for child_element in element if child_element.tag == tag]


def _read_value(element: etree._Element, raw: str, simple: Simple, attribute: str | None) -> Any:
    try:
        return _from_text(raw, simple)
    except ValueError as error:
        raise ParseError(str(error), node=_path(element), attribute=attribute) from None


def _missing(element: etree._Element, what: str, attribute: str | None = None) -> ParseError:
    return ParseError(f'required {what} is missing', node=_path(element), attribute=attribute)


def deserialize[T](cls: type[T], element: etree._Element) -> T:
    """Build a model from its element. Raises ``ParseError`` naming the node and attribute."""
    info = _info(cls)
    for attribute, fixed_value in info.fixed:
        if element.get(attribute) != fixed_value:
            raise ParseError(
                f'{attribute} must be {fixed_value}', node=_path(element), attribute=attribute
            )
    values: dict[str, Any] = {}
    for name, mapping, required in _fields(cls):
        if mapping.kind == 'attribute':
            raw = element.get(name)
            if raw is None:
                if required:
                    raise _missing(element, f'attribute {name}', name)
                continue
            values[name] = _read_value(element, raw, mapping.simple, name)
        elif mapping.kind == 'text':
            values[name] = _read_value(element, element.text or '', mapping.simple, None)
        elif mapping.kind == 'text_child':
            found = _children(element, _q(info.namespace, name))
            read = [_read_value(sub, sub.text or '', mapping.simple, None) for sub in found]
            if mapping.many:
                if read or required:
                    values[name] = read
            elif read:
                values[name] = read[0]
            elif required:
                raise _missing(element, f'element {name}')
        elif mapping.kind == 'child':
            assert mapping.cls is not None
            item_cls = _resolve(cls, mapping.cls)
            item_info = _info(item_cls)
            parent: etree._Element | None = element
            if mapping.wrapper is not None:
                wrappers = _children(element, _q(info.namespace, mapping.wrapper))
                parent = wrappers[0] if wrappers else None
            found = (
                [] if parent is None else _children(parent, _q(item_info.namespace, item_info.name))
            )
            items = [deserialize(item_cls, sub) for sub in found]
            if mapping.many:
                if items or required:
                    values[name] = items
            elif items:
                values[name] = items[0]
            elif required:
                raise _missing(element, f'element {item_info.name}')
        elif mapping.kind == 'any':
            assert mapping.wrapper is not None
            wrappers = _children(element, _q(info.namespace, mapping.wrapper))
            values[name] = [] if not wrappers else _read_any(wrappers[0], mapping.accepts)
    return cls(**values)


def _read_any(wrapper: etree._Element, accepts: Accepts | None) -> list[Any]:
    items: list[Any] = []
    for sub in wrapper:
        if not isinstance(sub.tag, str):
            continue
        qname = etree.QName(sub)
        known = registered(qname.namespace or '', qname.localname) if accepts != 'raw' else None
        if known is None:
            items.append(RawXml(etree.tostring(sub, with_tail=False)))
        else:
            items.append(deserialize(known, sub))
    return items


# Documents ----------------------------------------------------------------------------------


def _schema_locations(comprobante: Comprobante) -> str:
    models: list[Any] = [comprobante, *comprobante.Complemento]
    for concepto in comprobante.Conceptos:
        models.extend(concepto.ComplementoConcepto)
    pairs: dict[str, str] = {}
    for model in models:
        if isinstance(model, RawXml):
            continue
        info = _info(model)
        if info.schema_location is not None:
            pairs.setdefault(info.namespace, info.schema_location)
    return ' '.join(f'{namespace} {location}' for namespace, location in pairs.items())


def build(comprobante: Comprobante) -> tuple[etree._Element, list[Violation]]:
    """The element tree of a document, with every value or complement that cannot be emitted.

    Raises ``ParseError`` if a ``RawXml`` is not one well-formed element.
    """
    root, violations = serialize(comprobante, {'xsi': XSI})
    root.set(_q(XSI, 'schemaLocation'), _schema_locations(comprobante))
    namespace = _info(comprobante).namespace
    message = 'holds a complement the library does not model, which cannot be emitted'
    if any(isinstance(item, RawXml) for item in comprobante.Complemento):
        wrapper = root.find(_q(namespace, 'Complemento'))
        assert wrapper is not None
        violations.append(Violation(_path(wrapper), None, COMPLEMENT_NOT_MODELLED, message))
    concept_elements = root.findall(f'{_q(namespace, "Conceptos")}/{_q(namespace, "Concepto")}')
    for concepto, element in zip(comprobante.Conceptos, concept_elements, strict=True):
        if any(isinstance(item, RawXml) for item in concepto.ComplementoConcepto):
            wrapper = element.find(_q(namespace, 'ComplementoConcepto'))
            assert wrapper is not None
            violations.append(Violation(_path(wrapper), None, COMPLEMENT_NOT_MODELLED, message))
    return root, violations


def to_xml(comprobante: Comprobante) -> bytes:
    """The document as CFDI 4.0 XML in UTF-8. Does not compute derived values or validate.

    Raises ``ValidationError`` if a value cannot be written or a complement is not modelled,
    and ``ParseError`` if a ``RawXml`` is not one well-formed element.
    """
    root, violations = build(comprobante)
    if violations:
        raise ValidationError(violations)
    return b'<?xml version="1.0" encoding="UTF-8"?>\n' + etree.tostring(root, encoding='UTF-8')
