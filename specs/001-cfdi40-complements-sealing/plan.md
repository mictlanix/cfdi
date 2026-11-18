# Implementation Plan: CFDI 4.0 Standard, Current Complements and Document Sealing

**Branch**: `001-cfdi40-complements-sealing` | **Date**: 2026-11-17 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/001-cfdi40-complements-sealing/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command; its definition describes the execution workflow.

## Summary

The library builds CFDI 4.0 documents of all five types with the 29 complements the SAT accepts
today, computes the values the standard derives, validates against the SAT's XSDs and Anexo 20
rules, produces the original string with the SAT's XSLT, seals with the issuer's CSD and reads
stamped CFDIs with their TimbreFiscalDigital.

Technical approach: the SAT's XSDs and XSLTs are vendored unmodified and resolved offline by
lxml. Typed models are frozen dataclasses with the SAT's exact names, generated from those XSDs
by a dev-only script and committed; one generic mapper converts any model to and from XML.
Sealing uses `cryptography`. The public API is a handful of pure functions exported from
`mictlanix.cfdi`.

The import package is `mictlanix.cfdi` (requested on 2026-11-17, replacing `mtx_cfdi`):
`mictlanix` is a namespace package shared with other Mictlanix distributions, and
`mictlanix.cfdi.pac` is reserved for the PAC clients of mictlanix/cfdi#2 and #3. The
distribution is renamed from `mtx-cfdi` to `mictlanix-cfdi`, so the install name and the import
name line up.

Delivery follows the spec's three stories: P1 (income, expense, payment with Pagos
2.0, sealing, reading the TFD), P2 (Nómina, Carta Porte, Comercio Exterior, Impuestos Locales,
type T documents), P3 (the remaining complements).

## Technical Context

**Language/Version**: Python 3.12 (`requires-python >= 3.12`)

