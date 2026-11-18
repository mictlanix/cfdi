# Mictlanix CFDI Library

Python library for working with Mexican CFDI electronic invoices.

> Early setup: no CFDI functionality is implemented yet.

## Installation

```sh
pip install mtx-cfdi
```

```python
import mtx_cfdi
```

Requires Python 3.12+.

## Development

```sh
uv sync
uv run pytest -q
uv run ruff check
uv run ruff format --check
uv run mypy src
```

## License

[MIT](LICENSE)
