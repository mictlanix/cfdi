"""Download the SAT's XSDs and XSLTs into the package and record them in the manifest.

Dev-only; never shipped. Each file is stored byte-identical under
``src/mictlanix/cfdi/_sat_files/sitio_internet/`` at the path it has on the SAT's server, and
``src/mictlanix/cfdi/_sat_files/manifest.json`` records its URL, SHA-256, publication date (the
server's ``Last-Modified`` header) and retrieval date.

The URLs come from an explicit table, not from following includes: a complement's XSD is not
always next to its stylesheet. By default only files missing from the manifest are fetched, so
adding a URL never silently updates files already vendored. ``--refresh`` downloads everything
again; an update to a SAT file is a deliberate change.

Usage: uv run python tools/fetch_sat.py [--refresh]
"""

import argparse
import hashlib
import json
import sys
import urllib.request
from datetime import UTC, date, datetime
from email.utils import parsedate_to_datetime
from pathlib import Path

SAT_BASE = 'http://www.sat.gob.mx/sitio_internet/'
ROOT = Path(__file__).resolve().parent.parent
SAT_DIR = ROOT / 'src' / 'mictlanix' / 'cfdi' / '_sat_files'
MANIFEST = SAT_DIR / 'manifest.json'
USER_AGENT = 'Mozilla/5.0 (compatible; sat-artifact-fetcher)'

# CFDI 4.0, its catalogs and data types, the original-string stylesheet with every stylesheet
# it includes (the retired CartaPorte20, CartaPorte30 and ComercioExterior11 among them: the
# unmodified main stylesheet needs them to compile), and the TimbreFiscalDigital 1.1.
CFDI40 = [
    'cfd/4/cfdv40.xsd',
    'cfd/catalogos/catCFDI.xsd',
    'cfd/tipoDatos/tdCFDI/tdCFDI.xsd',
    'cfd/4/cadenaoriginal_4_0/cadenaoriginal_4_0.xslt',
    'cfd/2/cadenaoriginal_2_0/utilerias.xslt',
    'cfd/donat/donat11.xslt',
    'cfd/divisas/divisas.xslt',
    'cfd/implocal/implocal.xslt',
    'cfd/leyendasFiscales/leyendasFisc.xslt',
    'cfd/pfic/pfic.xslt',
    'cfd/TuristaPasajeroExtranjero/TuristaPasajeroExtranjero.xslt',
    'cfd/nomina/nomina12.xslt',
    'cfd/cfdiregistrofiscal/cfdiregistrofiscal.xslt',
    'cfd/pagoenespecie/pagoenespecie.xslt',
    'cfd/aerolineas/aerolineas.xslt',
    'cfd/valesdedespensa/valesdedespensa.xslt',
    'cfd/notariospublicos/notariospublicos.xslt',
    'cfd/vehiculousado/vehiculousado.xslt',
    'cfd/servicioparcialconstruccion/servicioparcialconstruccion.xslt',
    'cfd/renovacionysustitucionvehiculos/renovacionysustitucionvehiculos.xslt',
    'cfd/certificadodestruccion/certificadodedestruccion.xslt',
    'cfd/arteantiguedades/obrasarteantiguedades.xslt',
    'cfd/ComercioExterior11/ComercioExterior11.xslt',
    'cfd/ComercioExterior20/ComercioExterior20.xslt',
    'cfd/ine/ine11.xslt',
    'cfd/iedu/iedu.xslt',
    'cfd/ventavehiculos/ventavehiculos11.xslt',
    'cfd/detallista/detallista.xslt',
    'cfd/EstadoDeCuentaCombustible/ecc12.xslt',
    'cfd/consumodecombustibles/consumodeCombustibles11.xslt',
    'cfd/GastosHidrocarburos10/GastosHidrocarburos10.xslt',
    'cfd/IngresosHidrocarburos10/IngresosHidrocarburos.xslt',
    'cfd/CartaPorte/CartaPorte20.xslt',
    'cfd/Pagos/Pagos20.xslt',
    'cfd/CartaPorte/CartaPorte30.xslt',
    'cfd/CartaPorte/CartaPorte31.xslt',
    'cfd/HidrocarburosPetro/hidrocarburospetroliferos.xslt',
    'cfd/TimbreFiscalDigital/TimbreFiscalDigitalv11.xsd',
    'cfd/TimbreFiscalDigital/cadenaoriginal_TFD_1_1.xslt',
]