**Primary Dependencies**: `lxml` (XML parsing, XSD validation, XSLT) and `cryptography` (X.509,
encrypted PKCS#8, RSA-SHA256). No other runtime dependency. Dev: pytest, pytest-asyncio, ruff,
mypy (already present), plus `types-lxml` and a spreadsheet reader for the catalog extraction
script.

**Storage**: N/A. The library reads and writes nothing; SAT artifacts are package data.

**Testing**: pytest, offline. Fixtures: the SAT's public test CSDs, expected original strings and
seals, one stamped sample.

**Target Platform**: any platform with CPython 3.12+ and wheels for lxml and cryptography
(Linux, macOS, Windows).

**Project Type**: library (single package `mictlanix.cfdi` inside the `mictlanix` namespace
package, src layout).

**Performance Goals**: none set by the spec. Compiled SAT schemas and stylesheets are cached per
process so the cost (measured: about 0.5 s for `cfdv40.xsd` with its catalogs) is paid once, not
per document.

**Constraints**: no network access in any operation; no secrets in errors, logs or reprs; SAT
files shipped byte-identical; `mypy --strict` on the whole package.

**Scale/Scope**: 5 document types, 29 complement schemas plus TFD 1.1, about 75 vendored SAT
files (roughly 10 MB uncompressed), 31 generated model modules, 10 public functions.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Gate | Status |
|-----------|------|--------|
| I. The SAT is the source of truth | SAT XSDs and XSLTs vendored unmodified with publication date and hash; models generated from them; only current complement versions have models; a test fails if a vendored file or a generated model drifts | Pass |
| II. Test-first, always | Every task writes its tests first. One test per document type and per complement builds, validates against the SAT's XSD, checks the original string from the SAT's XSLT and seals. Seals are compared with known results for the SAT's public test CSDs. All tests are offline; this feature has no PAC tests | Pass |
| III. Secrets never leak | CSD material comes only from the caller as bytes; `CSD` has a safe `repr`; no error carries key material or a password; fixtures hold only the SAT's public test CSDs (see note 3); the library does not log | Pass |
| IV. Never stamp twice | Not applicable: no PAC client in this feature (mictlanix/cfdi#2, #3). Nothing here blocks it: `seal` is deterministic and has no side effects | N/A |
| V. Small, stable, typed public API | 10 functions, the model classes and 7 errors, all exported from `mictlanix.cfdi` and checked by `mypy --strict`. Complements are exported as modules used as namespaces (see note 1). The import package matches constitution 1.0.1 (see note 2) | Pass |
| VI. Simplicity | Two runtime dependencies, each justified in research.md (R1, R7). No options beyond the spec. One mapper for all models. The library knows nothing about applications, databases or frameworks | Pass |
| Development workflow | uv; `ruff check`, `ruff format --check`, `mypy` strict and `pytest` gate every merge; code and docs in English; SAT names exact | Pass |

**Note 1, on principle V**: "everything public MUST be exported from" the import package is met by exporting
each complement as a module (`mictlanix.cfdi.pagos20`), not by exporting every complement class by
name. The SAT reuses element names across complements (`Emisor`, `Receptor`, `Traslado`), so a
single flat list of names would force renaming SAT names, against principle I and the workflow
rule on SAT spelling. This is a reading of the principle, not a violation; it is recorded here so
a reviewer can disagree.

**Note 2, import package**: constitution 1.0.0 named the import package `mtx_cfdi`. It was
amended to 1.0.1 on 2026-11-17 to name `mictlanix.cfdi`, with PAC clients exported from
`mictlanix.cfdi.pac`, following the project owner's instruction. The rule itself did not change
(one public entry point, fully typed), only the name, hence a PATCH.

**Note 3, on principle III and the test CSDs**: principle III forbids certificates, keys and
passwords in test fixtures and the repository, and principle II requires sealing to be checked
against the SAT's public test CSDs with tests that run offline. Both hold only if principle III
is about the caller's secrets, which is how its first sentence frames it. The SAT publishes its
test CSDs and their password for anyone to use; they identify no real taxpayer. So the plan
commits those, and only those, under `tests/fixtures/csd/`, with a test that fails if any other
certificate or key file appears in the repository. Recorded here so the project owner can
disagree.

**Post-design re-check (after Phase 1)**: the design added no dependency, no option and no
public name beyond those in [contracts/public-api.md](contracts/public-api.md). No violations
to justify, so Complexity Tracking is empty.

## Project Structure

### Documentation (this feature)

```text
specs/001-cfdi40-complements-sealing/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/
│   ├── public-api.md        # Phase 1 output (/speckit-plan command)
│   └── validation-rules.md  # written by the first rules task: SAT codes in scope
├── checklists/
│   └── requirements.md  # /speckit-specify output
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
src/mictlanix/               # namespace package: it has NO __init__.py
src/mictlanix/cfdi/
├── __init__.py              # the public API: every export in contracts/public-api.md
├── py.typed
├── cfdi40.py                # generated: Comprobante and its nodes
├── tfd11.py                 # generated: TimbreFiscalDigital 1.1
├── pagos20.py               # generated, one module per complement and version
├── nomina12.py
├── cartaporte31.py
├── ...                      # the other complement modules (data-model.md 1.3)
├── _xml.py                  # generic mapper: model <-> XML, complement registry, RawXml
├── _sat.py                  # resolver for vendored SAT files, cached schemas and stylesheets
├── _compute.py              # derived values and rounding (document, Pagos 2.0)
├── _validate.py             # XSD validation with a composite schema
├── _rules.py                # Anexo 20 rules, one function per SAT code
├── _csd.py                  # CSD loading and checks
├── _seal.py                 # original string, signing, seal()
├── _read.py                 # read(), timbre(), tfd_original_string(), qr_data()
├── _errors.py               # CfdiError and its subclasses, Violation
├── (pac/)                   # reserved for mictlanix/cfdi#2 and #3; NOT created by this feature
└── sat/                     # vendored SAT artifacts (package data)
    ├── manifest.json        # url, sha256, SAT publication date, retrieval date per file
    ├── sitio_internet/cfd/  # XSDs and XSLTs, mirroring the SAT URL path, byte-identical
    └── catalogs/            # catalog columns the rules need, with their source and date

tools/                       # dev-only, not shipped in the wheel
├── fetch_sat.py             # download SAT files and write manifest.json
├── generate_models.py       # XSD -> model modules
└── extract_catalogs.py      # SAT catalog spreadsheet -> sat/catalogs/

tests/
├── conftest.py              # blocks outbound connections for the whole suite
├── test_smoke.py            # existing
├── test_sat_artifacts.py    # manifest hashes and dates; offline resolution
├── test_generated_models.py # committed models equal a fresh generation
├── test_errors.py           # error classes and their typed fields
├── test_xml.py              # mapper round trips
├── test_to_xml.py           # serialization; RawXml emission guard
├── test_validate.py         # XSD violations name node and rule
├── test_original_string.py  # original string against a known result
├── test_compute.py          # derived values and rounding for the document
├── test_compute_pagos.py    # derived values for Pagos 2.0
├── test_payment_comprobante.py  # fixed shape of type P documents
├── test_rules.py            # Anexo 20 rules and the two library rules
├── test_csd.py              # loading, mismatch, password, validity, no leaks
├── test_seal.py             # known seals, determinism, refusal of invalid documents
├── test_read.py             # stamped sample, TFD, QR data, unmodelled complements
├── test_retired.py          # retired complement versions cannot be emitted
├── test_no_secrets.py       # no secrets in the repository or in output
├── test_offline.py          # the network guard in conftest.py raises on connect
├── test_public_api.py       # exports equal contracts/public-api.md
├── complements/             # conftest.py with the shared helper; one build-validate-seal
│                            # test per document type and complement
└── fixtures/
    ├── csd/                 # the SAT's public test CSDs only
    ├── expected/            # known original strings and seals
    └── stamped/             # stamped sample CFDIs
```

**Structure Decision**: a single library package, `mictlanix.cfdi`, in the src layout.
`src/mictlanix/` is a namespace package (PEP 420) with no `__init__.py`, so other Mictlanix
distributions can install their own `mictlanix.*` packages beside it. The existing
`src/mtx_cfdi/` package from the repository setup is renamed to `src/mictlanix/cfdi/` and the
distribution to `mictlanix-cfdi`, with `pyproject.toml` (`name = "mictlanix-cfdi"`,
`[tool.uv.build-backend] module-name = "mictlanix.cfdi"`), `uv.lock`, the smoke test and the
README updated in the same change; `CHANGELOG.md` is updated at the end. Model modules are flat and public; everything else is an
underscore-prefixed internal module, and `mictlanix/cfdi/__init__.py` is the only public entry
point. `mictlanix.cfdi.pac` is left free for the PAC clients; this feature creates nothing
there. Dev tools live in `tools/` at the repository root
so they are never part of the wheel. `.gitignore` gains a negated pattern for
`tests/fixtures/csd/` (the repository ignores `*.cer` and `*.key`). Generated modules pass
`ruff check`, `ruff format --check` and `mypy --strict` like any other source.

## Delivery order

Each story is independently testable and leaves the library releasable.

1. **Foundation** (needed by every story): rename the import package to `mictlanix.cfdi` and
   the distribution to `mictlanix-cfdi` (research.md R11) with all gates still green; vendor the SAT files with their manifest and
   resolver; the generator and the mapper; `cfdi40` models; XSD validation with violations;
   original string.
2. **P1**: derived values for the document; Anexo 20 rules for income, expense and payment
   documents; `pagos20` with its derived totals and `payment_comprobante`; CSD loading and
   `seal`; `read`, `tfd11`, `timbre`, `tfd_original_string`, `qr_data`.
3. **P2**: `nomina12`, `cartaporte31`, `comercioexterior20`, `implocal10` (and its effect on
   `Total`), type T (transfer) documents, with the rules that apply to them.
4. **P3**: the 24 remaining complement modules, each with its build-validate-seal test.

## Risks and open items

- **The SAT's public test CSDs were not loaded during research** (research.md R7). Confirming
  that their encrypted keys load is the first sealing task; a failure there would change R7.
- **Anexo 20 rule coverage** (research.md R8) is the largest open-ended area. The plan bounds it
  to rules decidable offline and to the nodes each story uses; `/speckit-tasks` should list the
  SAT codes per story so the scope is explicit and reviewable.
- **Wheel size**: about 10 MB of catalog XSDs uncompressed. Accepted; revisit only if it becomes
  a problem for callers.

## Complexity Tracking

No constitution violations; nothing to justify.
