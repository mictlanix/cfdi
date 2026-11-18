"""Generate the model modules from the vendored SAT XSDs.

Dev-only; never shipped. Each module in ``SCHEMAS`` is generated from one XSD into
``src/mictlanix/cfdi/<module>.py``: frozen, keyword-only dataclasses with the SAT's exact
element and attribute names, mapped to XML by ``mictlanix.cfdi._xml``. The output is passed
through ``ruff format``, and a test fails if a committed module differs from a fresh
generation.

Usage: uv run python tools/generate_models.py [module ...]
"""

from __future__ import annotations

import keyword
import re
import subprocess
import sys
import textwrap
from dataclasses import dataclass, field
from pathlib import Path

from lxml import etree

from mictlanix.cfdi import _sat

ROOT = Path(__file__).resolve().parent.parent
PACKAGE = ROOT / 'src' / 'mictlanix' / 'cfdi'
XS = '{http://www.w3.org/2001/XMLSchema}'
S = _sat.SAT_BASE


class GeneratorError(Exception):
    pass


@dataclass(frozen=True)
class Schema:
    """What to generate from one XSD.

    ``level`` is ``root`` for ``Comprobante``, else where the complement may sit.
    ``clashes`` names the class for an element path whose element name is reused for different
    content in the same schema. ``library_written`` lists the paths of attributes and elements
    the library fills in, which are generated as optional although the XSD requires them.
    """

    xsd: str
    prefix: str
    level: str
    title: str
    clashes: dict[str, str] = field(default_factory=dict)
    library_written: frozenset[str] = frozenset()


