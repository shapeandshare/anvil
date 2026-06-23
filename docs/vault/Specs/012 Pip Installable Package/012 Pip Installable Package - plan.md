---
title: 012 Pip Installable Package - plan
type: plan
tags:
  - type/spec
spec-refs:
  - docs/vault/Specs/012 Pip Installable Package/
related:
  - '[[012 Pip Installable Package]]'
created: ~
updated: ~
---
# Implementation Plan: Pip-Installable Package

**Branch**: `012-pip-installable-package` | **Date**: 2026-06-18 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/docs/vault/Specs/012 Pip Installable Package/spec.md`

## Summary

Make anvil a genuine, self-contained pip-installable artifact and prove it works by installing the built wheel into a clean container, bringing it online with docker compose, and running focused system tests against the live instance.

The core technical work is **closing three packaging gaps** discovered during research: Alembic `migrations/` + `alembic.ini` and the `data/demo/` seed content currently live *outside* the `anvil` package and are resolved relative to the working directory, so they are absent from a wheel and silently break an installed package. The fix is the well-established pattern (precedent: IBM/mcp-context-forge PR #310, OpenStack Neutron): relocate these resources *inside* the package, resolve them via `importlib.resources` and Alembic's `package:resource` script-location syntax, and declare them as `[tool.setuptools.package-data]`. A multi-stage Dockerfile builds the wheel then `pip install`s only the `.whl` into a clean `python:3.11-slim` runtime; a single-service docker compose stack brings it online (in-process MLflow, ports 8080/5001, persistent named volume); and a small pytest+httpx system-test suite validates `/v1/health`, primary pages (assets present), CLI tools, DB init, and demo bootstrap.

## Technical Context

**Language/Version**: Python 3.11+ (`requires-python = ">=3.11"`)
**Primary Dependencies**: setuptools (build backend), `build`/`uv build` (wheel build), FastAPI, SQLAlchemy[asyncio], Alembic, MLflow (in-process), Jinja2 — all existing. No new runtime deps. New dev-only: `build` (or reuse `uv build`), `pytest` + `httpx` (existing) for system tests.
**Storage**: SQLite via async SQLAlchemy (`data/anvil-state.db`); MLflow SQLite (`mlruns/mlflow.db`); demo/seed files bundled in package, imported into DB on first run.
**Testing**: pytest (existing). New `tests/system/` suite runs against the running container via `httpx`; orchestrated by a Makefile target that does `docker compose up --wait` → pytest → `docker compose down -v`.
**Target Platform**: Linux container (`python:3.11-slim`); the wheel itself is pure-Python and OS-agnostic. Validation runs anywhere with Docker + Compose.
**Project Type**: Installable Python application (web service + CLI), single project.
**Performance Goals**: Build→image→online→tests-pass loop completes locally; workbench reachable within 5 min of install (SC-009); first-run init automatic.
**Constraints**: Base install MUST exclude torch and other heavyweight/GPU deps (Constitution Art. I & IX; torch stays in `[gpu]` extra). Wheel must be self-contained (no source tree at runtime). `mypy --strict`, `make lint`, 100% unit coverage gates still apply to changed Python code.
**Scale/Scope**: One wheel, one Dockerfile (multi-stage), one compose file, ~3 package relocations + path-resolution refactors, ~1 small system-test module. Public-index publishing, CI, and full e2e suites are OUT of scope (deferred).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Article | Relevance | Status |
|---|---|---|
| **I — Zero-Dependency Core** | `anvil/core/` must stay stdlib-only. This feature touches packaging/db/services, NOT `core/`. torch stays optional. | ✅ PASS — no core changes; base wheel adds no deps. |
| **II — Educational Clarity** | No engine/walkthrough changes. | ✅ N/A |
| **III — Seeded Reproducibility** | No training-determinism changes. | ✅ N/A |
| **IV — TDD Mandatory** | New/changed Python (path resolution, any new CLI) needs tests-first + 100% unit coverage; system tests are additive (the feature's acceptance gate). | ✅ PASS — plan mandates TDD for refactors; system tests are the gate. |
| **V — Async-First** | Migration service already async; no sync leakage introduced. | ✅ PASS |
| **VI — Implicit Namespace** | Moving `migrations/` into the package: research shows Alembic `package:resource` discovery may need an `__init__.py` in the migrations dir. This **conflicts** with Art. VI (no `__init__.py` for internal wiring). See Complexity Tracking + research decision to prefer `importlib.resources`-based resolution that avoids unnecessary `__init__.py`. | ⚠️ JUSTIFIED — see Complexity Tracking. |
| **VII — Layered Architecture** | Path-resolution fixes stay within db/service layers; no DB primitives leak. | ✅ PASS |
| **VIII — iOS-Grade Polish** | No UI changes; system tests assert assets render (protects polish). | ✅ PASS |
| **IX — Pit of Success** | Default no-arg install must produce a working system; GPU/torch opt-in only; first-run auto-bootstrap + auto-migrate must work from the installed package. | ✅ PASS — this feature directly enforces Art. IX for installed packages. |
| **Additional — Lean deps / ADR** | No new runtime deps. Packaging relocation is an architecture decision → ADR required in `docs/vault/Decisions/`. | ✅ PASS — ADR planned. |
| **Workflow — lint/typecheck/test gates** | All changed Python must pass `make lint`, `mypy --strict`, `make test` (100%). | ✅ PASS — gates retained. |

**Gate result**: PASS with one justified deviation (Art. VI re: migrations packaging — minimized via `importlib.resources`).

## Project Structure

### Documentation (this feature)

```text
docs/vault/Specs/012 Pip Installable Package/
├── plan.md              # This file
├── research.md          # Phase 0 output — consolidated decisions
├── data-model.md        # Phase 1 output — packaging/runtime entities
├── quickstart.md        # Phase 1 output — build→run→test loop
├── contracts/           # Phase 1 output
│   ├── packaging.md     #   Wheel contents + pyproject package-data contract
│   ├── dockerfile.md    #   Multi-stage build contract
│   ├── compose.md       #   Orchestration contract (ports, volume, healthcheck)
│   ├── cli.md           #   Console-scripts contract (must-work after install)
│   └── system-tests.md  #   System-test assertions contract
└── checklists/
    └── requirements.md  # (from /speckit.specify)
