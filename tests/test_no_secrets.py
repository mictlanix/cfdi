import ast
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKIPPED_DIRS = {'.git', '.venv'}
SECRET_SUFFIXES = {'.cer', '.key', '.pfx', '.pem'}
ALLOWED_DIR = ROOT / 'tests' / 'fixtures' / 'csd'


def _files(base: Path) -> list[Path]:
    found = []
    for path in base.rglob('*'):
        if SKIPPED_DIRS.intersection(path.relative_to(ROOT).parts):
            continue
        if path.is_file():
            found.append(path)
    return found


def _committable() -> list[Path]:
    """Every file git would commit: tracked, plus untracked files that are not ignored."""
    listed = subprocess.run(
        ['git', 'ls-files', '--cached', '--others', '--exclude-standard', '-z'],
        cwd=ROOT,
        capture_output=True,
        check=True,
    ).stdout
    return [ROOT / name for name in listed.decode('utf-8').split('\0') if name]


def test_no_certificate_or_key_outside_test_csd_fixtures() -> None:
    offenders = [
        path.relative_to(ROOT)
        for path in _committable()
        if path.suffix.lower() in SECRET_SUFFIXES and path.parent != ALLOWED_DIR
    ]
    assert offenders == []


def test_library_does_not_log_or_print() -> None:
    offenders = []
    for path in _files(ROOT / 'src'):
        if path.suffix != '.py':
            continue
        tree = ast.parse(path.read_text(encoding='utf-8'))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import) and any(a.name == 'logging' for a in node.names):
                offenders.append(f'{path.relative_to(ROOT)}: import logging')
            if isinstance(node, ast.ImportFrom) and node.module == 'logging':
                offenders.append(f'{path.relative_to(ROOT)}: from logging import')
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == 'print'
            ):
                offenders.append(f'{path.relative_to(ROOT)}:{node.lineno}: print()')
    assert offenders == []