SCHEMAS: dict[str, Schema] = {
    'cfdi40': Schema(
        xsd=S + 'cfd/4/cfdv40.xsd',
        prefix='cfdi',
        level='root',
        title='CFDI 4.0',
        clashes={
            'Comprobante/Conceptos/Concepto/Impuestos': 'ConceptoImpuestos',
            'Comprobante/Conceptos/Concepto/Impuestos/Traslados/Traslado': 'ConceptoTraslado',
            'Comprobante/Conceptos/Concepto/Impuestos/Retenciones/Retencion': 'ConceptoRetencion',
            'Comprobante/Conceptos/Concepto/Parte/InformacionAduanera': 'ParteInformacionAduanera',
        },
        library_written=frozenset(
            {
                'Comprobante/@SubTotal',
                'Comprobante/@Total',
                'Comprobante/@Sello',
                'Comprobante/@NoCertificado',
                'Comprobante/@Certificado',
            }
        ),
    ),
    'tfd11': Schema(
        xsd=S + 'cfd/TimbreFiscalDigital/TimbreFiscalDigitalv11.xsd',
        prefix='tfd',
        level='document',
        title='TimbreFiscalDigital 1.1',
    ),
    'pagos20': Schema(
        xsd=S + 'cfd/Pagos/Pagos20.xsd',
        prefix='pago20',
        level='document',
        title='Pagos 2.0',
        library_written=frozenset({'Pagos/Totales'}),
    ),
    'nomina12': Schema(
        xsd=S + 'cfd/nomina/nomina12.xsd',
        prefix='nomina12',
        level='document',
        title='Nómina 1.2',
    ),
    'cartaporte31': Schema(
        xsd=S + 'cfd/CartaPorte/CartaPorte31.xsd',
        prefix='cartaporte31',
        level='document',
        title='Carta Porte 3.1',
        clashes={
            'CartaPorte/Ubicaciones/Ubicacion/Domicilio': 'UbicacionDomicilio',
            'CartaPorte/FiguraTransporte/TiposFigura/Domicilio': 'TiposFiguraDomicilio',
            'CartaPorte/Mercancias/TransporteMaritimo/Contenedor': 'TransporteMaritimoContenedor',
            'CartaPorte/Mercancias/TransporteFerroviario/Carro/Contenedor': 'CarroContenedor',
        },
    ),
    'comercioexterior20': Schema(
        xsd=S + 'cfd/ComercioExterior20/ComercioExterior20.xsd',
        prefix='cce20',
        level='document',
        title='Comercio Exterior 2.0',
        clashes={
            'ComercioExterior/Emisor/Domicilio': 'EmisorDomicilio',
            'ComercioExterior/Receptor/Domicilio': 'ReceptorDomicilio',
            'ComercioExterior/Destinatario/Domicilio': 'DestinatarioDomicilio',
        },
    ),
    'implocal10': Schema(
        xsd=S + 'cfd/implocal/implocal.xsd',
        prefix='implocal',
        level='document',
        title='Impuestos Locales 1.0',
    ),
    'divisas10': Schema(
        xsd=S + 'cfd/divisas/divisas.xsd',
        prefix='divisas',
        level='document',
        title='Divisas 1.0',
    ),
    'donat11': Schema(
        xsd=S + 'cfd/donat/donat11.xsd',
        prefix='donat',
        level='document',
        title='Donatarias 1.1',
    ),
    'leyendasfiscales10': Schema(
        xsd=S + 'cfd/leyendasFiscales/leyendasFisc.xsd',
        prefix='leyendasFisc',
        level='document',
        title='Leyendas Fiscales 1.0',
    ),
    'ine11': Schema(
        xsd=S + 'cfd/ine/ine11.xsd',
        prefix='ine',
        level='document',
        title='INE 1.1',
    ),
    'aerolineas10': Schema(
        xsd=S + 'cfd/aerolineas/aerolineas.xsd',
        prefix='aerolineas',
        level='document',
        title='Aerolíneas 1.0',
    ),
    'detallista': Schema(
        xsd=S + 'cfd/detallista/detallista.xsd',
        prefix='detallista',
        level='document',
        title='Detallista 1.3.1',
        clashes={
            'detallista/AdditionalInformation/referenceIdentification': (
                'AdditionalInformationReferenceIdentification'
            ),
            'detallista/lineItem/AdditionalInformation/referenceIdentification': (
                'LineItemReferenceIdentification'
            ),
            'detallista/InvoiceCreator/alternatePartyIdentification': (
                'InvoiceCreatorAlternatePartyIdentification'
            ),
            'detallista/lineItem/Customs/alternatePartyIdentification': (
                'LineItemCustomsAlternatePartyIdentification'
            ),
            'detallista/InvoiceCreator/nameAndAddress': 'InvoiceCreatorNameAndAddress',
            'detallista/lineItem/Customs/nameAndAddress': 'LineItemCustomsNameAndAddress',
            'detallista/lineItem/Customs': 'LineItemCustoms',
            'detallista/lineItem/allowanceCharge/monetaryAmountOrPercentage': (
                'LineItemMonetaryAmountOrPercentage'
            ),
            'detallista/lineItem/allowanceCharge': 'LineItemAllowanceCharge',
        },
    ),
    'tpe10': Schema(
        xsd=S + 'cfd/TuristaPasajeroExtranjero/TuristaPasajeroExtranjero.xsd',
        prefix='tpe',
        level='document',
        title='Turista Pasajero Extranjero 1.0',
    ),
    'ecc12': Schema(
        xsd=S + 'cfd/EstadoDeCuentaCombustible/ecc12.xsd',
        prefix='ecc12',
        level='document',
        title='Estado de Cuenta de Combustibles 1.2',
    ),
    'consumodecombustibles11': Schema(
        xsd=S + 'cfd/consumodecombustibles/consumodeCombustibles11.xsd',
        prefix='consumodecombustibles11',
        level='document',
        title='Consumo de Combustibles 1.1',
    ),
    'gastoshidrocarburos10': Schema(
        xsd=S + 'cfd/GastosHidrocarburos10/GastosHidrocarburos10.xsd',
        prefix='gceh',
        level='document',
        title='Gastos de Hidrocarburos 1.0',
    ),
    'ingresoshidrocarburos10': Schema(
        xsd=S + 'cfd/IngresosHidrocarburos10/IngresosHidrocarburos.xsd',
        prefix='ieeh',
        level='document',
        title='Ingresos de Hidrocarburos 1.0',
    ),
    'notariospublicos10': Schema(
        xsd=S + 'cfd/notariospublicos/notariospublicos.xsd',
        prefix='notariospublicos',
        level='document',
        title='Notarios Públicos 1.0',
    ),
    'arteantiguedades10': Schema(
        xsd=S + 'cfd/arteantiguedades/obrasarteantiguedades.xsd',
        prefix='obrasarte',
        level='document',
        title='Obras de Arte y Antigüedades 1.0',
    ),
    'pagoenespecie10': Schema(
        xsd=S + 'cfd/pagoenespecie/pagoenespecie.xsd',
        prefix='pagoenespecie',
        level='document',
        title='Pago en Especie 1.0',
    ),
    'valesdedespensa10': Schema(
        xsd=S + 'cfd/valesdedespensa/valesdedespensa.xsd',
        prefix='valesdedespensa',
        level='document',
        title='Vales de Despensa 1.0',
    ),
    'vehiculousado10': Schema(
        xsd=S + 'cfd/vehiculousado/vehiculousado.xsd',
        prefix='vehiculousado',
        level='document',
        title='Vehículo Usado 1.0',
    ),
    'renovacionysustitucionvehiculos10': Schema(
        xsd=S + 'cfd/renovacionysustitucionvehiculos/renovacionysustitucionvehiculos.xsd',
        prefix='decreto',
        level='document',
        title='Renovación y Sustitución de Vehículos 1.0',
        clashes={
            'renovacionysustitucionvehiculos/DecretoRenovVehicular/'
            'VehiculoNuvoSemEnajenadoFabAlPerm': ('RenovVehiculoNuvoSemEnajenadoFabAlPerm'),
            'renovacionysustitucionvehiculos/DecretoSustitVehicular/'
            'VehiculoNuvoSemEnajenadoFabAlPerm': ('SustitVehiculoNuvoSemEnajenadoFabAlPerm'),
        },
    ),
    'certificadodestruccion10': Schema(
        xsd=S + 'cfd/certificadodestruccion/certificadodedestruccion.xsd',
        prefix='destruccion',
        level='document',
        title='Certificado de Destrucción 1.0',
    ),
    'servicioparcialconstruccion10': Schema(
        xsd=S + 'cfd/servicioparcialconstruccion/servicioparcialconstruccion.xsd',
        prefix='servicioparcial',
        level='document',
        title='Servicios Parciales de Construcción 1.0',
    ),
    'registrofiscal10': Schema(
        xsd=S + 'cfd/cfdiregistrofiscal/cfdiregistrofiscal.xsd',
        prefix='registrofiscal',
        level='document',
        title='CFDI Registro Fiscal 1.0',
    ),
    'pfic10': Schema(
        xsd=S + 'cfd/pfic/pfic.xsd',
        prefix='pfic',
        level='document',
        title='PFIC 1.0',
    ),
    'iedu10': Schema(
        xsd=S + 'cfd/iedu/iedu.xsd',
        prefix='iedu',
        level='concept',
        title='Instituciones Educativas Privadas 1.0',
    ),
    'ventavehiculos11': Schema(
        xsd=S + 'cfd/ventavehiculos/ventavehiculos11.xsd',
        prefix='ventavehiculos',
        level='concept',
        title='Venta de Vehículos 1.1',
        clashes={
            'VentaVehiculos/Parte/InformacionAduanera': 'ParteInformacionAduanera',
        },
    ),
    'hidrocarburospetroliferos10': Schema(
        xsd=S + 'cfd/hidrocarburospetroliferos.xsd',
        prefix='hidrocarburospetroliferos',
        level='concept',
        title='Hidrocarburos y Petrolíferos 1.0',
    ),
}

