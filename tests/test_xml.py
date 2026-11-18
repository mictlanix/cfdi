"""The generic mapper, tested with small hand-written models."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from typing import ClassVar

import pytest
from lxml import etree

from mictlanix.cfdi import ParseError
from mictlanix.cfdi._xml import (
    XmlClass,
    attr,
    child,
    deserialize,
    serialize,
    text,
    text_child,
)

NS = 'urn:test'
Q = f'{{{NS}}}'


@dataclass(frozen=True, kw_only=True)
class Medida:
    __xml__: ClassVar[XmlClass] = XmlClass('Medida', NS, 't')
    Unidad: str = attr()
    valor: Decimal = text('decimal')


@dataclass(frozen=True, kw_only=True)
class Linea:
    __xml__: ClassVar[XmlClass] = XmlClass('Linea', NS, 't')
    Clave: str = attr()
    Importe: Decimal = attr('decimal')
    Cantidad: int | None = attr('int', default=None)


@dataclass(frozen=True, kw_only=True)
class Nota:
    __xml__: ClassVar[XmlClass] = XmlClass('Nota', NS, 't')
    Texto: str = attr()


@dataclass(frozen=True, kw_only=True)
class Etiqueta:
    __xml__: ClassVar[XmlClass] = XmlClass('Etiqueta', NS, 't')
    Texto: str = attr()


@dataclass(frozen=True, kw_only=True)
class Raiz:
    __xml__: ClassVar[XmlClass] = XmlClass('Raiz', NS, 't', fixed=(('Version', '9.9'),))
    Fecha: datetime = attr('datetime')
    Dia: date | None = attr('date', default=None)
    Hora: time | None = attr('time', default=None)
    Activo: bool | None = attr('bool', default=None)
    Total: Decimal | None = attr('decimal', default=None)
    Nota: Nota | None = child('Nota', default=None)
    Lineas: list[Linea] = child('Linea', many=True, wrapper='Lineas', wrapper_optional=False)
    Etiqueta: list[Etiqueta] = child('Etiqueta', many=True, default=None)
    Referencia: str | None = text_child('str', default=None)
    Medida: Medida | None = child('Medida', default=None)


def _sample(**changes: object) -> Raiz:
    values: dict[str, object] = {
        'Fecha': datetime(2026, 11, 17, 12, 0, 0),
        'Dia': date(2026, 11, 17),
        'Hora': time(8, 30, 5),
        'Activo': True,
        'Total': Decimal('100.00'),
        'Nota': Nota(Texto='primera'),
        'Lineas': [
            Linea(Clave='A', Importe=Decimal('60.00'), Cantidad=2),
            Linea(Clave='B', Importe=Decimal('40.000000')),
        ],
        'Etiqueta': [Etiqueta(Texto='x'), Etiqueta(Texto='y')],
        'Referencia': 'REF-1',
        'Medida': Medida(Unidad='kg', valor=Decimal('1.5')),
    }
    values.update(changes)
    return Raiz(**values)  # type: ignore[arg-type]


def test_attributes_are_written_with_their_exact_names_and_values() -> None:
    root, violations = serialize(_sample())
    assert violations == []
    assert root.tag == Q + 'Raiz'
    assert root.get('Version') == '9.9'
    assert root.get('Fecha') == '2026-11-17T12:00:00'
    assert root.get('Dia') == '2026-11-17'
    assert root.get('Hora') == '08:30:05'
    assert root.get('Activo') == 'true'
    assert root.get('Total') == '100.00'


def test_decimals_are_written_exactly_as_given() -> None:
    root, _ = serialize(_sample())
    lineas = root.findall(f'{Q}Lineas/{Q}Linea')
    assert [linea.get('Importe') for linea in lineas] == ['60.00', '40.000000']
    assert lineas[0].get('Cantidad') == '2'


def test_optional_fields_left_as_none_are_omitted() -> None:
    root, _ = serialize(_sample(Dia=None, Hora=None, Activo=None, Total=None, Nota=None))
    for name in ('Dia', 'Hora', 'Activo', 'Total'):
        assert root.get(name) is None
    assert root.find(Q + 'Nota') is None
    assert root.findall(f'{Q}Lineas/{Q}Linea')[1].get('Cantidad') is None


def test_children_follow_field_order_and_use_the_namespace_prefix() -> None:
    root, _ = serialize(_sample())
    assert [etree.QName(element).localname for element in root] == [
        'Nota',
        'Lineas',
        'Etiqueta',
        'Etiqueta',
        'Referencia',
        'Medida',
    ]
    assert root.prefix == 't'
    assert all(element.prefix == 't' for element in root.iter())


def test_a_flattened_wrapper_holds_the_repeated_children() -> None:
    root, _ = serialize(_sample())
    wrapper = root.find(Q + 'Lineas')
    assert wrapper is not None and wrapper.attrib == {}
    assert [linea.get('Clave') for linea in wrapper] == ['A', 'B']


def test_a_required_wrapper_is_written_even_when_empty() -> None:
    root, _ = serialize(_sample(Lineas=[]))
    wrapper = root.find(Q + 'Lineas')
    assert wrapper is not None and len(wrapper) == 0


def test_text_content_is_written() -> None:
    root, _ = serialize(_sample())
    assert root.findtext(Q + 'Referencia') == 'REF-1'
    medida = root.find(Q + 'Medida')
    assert medida is not None
    assert (medida.get('Unidad'), medida.text) == ('kg', '1.5')


def test_round_trip_gives_back_an_equal_model() -> None:
    model = _sample()
    root, _ = serialize(model)
    reparsed = etree.fromstring(etree.tostring(root))
    assert deserialize(Raiz, reparsed) == model


def test_a_character_xml_cannot_carry_is_a_violation_naming_the_field() -> None:
    model = _sample(Lineas=[Linea(Clave='A\x00', Importe=Decimal('1'))])
    root, violations = serialize(model)
    assert len(violations) == 1
    violation = violations[0]
    assert violation.rule == 'xml-invalid-character'
    assert violation.node == '/t:Raiz/t:Lineas/t:Linea'
    assert violation.attribute == 'Clave'
    assert root.find(f'{Q}Lineas/{Q}Linea') is not None


def test_a_datetime_with_a_time_zone_is_a_violation_naming_the_field() -> None:
    aware = datetime(2026, 11, 17, 12, 0, 0, tzinfo=timezone(timedelta(hours=-6)))
    root, violations = serialize(_sample(Fecha=aware))
    assert [(v.node, v.attribute, v.rule) for v in violations] == [
        ('/t:Raiz', 'Fecha', 'datetime-not-naive')
    ]
    assert root.get('Fecha') is None


def test_a_missing_required_attribute_is_a_parse_error_naming_it() -> None:
    root, _ = serialize(_sample())
    del root.find(f'{Q}Lineas/{Q}Linea').attrib['Clave']  # type: ignore[union-attr]
    reparsed = etree.fromstring(etree.tostring(root))
    with pytest.raises(ParseError) as caught:
        deserialize(Raiz, reparsed)
    assert caught.value.node == '/t:Raiz/t:Lineas/t:Linea[1]'
    assert caught.value.attribute == 'Clave'


def test_a_value_of_the_wrong_type_is_a_parse_error_naming_it() -> None:
    root, _ = serialize(_sample())
    root.set('Total', 'abc')
    reparsed = etree.fromstring(etree.tostring(root))
    with pytest.raises(ParseError) as caught:
        deserialize(Raiz, reparsed)
    assert (caught.value.node, caught.value.attribute) == ('/t:Raiz', 'Total')
