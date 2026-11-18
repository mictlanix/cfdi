"""Record and scrub Multifacturas test-mode answers into tests/fixtures/multifacturas/.

Dev-only. Run from the repository root with the PAC's test-mode credentials in the environment:

    MULTIFACTURAS_USER=... MULTIFACTURAS_PASSWORD=... uv run python tools/record_multifacturas.py

Every call uses produccion=NO, the SAT's public test CSD and a fresh test invoice. The answers are
scrubbed (credentials, RFCs outside the SAT's test set, PAC payload fields) before they are
written; synthetic answers for cases test mode cannot produce are derived from recorded envelopes.
"""

from __future__ import annotations

import base64
import os
import re
import ssl
import sys
import urllib.error
import urllib.request
from datetime import date, timedelta
from pathlib import Path
from xml.sax.saxutils import escape

from lxml import etree

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'src'))

from mictlanix.cfdi import CSD, _mexico, seal  # noqa: E402
from tests.conftest import invoice  # noqa: E402

OUT = ROOT / 'tests' / 'fixtures' / 'multifacturas'
CSD_DIR = ROOT / 'tests' / 'fixtures' / 'csd'
PAC = 'https://ws.multifacturas.com/pac/index.php'
CANCEL = 'https://ws.multifacturas.com/cancelacion2022/index.php'
ALLOWED_RFCS = {'EKU9003173C9', 'URE180429TM6', 'XAXX010101000', 'AAA010101AAA'}
RFC = re.compile(r'\b[A-ZÑ&]{3,4}[0-9]{6}[A-Z0-9]{3}\b')
BLANK = ('png', 'mensaje_original', 'mensaje_original_pac_json')
DOCUMENTS = ('cfdi', 'acuse', 'acuseSATResult')
CSD_PASSWORD = '12345678a'  # published by the SAT with its test CSDs

USER = os.environ.get('MULTIFACTURAS_USER', '')
PASSWORD = os.environ.get('MULTIFACTURAS_PASSWORD', '')


def _rpc(operation: str, body: str) -> bytes:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"'
        ' xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"'
        ' xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:tns="urn:wservicewsdl"'
        ' soap:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">'
        f'<soap:Body><tns:{operation}>{body}</tns:{operation}></soap:Body></soap:Envelope>'
    ).encode()


def _param(name: str, value: str) -> str:
    return f'<{name} xsi:type="xsd:string">{escape(value)}</{name}>'


def _send(url: str, action: str, envelope: bytes) -> bytes:
    request = urllib.request.Request(
        url,
        data=envelope,
        headers={'Content-Type': 'text/xml; charset=utf-8', 'SOAPAction': f'"{action}"'},
    )
    context = ssl.create_default_context()
    try:
        with urllib.request.urlopen(request, timeout=60, context=context) as response:
            return bytes(response.read())
    except urllib.error.HTTPError as error:
        return bytes(error.read())


def _pac(operation: str, params: dict[str, str], url: str = PAC) -> bytes:
    body = ''.join(_param(k, v) for k, v in params.items())
    return _send(url, f'urn:wservicewsdl#{operation}', _rpc(operation, body))


def _leaf(root: etree._Element, name: str) -> etree._Element | None:
    for node in root.iter():
        if isinstance(node.tag, str) and etree.QName(node).localname == name:
            return node
    return None


def _set(root: etree._Element, name: str, value: str) -> None:
    node = _leaf(root, name)
    if node is None:
        raise KeyError(name)
    node.text = value
    node.attrib.pop('{http://www.w3.org/2001/XMLSchema-instance}nil', None)


def _scrub_text(text: str) -> str:
    for secret, placeholder in ((USER, 'USER'), (PASSWORD, 'PASSWORD')):
        if secret:
            text = text.replace(secret, placeholder)
    return RFC.sub(lambda m: m.group(0) if m.group(0) in ALLOWED_RFCS else 'AAA010101AAA', text)


def _scrub(raw: bytes) -> etree._Element:
    root = etree.fromstring(raw)
    for name in BLANK:
        node = _leaf(root, name)
        if node is not None:
            node.text = ''
    for name in DOCUMENTS:
        node = _leaf(root, name)
        if node is not None and node.text and len(node.text) > 40:
            document = base64.b64decode(node.text).decode('utf-8')
            node.text = base64.b64encode(_scrub_text(document).encode('utf-8')).decode()
    for node in root.iter():
        if isinstance(node.tag, str) and node.text:
            node.text = _scrub_text(node.text)
    return root


def _write(name: str, root: etree._Element) -> None:
    (OUT / name).write_bytes(etree.tostring(root, xml_declaration=True, encoding='UTF-8'))


def _sealed() -> bytes:
    csd = CSD.load(
        (CSD_DIR / 'eku9003173c9.cer').read_bytes(),
        (CSD_DIR / 'eku9003173c9.key').read_bytes(),
        CSD_PASSWORD,
    )
    fecha = _mexico.now() - timedelta(hours=1)
    return seal(invoice(totals=False, Fecha=fecha, Folio=fecha.strftime('%H%M%S')), csd)


def _cancel(uuid: str, password: str) -> bytes:
    fields = {
        'usuario': USER,
        'pass': PASSWORD,
        'accion': 'cancelar',
        'produccion': 'NO',
        'uuid': uuid.upper(),
        'rfc': 'EKU9003173C9',
        'password': password,
        'motivo': '02',
        'folioSustitucion': '',
        'b64Cer': base64.b64encode((CSD_DIR / 'eku9003173c9.cer').read_bytes()).decode(),
        'b64Key': base64.b64encode((CSD_DIR / 'eku9003173c9.key').read_bytes()).decode(),
    }
    inner = ''.join(_param(k, v) for k, v in fields.items())
    body = f'<datos xsi:type="tns:datos">{inner}</datos>'
    return _send(CANCEL, 'urn:wservicewsdl#cancelarCfdi', _rpc('cancelarCfdi', body))