# Elements whose content is open (xs:any), and what they hold.
OPEN_CONTENT = {'Complemento': 'document', 'ComplementoConcepto': 'concept', 'Addenda': 'raw'}

XS_TYPES = {
    'string': 'str',
    'normalizedString': 'str',
    'token': 'str',
    'base64Binary': 'str',
    'anyURI': 'str',
    'decimal': 'decimal',
    'integer': 'int',
    'int': 'int',
    'long': 'int',
    'short': 'int',
    'byte': 'int',
    'nonNegativeInteger': 'int',
    'positiveInteger': 'int',
    'negativeInteger': 'int',
    'nonPositiveInteger': 'int',
    'unsignedLong': 'int',
    'unsignedInt': 'int',
    'unsignedShort': 'int',
    'unsignedByte': 'int',
    'dateTime': 'datetime',
    'date': 'date',
    'time': 'time',
    'boolean': 'bool',
}
PY_TYPES = {
    'str': 'str',
    'decimal': 'Decimal',
    'int': 'int',
    'datetime': 'datetime',
    'date': 'date',
    'time': 'time',
    'bool': 'bool',
}
IMPORTED_NAMES = {'ClassVar', 'Decimal', 'date', 'datetime', 'time', 'XmlClass'} | {
    'attr',
    'child',
    'text',
    'text_child',
    'any_children',
    'register',
    'RawXml',
    'DocumentComplement',
    'ConceptComplement',
}
TEXT_FIELD = 'value'


