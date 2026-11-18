"""Extract the catalog columns the validation rules need from the SAT's catalog spreadsheet.

Dev-only; never shipped. The SAT publishes the CFDI 4.0 catalogs as one spreadsheet, linked as
``documentos/catCFDI_V_4_<date>.xls`` on the Anexo 20 page. Only the columns a rule or a
derivation uses are extracted, each into ``src/mictlanix/cfdi/_sat_files/catalogs/<name>.json``,
recorded in the manifest with the spreadsheet's URL and publication date.

Usage: uv run python tools/extract_catalogs.py [--file local-copy.xls --published YYYY-MM-DD]
"""

import argparse
import hashlib
import json
import sys
import tempfile
from collections.abc import Callable
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import xlrd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fetch_sat import SAT_DIR, fetch, load_manifest, save_manifest  # noqa: E402

CATALOG_URL = (
    'http://omawww.sat.gob.mx/tramitesyservicios/Paginas/documentos/catCFDI_V_4_20261106.xls'
)

Extract = Callable[[xlrd.sheet.Sheet], Any]

_TAX_CODES = {'IVA': '002', 'IEPS': '003', 'ISR': '001'}


def _rows(sheet: xlrd.sheet.Sheet, header: str | None = None) -> list[list[Any]]:
    """The data rows: everything after the header row, which starts with ``header``.

    The header defaults to the sheet's name, which is how most catalog sheets start it.
    """
    label = (header or sheet.name).lower()
    for index in range(sheet.nrows):
        if str(sheet.cell_value(index, 0)).strip().lower() == label:
            return [sheet.row_values(row) for row in range(index + 1, sheet.nrows)]
    raise SystemExit(f'{sheet.name}: header row not found')


def _text(value: Any) -> str:
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def _yes(value: Any) -> bool:
    return _text(value) == 'Sí'


def moneda_decimals(sheet: xlrd.sheet.Sheet) -> dict[str, int]:
    """Currency key to its number of decimals."""
    return {_text(row[0]): int(_text(row[2])) for row in _rows(sheet) if _text(row[0])}


def regimen_persona(sheet: xlrd.sheet.Sheet) -> dict[str, dict[str, bool]]:
    """Tax regime to the persona types it applies to."""
    return {
        _text(row[0]): {'fisica': _yes(row[2]), 'moral': _yes(row[3])}
        for row in _rows(sheet)
        if _text(row[0])
    }


def uso_cfdi(sheet: xlrd.sheet.Sheet) -> dict[str, dict[str, Any]]:
    """CFDI use to the persona types and recipient regimes it applies to."""
    found = {}
    for row in _rows(sheet):
        key = _text(row[0])
        if not key:
            continue
        regimenes = [part.strip() for part in _text(row[6]).split(',') if part.strip()]
        found[key] = {'fisica': _yes(row[2]), 'moral': _yes(row[3]), 'regimenes': regimenes}
    return found


def tasa_o_cuota(sheet: xlrd.sheet.Sheet) -> list[dict[str, Any]]:
    """Every rate or range, by tax code and factor, and whether it applies to each direction."""
    entries = []
    for index in range(sheet.nrows):
        if _text(sheet.cell_value(index, 0)) == 'Rango o Fijo':
            break
    else:
        raise SystemExit('c_TasaOCuota: header row not found')
    for row in (sheet.row_values(r) for r in range(index + 2, sheet.nrows)):
        kind = _text(row[0])
        if kind not in ('Fijo', 'Rango'):
            continue
        tax = next(code for name, code in _TAX_CODES.items() if _text(row[3]).startswith(name))
        entries.append(
            {
                'impuesto': tax,
                'factor': _text(row[4]),
                'rango': kind == 'Rango',
                'minimo': _text(row[1]) or None,
                'maximo': _text(row[2]),
                'traslado': _yes(row[5]),
                'retencion': _yes(row[6]),
            }
        )
    return entries


def pais_formato(sheet: xlrd.sheet.Sheet) -> dict[str, str]:
    """Country to its tax-ID pattern, for countries without an online register."""
    return {
        _text(row[0]): _text(row[3]) for row in _rows(sheet) if _text(row[3]) and not _text(row[4])
    }


def clave_prod_serv(sheet: xlrd.sheet.Sheet) -> dict[str, dict[str, bool]]:
    """Product keys that require a transferred tax, and which."""
    return {
        _text(row[0]).zfill(8): {'iva': _yes(row[2]), 'ieps': _yes(row[3])}
        for row in _rows(sheet)
        if _yes(row[2]) or _yes(row[3])
    }


def aduana(sheet: xlrd.sheet.Sheet) -> list[str]:
    return sorted(_text(row[0]).zfill(2) for row in _rows(sheet) if _text(row[0]))


def patente(sheet: xlrd.sheet.Sheet) -> list[str]:
    return sorted(_text(row[0]).zfill(4) for row in _rows(sheet) if _text(row[0]))


def num_pedimento(sheet: xlrd.sheet.Sheet) -> dict[str, int]:
    """'aduana|patente|ejercicio' to the highest consecutive number in use."""
    found = {}
    for row in _rows(sheet, header='c_Aduana'):
        if not _text(row[0]):
            continue
        key = f'{_text(row[0]).zfill(2)}|{_text(row[1]).zfill(4)}|{_text(row[2])}'
        found[key] = int(_text(row[3]))
    return found


# Output file name: (sheet, extractor).
CATALOGS: dict[str, tuple[str, Extract]] = {
    'c_Moneda': ('c_Moneda', moneda_decimals),
    'c_RegimenFiscal': ('c_RegimenFiscal', regimen_persona),
    'c_UsoCFDI': ('c_UsoCFDI', uso_cfdi),
    'c_TasaOCuota': ('c_TasaOCuota', tasa_o_cuota),
    'c_Pais': ('c_Pais', pais_formato),
    'c_ClaveProdServ': ('c_ClaveProdServ', clave_prod_serv),
    'c_Aduana': ('c_Aduana', aduana),
    'c_PatenteAduanal': ('c_PatenteAduanal', patente),
    'c_NumPedimentoAduana': ('c_NumPedimentoAduana', num_pedimento),
}


def main() -> None:
    args = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    args.add_argument('--file', type=Path, help='use a local copy of the spreadsheet')
    args.add_argument('--published', type=date.fromisoformat, help="the local copy's date")
    options = args.parse_args()

    if options.file is None:
        content, published = fetch(CATALOG_URL)
    elif options.published is None:
        raise SystemExit('--file needs --published, the SAT publication date of that copy')
    else:
        content, published = options.file.read_bytes(), options.published
    with tempfile.NamedTemporaryFile(suffix='.xls') as handle:
        handle.write(content)
        handle.flush()
        book = xlrd.open_workbook(handle.name)

    manifest = load_manifest()
    today = datetime.now(UTC).date().isoformat()
    for name, (sheet_name, extract) in CATALOGS.items():
        data = extract(book.sheet_by_name(sheet_name))
        if isinstance(data, dict):
            data = dict(sorted(data.items()))
        text = json.dumps(data, indent=1, ensure_ascii=False) + '\n'
        target = SAT_DIR / 'catalogs' / f'{name}.json'
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding='utf-8')
        manifest[f'catalogs/{name}.json'] = {
            'url': CATALOG_URL,
            'sheet': sheet_name,
            'sha256': hashlib.sha256(text.encode('utf-8')).hexdigest(),
            'published': published.isoformat(),
            'retrieved': today,
        }
        print(f'{name}: {len(data)} entries', file=sys.stderr)
    save_manifest(manifest)


if __name__ == '__main__':
    main()
