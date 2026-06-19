---
title: 'Session: Pip-Installable Package'
type: session-log
tags:
  - type/session-log
  - domain/infrastructure
  - domain/database
  - domain/operations
  - status/reviewed
created: '2026-06-18'
updated: '2026-06-18'
aliases:
  - 'Session: Pip-Installable Package'
  - 009-pip-installable-package
  - Pip-Installable Package Session
source: agent
code-refs:
  - specs/009-pip-installable-package/spec.md
  - specs/009-pip-installable-package/tasks.md
  - anvil/db/migration.py
  - anvil/services/demo_bootstrap.py
  - Dockerfile
  - compose.yaml
  - tests/system/test_installed_runtime.py
---
# Session: Pip-Installable Package

**Date**: 2026-06-18
**Trigger**: Feature: anvil must be pip installable by a user

## Problem

anvil required cloning the repository and running project-specific tooling (`make setup`). Three resource directories (`migrations/`, `alembic.ini`, `data/demo/`) lived outside the `anvil` Python package and were resolved relative to the working directory, so they were absent from a pip-installed wheel and silent failures occurred at runtime.

## Discovery

During codebase research, three critical packaging gaps were found:
1. `anvil/db/migration.py:15` — `ALEMBIC_INI` resolved to **repo root** via `Path(__file__).parent.parent.parent / "alembic.ini"` (absent in wheel).
2. `alembic.ini:2` — `script_location = migrations` was **CWD-relative**; `migrations/` lived at repo root outside the package.
3. `anvil/services/demo_bootstrap.py:27` — `DEMO_DIR = Path("data/demo")` was **CWD-relative** — a long-standing bug masked because devs always ran from the repo root.

Bonus: `anvil-migrate-registry` in `pyproject.toml` entry points referenced `anvil.cli:migrate_registry` — a function that does not exist (phantom entry point).

## What was implemented

38 tasks across 7 phases. Key files changed:

| File | Change |
|------|--------|
| `anvil/db/migration.py` | Resolve `alembic.ini` + `script_location` via `importlib.resources` (ADR-018) |
| `anvil/services/demo_bootstrap.py` | Resolve `DEMO_DIR` via `importlib.resources` |
| `alembic.ini` → `anvil/_resources/alembic.ini` | Relocated into package (git mv) |
| `migrations/` → `anvil/_resources/migrations/` | Relocated into package (git mv) |
| `data/demo/` → `anvil/data/demo/` | Relocated into package (git mv) |
| `pyproject.toml` | Added `[tool.setuptools.package-data]`; removed phantom entry point; updated ruff/coverage paths |
| `Dockerfile` | Multi-stage: builder builds wheel, runtime `pip install`s wheel ONLY (no source tree) |
| `compose.yaml` (new) | Single service, in-process MLflow, named volume, `python -c` healthcheck |
| `Makefile` | Added `build`, `compose-up`, `compose-down`, `compose-reset`, `test-system` targets |
| `tests/system/test_installed_runtime.py` | 25 system-test assertions (HTTP pages, assets, CLI) |
| `tests/system/test_wheel_contents.py` | 10 wheel-inspection assertions (resources, metadata, dep checks) |

### Tests written (TDD)

- `tests/unit/db/test_migration_paths.py` — asserts resolved paths are package-relative (via importlib.resources)
- `tests/unit/services/test_demo_bootstrap_paths.py` — asserts demo dir is resolved from package, not CWD
- Existing `test_migration.py` updated for additional `set_main_option("script_location")` call

## Key ADR

- **ADR-018**: Package Runtime Resources Inside the Wheel — records the context, decision, and consequences of relocating `migrations/`, `alembic.ini`, and `data/demo/` into the anvil package.

## Validation

Full `make test-system` loop passes 35/35 consistently:
- Build → wheel produced → resources bundled, metadata correct, torch NOT in base deps
- Docker build → runtime stage has zero source tree
- Compose up → healthy, migrations run, demo bootstraps
- System tests → all pages 200, per-page assets resolve, CLI tools work
- Teardown → volume cleaned

## Tags
- type/session-log
- domain/infrastructure
- domain/operations
- domain/database
- status/reviewed