# Schema reading ------------------------------------------------------------------------------


class Types:
    """Resolves simple types and named complex types across a schema and its imports."""

    def __init__(self, url: str) -> None:
        self.simple: dict[tuple[str, str], etree._Element] = {}
        self.complex: dict[tuple[str, str], etree._Element] = {}
        self._loaded: set[str] = set()
        self._load(url)

    def _load(self, url: str) -> None:
        if url in self._loaded:
            return
        self._loaded.add(url)
        root = _sat.load(url).getroot()
        namespace = root.get('targetNamespace', '')
        for node in root.findall(XS + 'simpleType'):
            self.simple[(namespace, node.get('name', ''))] = node
        for node in root.findall(XS + 'complexType'):
            self.complex[(namespace, node.get('name', ''))] = node
        for node in root.findall(XS + 'import'):
            location = node.get('schemaLocation')
            if location:
                self._load(location)

    @staticmethod
    def qname(node: etree._Element, value: str) -> tuple[str, str]:
        prefix, _, local = value.rpartition(':')
        namespace = node.nsmap.get(prefix or None, '')
        return namespace or '', local

    def kind(self, node: etree._Element, type_name: str | None = None) -> str:
        """The mapper's simple kind of an attribute or a text-only element."""
        if type_name is None:
            type_name = node.get('type')
        if type_name is None:
            inline = node.find(XS + 'simpleType')
            if inline is None:
                return 'str'
            return self._kind_of_simple(inline)
        namespace, local = self.qname(node, type_name)
        if namespace == XS[1:-1]:
            return XS_TYPES.get(local, 'str')
        found = self.simple.get((namespace, local))
        if found is None:
            raise GeneratorError(f'unknown simple type {type_name}')
        return self._kind_of_simple(found)

    def _kind_of_simple(self, simple_type: etree._Element) -> str:
        restriction = simple_type.find(XS + 'restriction')
        if restriction is None:
            return 'str'
        base = restriction.get('base')
        if base is None:
            inner = restriction.find(XS + 'simpleType')
            return 'str' if inner is None else self._kind_of_simple(inner)
        kind = self.kind(restriction, base)
        if kind == 'int' and _leading_zeros(restriction):
            # The digits themselves matter (a bank account), so keep the text.
            return 'str'
        return kind

    def complex_type(self, element: etree._Element) -> etree._Element | None:
        inline = element.find(XS + 'complexType')
        if inline is not None:
            return inline
        type_name = element.get('type')
        if type_name is None:
            return None
        return self.complex.get(self.qname(element, type_name))