def _copy(root: etree._Element) -> etree._Element:
    return etree.fromstring(etree.tostring(root))


def main() -> None:
    if not USER or not PASSWORD:
        sys.exit('set MULTIFACTURAS_USER and MULTIFACTURAS_PASSWORD (test-mode credentials)')
    OUT.mkdir(parents=True, exist_ok=True)
    rows: list[tuple[str, str]] = []

    def keep(name: str, root: etree._Element, how: str) -> None:
        _write(name, root)
        rows.append((name, how))

    sealed = _sealed()
    xml64 = base64.b64encode(sealed).decode()
    stamp = {'rfc': USER, 'clave': PASSWORD, 'xml': xml64, 'produccion': 'NO'}
    ok = _scrub(_pac('timbrar33b64', stamp))
    keep('timbrar33b64_ok.xml', ok, 'recorded: a first stamp')
    keep(
        'timbrar33b64_duplicate.xml',
        _scrub(_pac('timbrar33b64', stamp)),
        'recorded: the same document again',
    )
    bad = {**stamp, 'xml': base64.b64encode(b'<not-a-cfdi/>').decode()}
    keep('timbrar33b64_301.xml', _scrub(_pac('timbrar33b64', bad)), 'recorded: malformed XML')
    tampered = sealed.replace(b'Sello="', b'Sello="X')
    bad = {**stamp, 'xml': base64.b64encode(tampered).decode()}
    keep(
        'timbrar33b64_CFDI40102.xml',
        _scrub(_pac('timbrar33b64', bad)),
        'recorded: a seal that does not verify',
    )
    saldo = _scrub(_pac('saldo', {'rfc': USER, 'clave': PASSWORD}))
    keep('saldo.xml', saldo, 'recorded: the balance')

    uuid = _leaf(ok, 'uuid').text or ''  # type: ignore[union-attr]
    keep(
        'acuseSAT_200.xml',
        _scrub(_pac('acuseSAT', {'rfc': USER, 'pwd': PASSWORD, 'uuid': uuid})),
        'recorded: test mode returns 200, not the document',
    )
    cancel = _scrub(_cancel(uuid, CSD_PASSWORD))
    keep('cancelarCfdi_205.xml', cancel, 'recorded: the SAT does not know test stamps')
    keep(
        'cancelarCfdi_CACFDI33.xml',
        _scrub(_cancel(uuid, 'wrong')),
        'recorded: a CSD password that does not open the key',
    )

    cfdi = _leaf(ok, 'cfdi').text or ''  # type: ignore[union-attr]
    for name, keep_cfdi, keep_uuid in (
        ('cfdi', True, True),
        ('uuid', False, True),
        ('none', False, False),
    ):
        root = _copy(ok)
        _set(root, 'codigo_mf_numero', '2')
        _set(root, 'codigo_mf_texto', '307 - El CFDI contiene un timbre previo.')
        if not keep_cfdi:
            _set(root, 'cfdi', '')
        if not keep_uuid:
            _set(root, 'uuid', '')
        keep(f'timbrar33b64_307_{name}.xml', root, 'synthetic: a duplicate reported as SAT 307')
    acuse = _copy(
        etree.fromstring(
            etree.tostring(_scrub(_pac('acuseSAT', {'rfc': USER, 'pwd': PASSWORD, 'uuid': uuid})))
        )
    )
    _set(acuse, 'acuseSATResult', cfdi)
    keep('acuseSAT_cfdi.xml', acuse, 'synthetic: production returns the stamped document')
    for code, text in (
        ('201', 'Solicitud de cancelación recibida'),
        ('202', 'Previamente cancelado'),
    ):
        root = _copy(cancel)
        _set(root, 'codigo_respuesta_sat', code)
        _set(root, 'codigo_respuesta_sat_texto', text)
        keep(f'cancelarCfdi_{code}.xml', root, f'synthetic: SAT {code}')
    error = _copy(saldo)
    _set(error, 'codigo_mf_numero', '1')
    _set(
        error,
        'codigo_mf_texto',
        'ERROR: {"message":"SYN01 - Credenciales no validas (sintetico).",'
        '"messageDetail":"","data":null,"status":"error"}',
    )
    _set(error, 'saldo', '0')
    keep('saldo_error.xml', error, 'synthetic: test mode ignores credentials')

    lines = [
        '# Multifacturas recorded answers',
        '',
        f"Recorded from the PAC's test mode (`produccion=NO`) on {date.today().isoformat()} with",
        "`tools/record_multifacturas.py`, using the SAT's public test CSD and a test invoice. The",
        'recorder scrubs every answer: credentials become `USER`/`PASSWORD`, RFCs outside the',
        "SAT's test set (including the PAC's own) become `AAA010101AAA`, and `png` and the",
        '`mensaje_original*` fields are blanked. Synthetic answers are derived from recorded',
        'envelopes for cases test mode cannot produce.',
        '',
        '| File | Source |',
        '|------|--------|',
        *(f'| `{name}` | {how} |' for name, how in rows),
        '',
    ]
    (OUT / 'README.md').write_text('\n'.join(lines), encoding='utf-8')
    print(f'wrote {len(rows)} fixtures to {OUT.relative_to(ROOT)}')


if __name__ == '__main__':
    main()
