# Mictlanix CFDI Library Constitution

The Mictlanix CFDI Library (repository `mictlanix/cfdi`, import package `mictlanix.cfdi`) is a
Python 3.12 library that builds, validates and seals CFDI 4.0 documents with their complements,
and talks to PACs to stamp and cancel them.

## Core Principles

### I. The SAT Is the Source of Truth

- Every document MUST follow the SAT's current Anexo 20, XSDs, catalogs and XSLTs.
- The library MUST emit only versions the SAT accepts today.
- A version the SAT retires MUST be removed in a minor release, with its end date recorded in the
  changelog.
- SAT artifacts MUST be vendored in the package together with their publication date.
- Updating a vendored SAT artifact MUST be a deliberate, tested change.

Rationale: the SAT alone decides what a valid CFDI is; a document that deviates from its
published artifacts is rejected or, worse, legally invalid.

### II. Test-First, Always

- Tests MUST be written before the code, and are mandatory for all work with behavior.
- Every document type and every complement MUST have a test that builds it, validates it against
  the SAT's XSD and checks its original string against the SAT's XSLT.
- Sealing MUST be checked against known results from the SAT's public test CSDs.
- Tests MUST run offline by default.
- Tests against a PAC's test environment MUST be opt-in through environment variables and MUST be
  skipped when those variables are absent.

Rationale: fiscal documents fail in ways that are only visible when checked against the SAT's own
artifacts; an offline default keeps the suite fast, repeatable and free of credentials.

### III. Secrets Never Leak

- Certificates, private keys, passwords and PAC credentials MUST come only from the caller.
- They MUST NOT appear in exceptions, logs, reprs, test fixtures or the repository.
- Recorded PAC responses MUST be scrubbed before they are committed.

Rationale: a leaked CSD key or PAC credential lets a third party issue fiscal documents in the
taxpayer's name.

### IV. Never Stamp Twice

- PAC clients MUST be async.
- PAC clients MUST raise typed errors: rejected (carrying the PAC's code and message),
  unavailable, and timeout with unknown outcome.
- A timeout MUST be resolved by looking the stamp up, never by stamping again.
- Callers MUST never need to parse error text.

Rationale: a duplicated stamp is a second fiscal document that has to be cancelled; typed errors
let callers react correctly without guessing from messages.

### V. A Small, Stable, Typed Public API

- Everything public MUST be exported from `mictlanix.cfdi`, except the PAC surface: the generic
  PAC interface (its protocol, values, enums and errors) and every PAC client MUST be exported
  from `mictlanix.cfdi.pac`, and only from there.
- The public API MUST be fully typed and checked by mypy in strict mode.
- The library follows semantic versioning: breaking changes MUST happen only in a major release
  and MUST be listed in the changelog.

Rationale: callers build invoicing systems on this API; a small typed surface is one they can
depend on and one the project can keep stable.

### VI. Simplicity

- Code MUST be the minimum that satisfies the requirement, with no speculative options.
- Runtime dependencies MUST be few, and each one MUST be justified.
- The library MUST know nothing about any application, database or framework that uses it.
- Each PAC MUST live in its own client module, and all PAC clients MUST sit behind the same
  generic interface.

Rationale: every option and dependency is a permanent maintenance and security cost in a library
that other systems embed.

## Development Workflow

- uv is used for everything: environments, dependencies, running tools and builds.
- Before any merge, `uv run ruff check`, `uv run ruff format --check` and mypy in strict mode
  MUST pass, and `uv run pytest` MUST be green.
- Code, docs, issues and PRs MUST be written in English. SAT names (field, catalog and complement
  names) MUST keep their official Spanish spelling.
- Plan issues live in this repository; PRs MUST reference them.

## Governance

- This constitution outranks all other project practices.
- An amendment MUST bump the constitution's version, state its reason, and update the affected
  templates.
- The version follows semantic versioning: MAJOR for removing or redefining a principle or
  governance rule, MINOR for adding a principle or section or materially expanding guidance,
  PATCH for clarifications and wording.
- PRs and reviews MUST verify compliance with this constitution.

**Version**: 1.0.2 | **Ratified**: 2026-11-17 | **Last Amended**: 2026-11-18