def _leading_zeros(restriction: etree._Element) -> bool:
    """Whether an integer restriction's pattern accepts a value that starts with zero."""
    for facet in restriction.findall(XS + 'pattern'):
        pattern = facet.get('value', '')
        if any(re.fullmatch(pattern, '0' * length) for length in range(2, 31)):
            return True
    return False


@dataclass
class Field:
    name: str
    kind: str
    simple: str = 'str'
    cls: str | None = None
    many: bool = False
    required: bool = False
    wrapper_optional: bool = True
    accepts: str | None = None


@dataclass
class Class:
    path: str
    element: str
    name: str = ''
    fields: list[Field] = field(default_factory=list)
    fixed: list[tuple[str, str]] = field(default_factory=list)


def _occurs(node: etree._Element, attribute: str) -> int | None:
    value = node.get(attribute, '1')
    return None if value == 'unbounded' else int(value)


Particle = tuple[etree._Element, bool, bool]


def _particles(group: etree._Element, optional: bool, repeating: bool) -> list[Particle]:
    """The elements and wildcards of a model group: (node, optional, in a repeating group).

    A choice makes its members optional; a group with maxOccurs other than 1 makes them repeat.
    """
    optional = optional or _occurs(group, 'minOccurs') == 0 or group.tag == XS + 'choice'
    repeating = repeating or _occurs(group, 'maxOccurs') != 1
    found: list[Particle] = []
    for node in group:
        tag = node.tag if isinstance(node.tag, str) else ''
        if tag in (XS + 'element', XS + 'any'):
            found.append((node, optional or _occurs(node, 'minOccurs') == 0, repeating))
        elif tag in (XS + 'sequence', XS + 'all', XS + 'choice'):
            found.extend(_particles(node, optional, repeating))
    return found


def _content(complex_type: etree._Element) -> list[Particle]:
    for tag in ('sequence', 'all', 'choice'):
        group = complex_type.find(XS + tag)
        if group is not None:
            return _particles(group, False, False)
    return []


class Reader:
    def __init__(self, schema: Schema, clashes: dict[str, str]) -> None:
        self.schema = schema
        self.clashes = clashes
        self.types = Types(schema.xsd)
        self.classes: list[Class] = []

    def read(self) -> Class:
        root = _sat.load(self.schema.xsd).getroot()
        elements = root.findall(XS + 'element')
        if len(elements) != 1:
            raise GeneratorError(f'{self.schema.xsd}: expected one root element')
        return self._class(elements[0], elements[0].get('name', ''))

    def _class(self, element: etree._Element, path: str) -> Class:
        model = Class(path=path, element=element.get('name', ''))
        complex_type = self.types.complex_type(element)
        assert complex_type is not None
        simple_content = complex_type.find(XS + 'simpleContent')
        attribute_holder = complex_type
        if simple_content is not None:
            extension = simple_content.find(XS + 'extension')
            if extension is None:
                raise GeneratorError(f'{path}: simpleContent without extension')
            attribute_holder = extension
        for attribute in attribute_holder.findall(XS + 'attribute'):
            name = attribute.get('name', '')
            if attribute.get('fixed') is not None:
                model.fixed.append((name, attribute.get('fixed', '')))
                continue
            required = attribute.get('use') == 'required'
            if f'{path}/@{name}' in self.schema.library_written:
                required = False
            model.fields.append(
                Field(name, 'attribute', simple=self.types.kind(attribute), required=required)
            )
        if simple_content is not None:
            extension = simple_content.find(XS + 'extension')
            assert extension is not None
            model.fields.append(
                Field(TEXT_FIELD, 'text', simple=self.types.kind(extension, extension.get('base')))
            )
        for particle, optional, repeating in _content(complex_type):
            model.fields.append(self._particle(particle, optional, repeating, path))
        self.classes.append(model)
        return model

    def _particle(self, node: etree._Element, optional: bool, repeating: bool, path: str) -> Field:
        if node.tag == XS + 'any':
            raise GeneratorError(f'{path}: xs:any outside an open-content element')
        name = node.get('name', '')
        child_path = f'{path}/{name}'
        many = repeating or _occurs(node, 'maxOccurs') != 1
        required = not optional and child_path not in self.schema.library_written
        complex_type = self.types.complex_type(node)
        if complex_type is None:
            return Field(
                name, 'text_child', simple=self.types.kind(node), many=many, required=required
            )
        content = _content(complex_type)
        if name in OPEN_CONTENT and content and content[0][0].tag == XS + 'any':
            return Field(name, 'any', accepts=OPEN_CONTENT[name])
        has_attributes = complex_type.find(XS + 'attribute') is not None
        if (
            not many
            and not has_attributes
            and len(content) == 1
            and content[0][0].tag == XS + 'element'
            and _occurs(content[0][0], 'maxOccurs') != 1
        ):
            item, item_optional, _ = content[0]
            item_class = self._class(item, f'{child_path}/{item.get("name")}')
            return Field(
                name,
                'child',
                cls=item_class.path,
                many=True,
                required=required and not item_optional,
                wrapper_optional=optional,
            )
        child_class = self._class(node, child_path)
        return Field(name, 'child', cls=child_class.path, many=many, required=required)