# Pagos 2.0 and its catalog.
PAGOS20 = [
    'cfd/Pagos/Pagos20.xsd',
    'cfd/catalogos/Pagos/catPagos.xsd',
]

# User Story 2 complements and the catalogs they import.
P2 = [
    'cfd/nomina/nomina12.xsd',
    'cfd/catalogos/Nomina/catNomina.xsd',
    'cfd/CartaPorte/CartaPorte31.xsd',
    'cfd/catalogos/CartaPorte/catCartaPorte.xsd',
    'cfd/catalogos/ComExt/catComExt.xsd',
    'cfd/ComercioExterior20/ComercioExterior20.xsd',
    'cfd/implocal/implocal.xsd',
]

# User Story 3: the remaining complements and the catalogs they import. The Hidrocarburos y
# Petrolíferos XSD is not next to its stylesheet; its URL comes from the SAT's complement page.
P3 = [
    'cfd/catalogos/Combustible/catCombustible.xsd',
    'cfd/catalogos/hidrocarburos/catHidrocarburos.xsd',
    'cfd/catalogos/HidrocarburosPetro/catHidroYPetro.xsd',
    'cfd/divisas/divisas.xsd',
    'cfd/donat/donat11.xsd',
    'cfd/leyendasFiscales/leyendasFisc.xsd',
    'cfd/ine/ine11.xsd',
    'cfd/aerolineas/aerolineas.xsd',
    'cfd/detallista/detallista.xsd',
    'cfd/TuristaPasajeroExtranjero/TuristaPasajeroExtranjero.xsd',
    'cfd/EstadoDeCuentaCombustible/ecc12.xsd',
    'cfd/consumodecombustibles/consumodeCombustibles11.xsd',
    'cfd/GastosHidrocarburos10/GastosHidrocarburos10.xsd',
    'cfd/IngresosHidrocarburos10/IngresosHidrocarburos.xsd',
    'cfd/notariospublicos/notariospublicos.xsd',
    'cfd/arteantiguedades/obrasarteantiguedades.xsd',
    'cfd/pagoenespecie/pagoenespecie.xsd',
    'cfd/valesdedespensa/valesdedespensa.xsd',
    'cfd/vehiculousado/vehiculousado.xsd',
    'cfd/renovacionysustitucionvehiculos/renovacionysustitucionvehiculos.xsd',
    'cfd/certificadodestruccion/certificadodedestruccion.xsd',
    'cfd/servicioparcialconstruccion/servicioparcialconstruccion.xsd',
    'cfd/cfdiregistrofiscal/cfdiregistrofiscal.xsd',
    'cfd/pfic/pfic.xsd',
    'cfd/iedu/iedu.xsd',
    'cfd/ventavehiculos/ventavehiculos11.xsd',
    'cfd/hidrocarburospetroliferos.xsd',
]

TABLE = CFDI40 + PAGOS20 + P2 + P3


def load_manifest() -> dict[str, dict[str, str]]:
    if not MANIFEST.exists():
        return {}
    data: dict[str, dict[str, str]] = json.loads(MANIFEST.read_text(encoding='utf-8'))
    return data


def save_manifest(manifest: dict[str, dict[str, str]]) -> None:
    text = json.dumps(dict(sorted(manifest.items())), indent=2, ensure_ascii=False)
    MANIFEST.write_text(text + '\n', encoding='utf-8')


def fetch(url: str) -> tuple[bytes, date]:
    request = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
    with urllib.request.urlopen(request, timeout=120) as response:
        content: bytes = response.read()
        last_modified = response.headers.get('Last-Modified')
    if not last_modified:
        raise SystemExit(f'{url}: the server sent no Last-Modified header')
    return content, parsedate_to_datetime(last_modified).date()


def main() -> None:
    args = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    args.add_argument('--refresh', action='store_true', help='download every file again')
    refresh = args.parse_args().refresh

    manifest = load_manifest()
    today = datetime.now(UTC).date().isoformat()
    for path in TABLE:
        key = f'sitio_internet/{path}'
        if key in manifest and not refresh:
            continue
        url = SAT_BASE + path
        content, published = fetch(url)
        target = SAT_DIR / key
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        manifest[key] = {
            'url': url,
            'sha256': hashlib.sha256(content).hexdigest(),
            'published': published.isoformat(),
            'retrieved': today,
        }
        print(f'{published}  {len(content):>9}  {path}', file=sys.stderr)
    save_manifest(manifest)


if __name__ == '__main__':
    main()