```

### Source Code (repository root)

```text
# Resources RELOCATED into the package (the central change):
anvil/
├── _resources/
│   ├── alembic.ini              # moved from repo-root alembic.ini
│   └── migrations/              # moved from repo-root migrations/
│       ├── env.py               #   (imports anvil.db.base already — package-aware)
│       ├── script.py.mako
│       ├── scripts/
│       └── versions/*.py        #   incl. merge-head 12a4027155f0_*
├── data/
│   └── demo/                    # moved from repo-root data/demo/
│       ├── small/ medium/ large/  (*.txt seed corpora)
│       └── README.md
├── db/
│   └── migration.py             # EDIT: resolve alembic.ini + script_location via importlib.resources
├── services/
│   └── demo_bootstrap.py        # EDIT: resolve DEMO_DIR via importlib.resources
├── cli.py                       # EDIT: remove/fix phantom `migrate_registry` entry; (optional) add `--version`
└── ... (unchanged)

# Build / packaging:
pyproject.toml                   # EDIT: add [tool.setuptools.package-data]; keep torch in [gpu]
Dockerfile                       # REWRITE: multi-stage build-wheel → pip install wheel into clean image
compose.yaml                     # NEW: single anvil service, ports 8080/5001, named volume, healthcheck
Makefile / shared/*.mk           # EDIT: add `build` (wheel) + `test-system` targets

# Tests:
tests/system/                    # NEW: pytest + httpx system tests against running container
└── test_installed_runtime.py
```

**Structure Decision**: Single project. The defining decision is relocating `migrations/`, `alembic.ini`, and `data/demo/` **into** the `anvil/` package under `anvil/_resources/` and `anvil/data/` so they are captured by the wheel and resolvable via `importlib.resources` regardless of CWD. This directly satisfies FR-003/FR-003a and the clean-install requirement (FR-005/FR-007). Validation tooling (Dockerfile, compose, system tests) lives at the repo root / `tests/system/`.

## Complexity Tracking

> Fill ONLY if Constitution Check has violations that must be justified.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| **Art. VI** — possible `__init__.py` inside `anvil/_resources/migrations/` to enable Alembic package-resource discovery | Alembic's `script_location = anvil:_resources/migrations` resolves via package import machinery; a versions package historically wanted importability | **Rejected** keeping migrations at repo root (breaks the wheel — the whole bug). **Mitigation**: research selects `importlib.resources.files("anvil")`-derived absolute `script_location` so Alembic gets a real filesystem path and NO `__init__.py` is required inside the migrations dirs, keeping Art. VI intact. The deviation is only invoked if runtime testing proves resource resolution otherwise fails. |
| **Relocating resources into the package** (structural change to long-standing layout) | A wheel only bundles files under the package dir by default; CWD-relative resources cannot work for an installed user (FR-003, FR-005) | Keeping resources at repo-root + `data-files`/`MANIFEST.in` rejected: `MANIFEST.in` only affects sdist (not wheel), and `data-files` land in unpredictable `*.data/` prefixes that break `importlib.resources` and zipapp/PyInstaller portability (per research). Recorded as an ADR. |