def _name_classes(classes: list[Class], clashes: dict[str, str]) -> None:
    by_name: dict[str, list[Class]] = {}
    for model in classes:
        model.name = clashes.get(model.path, model.element)
        by_name.setdefault(model.name, []).append(model)
    clashes = [
        f'element name {name} is reused for different content: '
        + ', '.join(model.path for model in group)
        for name, group in by_name.items()
        if len(group) > 1
    ]
    if clashes:
        raise GeneratorError(
            '; '.join(clashes) + '; name all but one path of each in the schema clash table'
        )
    for model in classes:
        if model.name in IMPORTED_NAMES or keyword.iskeyword(model.name):
            raise GeneratorError(f'class name {model.name} collides with a reserved name')
        for item in model.fields:
            if keyword.iskeyword(item.name):
                raise GeneratorError(f'{model.path}: field {item.name} is a Python keyword')


# Emitting ------------------------------------------------------------------------------------


def _annotation(item: Field, names: dict[str, str]) -> str:
    if item.kind == 'any':
        accepts = {
            'document': 'DocumentComplement | RawXml',
            'concept': 'ConceptComplement | RawXml',
            'raw': 'RawXml',
        }[item.accepts or 'raw']
        return f'list[{accepts}]'
    base = names[item.cls] if item.kind == 'child' and item.cls else PY_TYPES[item.simple]
    if item.many:
        return f'list[{base}]'
    return base if item.required else f'{base} | None'


def _value(item: Field, names: dict[str, str], classes: dict[str, Class]) -> str:
    default = '' if item.required else ', default=None'
    if item.kind == 'attribute':
        simple = '' if item.simple == 'str' else repr(item.simple)
        args = ', '.join(part for part in (simple, default.removeprefix(', ')) if part)
        return f'attr({args})'
    if item.kind == 'text':
        return 'text()' if item.simple == 'str' else f'text({item.simple!r})'
    if item.kind == 'text_child':
        many = ', many=True' if item.many else ''
        return f'text_child({item.simple!r}{many}{default})'
    if item.kind == 'any':
        return f'any_children({item.name!r}, {item.accepts!r})'
    assert item.cls is not None
    target = classes[item.cls]
    if item.many and target.element != item.name:
        wrapper_optional = '' if item.wrapper_optional else ', wrapper_optional=False'
        return (
            f'child({names[item.cls]!r}, many=True, wrapper={item.name!r}'
            f'{wrapper_optional}{default})'
        )
    many = ', many=True' if item.many else ''
    return f'child({names[item.cls]!r}{many}{default})'


