---
title: 'ADR-018: Package Runtime Resources Inside the Wheel'
type: decision
tags:
  - type/decision
  - domain/infrastructure
  - domain/database
created: '2026-06-18'
updated: '2026-06-18'
aliases:
  - 'ADR-018: Package Runtime Resources Inside the Wheel'
  - ADR-018
  - Packaging Resource Relocation
source: agent
code-refs:
  - anvil/db/migration.py
  - anvil/services/demo_bootstrap.py
  - pyproject.toml
---
# ADR-018: Package Runtime Resources Inside the Wheel

## Status

Accepted

## Context

anvil required three non-Python resource directories at runtime that lived
*outside* the `anvil` Python package at the repository root:

- `migrations/` (Alembic schema migrations) — ref'd in `alembic.ini` as
  `script_location = migrations` (CWD-relative).
- `alembic.ini` — resolved by `anvil/db/migration.py` via
  `Path(__file__).parent.parent.parent / "alembic.ini"` (repo-root-relative).
- `data/demo/` (seed corpora/datasets for first-run bootstrap) — resolved by
  `anvil/services/demo_bootstrap.py` via `Path("data/demo")` (CWD-relative).

When anvil was installed via `pip install` from a wheel, none of these
resources were present because setuptools only bundles files *inside* the
package directory (`anvil/`) by default. The result was:
- Database migrations would silently not be found (Alembic would error).
- Demo content auto-bootstrap would no-op.
- The web server would fail to start or serve a degraded experience.

This made the project non-installable — a developer had to clone the repo
and use project-specific tooling (`make setup`) to run it.

## Decision

Move the three resource directories into the `anvil` package and resolve them
via the standard library's `importlib.resources` mechanism (Python ≥3.11):

| Resource | Old location | New location (in package) |
|---|---|---|
| Alembic config | `./alembic.ini` | `anvil/_resources/alembic.ini` |
| Migrations | `./migrations/` | `anvil/_resources/migrations/` |
| Demo/seed data | `./data/demo/` | `anvil/data/demo/` |

**Resolution mechanism**:
- `ALEMBIC_INI` in `anvil/db/migration.py` now uses
  `importlib.resources.files("anvil") / "_resources" / "alembic.ini"`.
- Script location is overridden programmatically to an absolute path
  derived from the same resource package. This avoids needing Alembic's
  `package:resource` syntax, which historically nudges toward adding
  `__init__.py` to migration directories (conflict with Constitution
  Art. VI — implicit namespace packages).
- `DEMO_DIR` in `anvil/services/demo_bootstrap.py` now uses
  `importlib.resources.files("anvil") / "data" / "demo"`.

**Packaging declaration**: `[tool.setuptools.package-data]` globs in
`pyproject.toml` explicitly include all non-Python resources in the wheel.

## Consequences

**Easier**:
- The project is genuinely `pip install`-able. A wheel contains everything
  needed to run the full workbench.
- Importlib.resources-based resolution works regardless of CWD, container
  file system layout, or future distribution formats (zipapp, PyInstaller).
- No `__init__.py` files were added to migration directories (Art. VI
  preserved). Only an `__init__.py` in `anvil/_resources/` is needed if
  the directory itself is imported (it is not; resources are resolved by
  name within the `anvil` package).
- Reproducible validation exists via the multi-stage Dockerfile +
  docker compose + system-test loop.

**Harder**:
- Developers working from a source checkout will no longer have
  `./alembic.ini` or `./migrations/` at the repo root. The MigrationService
  still discovers these from the installed package; development tooling
  (editable pip install, `uv run`) covers this correctly.
- Existing test assertions that reference repo-root paths needed updates
  (e.g., `test_migration.py` call-count assertions).
- The old `make docker` target was deprecated; the `make compose-up` path
  must be learned.

## Compliance

Verified by:
1. `make build` + inspection: `unzip -l dist/anvil-*.whl` shows all resources.
2. `docker build` + run: the runtime stage has no source tree; `anvil serve`
   runs migrations and bootstraps demo automatically.
3. `make test-system` (35 passes): HTTP, asset, DB, and CLI assertions
   against the installed container.
4. Unit tests verify `MigrationService` and `DemoBootstrapService` resolve
   paths from inside the package.

## See Also

- [[Decisions/README|Decisions]]
