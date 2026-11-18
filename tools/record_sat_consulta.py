"""Record the SAT's not-found status answer and derive synthetic answers into tests/fixtures/sat/.

Dev-only. Run from the repository root:

    uv run python tools/record_sat_consulta.py

The SAT's status service needs no credentials. The one call uses the SAT's test RFCs and a test
UUID, which the SAT does not know, so the answer is "not found" and carries nothing to scrub. Every
other state is a synthetic answer derived from that recorded envelope (spec 004 research R8).
"""

from __future__ import annotations

import ssl
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path
from xml.sax.saxutils import escape

from lxml import etree

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'tests' / 'fixtures' / 'sat'
URL = 'https://consultaqr.facturaelectronica.sat.gob.mx/ConsultaCFDIService.svc'
ACTION = 'http://tempuri.org/IConsultaCFDIService/Consulta'
EXPRESSION = '?re=EKU9003173C9&rr=URE180429TM6&tt=116.0&id=939513EF-CEAA-4E44-9AD9-6224778D9A9D'
FOUND = 'S - Comprobante obtenido satisfactoriamente.'
NIL = '{http://www.w3.org/2001/XMLSchema-instance}nil'

# name: (CodigoEstatus, Estado, EsCancelable, EstatusCancelacion)
SYNTHETIC: dict[str, tuple[str, str, str, str]] = {
    'vigente_sin_aceptacion': (FOUND, 'Vigente', 'Cancelable sin aceptación', ''),
    'vigente_con_aceptacion': (FOUND, 'Vigente', 'Cancelable con aceptación', ''),
    'vigente_no_cancelable': (FOUND, 'Vigente', 'No cancelable', ''),
    'vigente_en_proceso': (FOUND, 'Vigente', 'Cancelable con aceptación', 'En proceso'),
    'vigente_rechazada': (FOUND, 'Vigente', 'Cancelable con aceptación', 'Solicitud rechazada'),
    'cancelado_sin_aceptacion': (
        FOUND,
        'Cancelado',
        'Cancelable sin aceptación',
        'Cancelado sin aceptación',
    ),
    'cancelado_con_aceptacion': (
        FOUND,
        'Cancelado',
        'Cancelable con aceptación',
        'Cancelado con aceptación',
    ),
    'cancelado_plazo_vencido': (FOUND, 'Cancelado', 'Cancelable con aceptación', 'Plazo vencido'),
    'cancelado_sin_estatus': (FOUND, 'Cancelado', 'Cancelable sin aceptación', ''),
    'codigo_n': (
        'N - 601: La expresión impresa proporcionada no es válida.',
        'Vigente',
        'Cancelable sin aceptación',
        '',
    ),
    'estado_desconocido': (FOUND, 'Suspendido', 'Cancelable sin aceptación', ''),
    'cancelable_desconocido': (FOUND, 'Vigente', 'Cancelable', ''),
    'estatus_desconocido': (FOUND, 'Vigente', 'Cancelable con aceptación', 'Desconocido'),
}


def _record() -> bytes:
    envelope = (
        '<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"'
        ' xmlns:tem="http://tempuri.org/"><soapenv:Body><tem:Consulta>'
        f'<tem:expresionImpresa>{escape(EXPRESSION)}</tem:expresionImpresa>'
        '</tem:Consulta></soapenv:Body></soapenv:Envelope>'
    ).encode()
    request = urllib.request.Request(
        URL,
        data=envelope,
        headers={'Content-Type': 'text/xml; charset=utf-8', 'SOAPAction': f'"{ACTION}"'},
    )
    try:
        with urllib.request.urlopen(
            request, timeout=60, context=ssl.create_default_context()
        ) as response:
            return bytes(response.read())
    except urllib.error.HTTPError as error:
        return bytes(error.read())


def _leaf(root: etree._Element, name: str) -> etree._Element:
    for node in root.iter():
        if isinstance(node.tag, str) and etree.QName(node).localname == name:
            return node
    raise KeyError(name)


def _write(name: str, root: etree._Element) -> None:
    (OUT / name).write_bytes(etree.tostring(root, xml_declaration=True, encoding='UTF-8'))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    recorded = etree.fromstring(_record())
    if _leaf(recorded, 'Estado').text != 'No Encontrado':
        raise SystemExit('the SAT did not answer "No Encontrado" for the test UUID')
    rows = [('consulta_no_encontrado.xml', 'recorded: the SAT does not know the test UUID')]
    _write(rows[0][0], recorded)
    for name, values in SYNTHETIC.items():
        root = etree.fromstring(etree.tostring(recorded))
        for field, value in zip(
            ('CodigoEstatus', 'Estado', 'EsCancelable', 'EstatusCancelacion'), values, strict=True
        ):
            node = _leaf(root, field)
            node.text = value or None
            node.attrib.pop(NIL, None)
        file = f'consulta_{name}.xml'
        _write(file, root)
        rows.append((file, 'synthetic: ' + ' / '.join(v or '(empty)' for v in values[1:])))
    lines = [
        '# SAT status answers',
        '',
        f"Recorded from the SAT's ConsultaCFDIService on {date.today().isoformat()} with",
        "`tools/record_sat_consulta.py`. The one call uses the SAT's test RFCs and a test UUID",
        'and needs no credentials, so there is nothing to scrub. Synthetic answers are derived',
        'from the recorded envelope for the states a test UUID cannot produce.',
        '',
        '| File | Source |',
        '|------|--------|',
        *(f'| `{name}` | {how} |' for name, how in rows),
        '',
    ]
    (OUT / 'README.md').write_text('\n'.join(lines), encoding='utf-8')
    print(f'wrote {len(rows)} answers to {OUT.relative_to(ROOT)}')


if __name__ == '__main__':
    main()