def _emit(module: str, schema: Schema, root: Class, classes: list[Class]) -> str:
    namespace = _sat.load(schema.xsd).getroot().get('targetNamespace', '')
    names = {model.path: model.name for model in classes}
    by_path = {model.path: model for model in classes}
    xsd_path = schema.xsd.removeprefix(_sat.SAT_BASE)
    lines = [
        f'"""{schema.title}: models generated from the SAT\'s schema.',
        '',
        f'Source: ``{xsd_path}``.',
        'Generated by ``tools/generate_models.py``; do not edit by hand.',
        '"""',
        '',
        'from __future__ import annotations',
        '',
        'from dataclasses import dataclass',
        'from datetime import date, datetime, time',
        'from decimal import Decimal',
        'from typing import ClassVar',
        '',
        'from mictlanix.cfdi._xml import (',
        '    ConceptComplement,',
        '    DocumentComplement,',
        '    RawXml,',
        '    XmlClass,',
        '    any_children,',
        '    attr,',
        '    child,',
        '    register,',
        '    text,',
        '    text_child,',
        ')',
        '',
        f'NAMESPACE = {namespace!r}',
        f'SCHEMA_LOCATION = {schema.xsd!r}',
    ]
    for model in classes:
        is_root = model is root
        bases = ''
        if is_root and schema.level == 'document':
            bases = '(DocumentComplement)'
        elif is_root and schema.level == 'concept':
            bases = '(ConceptComplement)'
        lines += ['', '']
        if is_root and schema.level != 'root':
            lines.append('@register')
        lines.append('@dataclass(frozen=True, kw_only=True)')
        lines.append(f'class {model.name}{bases}:')
        lines.append(f'    """``{schema.prefix}:{model.element}``.')
        lines.append('')
        path = textwrap.wrap(f'Path: {model.path.replace("/", " / ")}.', width=92)
        lines += [f'    {line}' for line in path]
        lines.append('    """')
        lines.append('')
        fixed = ''
        if model.fixed:
            fixed = ', fixed=(' + ''.join(f'({a!r}, {v!r}), ' for a, v in model.fixed) + ')'
        location = ', schema_location=SCHEMA_LOCATION' if is_root else ''
        lines.append(
            f'    __xml__: ClassVar[XmlClass] = XmlClass('
            f'{model.element!r}, NAMESPACE, {schema.prefix!r}{fixed}{location})'
        )
        for item in model.fields:
            annotation = _annotation(item, names)
            lines.append(f'    {item.name}: {annotation} = {_value(item, names, by_path)}')
    return '\n'.join(lines) + '\n'


def _ruff(arguments: list[str], source: str, module: str) -> str:
    result = subprocess.run(
        [
            sys.executable,
            '-m',
            'ruff',
            *arguments,
            '--stdin-filename',
            str(PACKAGE / f'{module}.py'),
            '-',
        ],
        input=source,
        capture_output=True,
        text=True,
        check=False,
        cwd=ROOT,
    )
    if result.returncode != 0:
        raise GeneratorError(
            f'ruff {arguments[0]} failed for {module}: {result.stdout}{result.stderr}'
        )
    return result.stdout


def _format(source: str, module: str) -> str:
    """Drop unused imports, sort them, and format like the rest of the code."""
    fixed = _ruff(['check', '--select', 'I,F401', '--fix', '--exit-zero'], source, module)
    return _ruff(['format'], fixed, module)


def generate(module: str, clashes: dict[str, str] | None = None) -> str:
    """The source of one model module."""
    schema = SCHEMAS[module]
    reader = Reader(schema, schema.clashes if clashes is None else clashes)
    root = reader.read()
    _name_classes(reader.classes, reader.clashes)
    return _format(_emit(module, schema, root, reader.classes), module)


def main() -> None:
    modules = sys.argv[1:] or sorted(SCHEMAS)
    for module in modules:
        (PACKAGE / f'{module}.py').write_text(generate(module), encoding='utf-8')
        print(f'generated {module}', file=sys.stderr)


if __name__ == '__main__':
    main()
