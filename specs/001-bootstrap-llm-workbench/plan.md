# Implementation Plan: Bootstrap LLM Workbench

**Branch**: `001-bootstrap-llm-workbench` | **Date**: 2026-06-10 | **Spec**: `specs/001-bootstrap-llm-workbench/spec.md`
**Input**: Feature specification from `specs/001-bootstrap-llm-workbench/spec.md`

## Summary

Bootstrap a Python LLM workbench repository (microgpt) using patterns from oldgrowth. The system is a pip-installable Python package (`anvil-workbench`) wrapping Karpathy's microgpt.py with a FastAPI web server (async, Jinja2 SSR), MLflow experiment tracking (SQLite backend), repository-pattern data access (async SQLAlchemy), process supervisor for background services, a retro whimsical UI (pixel art, ASCII, SVG, unicorns 🦄, SSE streaming), and full agentic governance (constitution, vault, ADRs, AGENTS.md, .specify/ tooling). Implementation order: Agentic Harness → Boilerplating → Remainder.

## Technical Context

**Language/Version**: Python 3.11+ (stdlib-only for core microgpt.py; CPython primary, PyPy for stdlib-only core)
**Primary Dependencies**: FastAPI (async handlers), Jinja2, Uvicorn, SQLAlchemy (async + aiosqlite), Alembic, Pydantic v2, MLflow, aiofiles, python-dotenv, ruff, black, isort, pylint, mypy/pyright, pytest, pytest-asyncio, httpx (test client)
**Storage**: SQLite (async via aiosqlite/SQLAlchemy for app DB; sync SQLite via MLflow's own store for experiment tracking), filesystem (local via aiofiles, S3-ready abstraction)
**Testing**: pytest + pytest-asyncio + httpx (AsyncClient for FastAPI tests); coverage.py; TDD mandatory with 100% coverage enforcement
**Target Platform**: macOS ARM (Apple Silicon) bare metal primary; Linux planned (Docker); Windows explicitly excluded
**Project Type**: Hybrid — pip-installable Python package (`anvil-workbench`) with CLI entry points, web server (FastAPI background daemon), and MLflow tracking service
**Performance Goals**: Training completes 1000 steps on names dataset in under 60s on Apple Silicon (M1+); web UI responds to interactions within 200ms; SSE streams update loss chart at least once per training step
**Constraints**: Zero third-party deps for core microgpt.py; optional features (web, MLflow, GPU) are opt-in layers; no page refreshes (SSE streaming); implicit namespace packages; all internal imports relative; `__init__.py` only for package exports; strict explicit typing; no circular imports
**Scale/Scope**: Single-user local network tool; not designed for concurrent multi-user access

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Gates derived from spec requirements:**

1. ✅ **Zero-Dependency Core**: `anvil.py` MUST have zero third-party Python dependencies (stdlib only) — CONFIRMED by spec FR-001, FR-022
2. ✅ **TDD Mandatory**: Tests MUST be written before implementation; 100% unit test coverage + full e2e tests — CONFIRMED by spec FR-032, SC-022
3. ✅ **Implicit Namespace**: No `__init__.py` except for public API exports; all internal imports relative — CONFIRMED by spec FR-023, SC-012
4. ✅ **Layer Isolation**: Repository → Service → God Class → Routes — no DB primitives leak beyond repositories — CONFIRMED by spec FR-040, SC-028
5. ✅ **Async Architecture**: Fully async (FastAPI handlers, SQLAlchemy, FileStore, service layer) — CONFIRMED by spec clarification Q2
6. ✅ **Semantic Versioning**: MAJOR.MINOR.PATCH in pyproject.toml, accessible via `anvil.__version__` — CONFIRMED by spec FR-033
7. ✅ **Agentic Design**: Constitution, vault, ADRs, AGENTS.md, vault enrichment protocol — CONFIRMED by spec FR-006, FR-013, FR-034, FR-039, Phase 1 priority
8. ✅ **MLflow Exclusivity**: MLflow with SQLite, not W&B — CONFIRMED by spec FR-017

**All gates pass. No violations to justify.**

## Project Structure

### Documentation (this feature)

```text
specs/001-bootstrap-llm-workbench/
├── spec.md               # Feature specification
├── plan.md               # This file (Phase 1+2 output)
├── research.md           # Phase 0 output
├── data-model.md         # Phase 1 output
├── quickstart.md         # Phase 1 output
├── contracts/            # Phase 1 output (API contracts)
└── tasks.md              # Phase 2 output (/speckit.tasks)
```

### Source Code (repository root)

```text
microgpt/                          # Implicit namespace package (no __init__.py)
├── core/                          # Stdlib-only core training (no external deps)
│   ├── __init__.py                # Public API exports only
│   ├── engine.py                  # Core GPT (from microgpt.py)
│   ├── tokenizer.py               # Character-level tokenizer
│   └── autograd.py                # Value class + autograd engine
├── db/                            # Database layer
│   ├── __init__.py                # Public API exports
│   ├── session.py                 # Async session factory + Unit of Work
│   ├── base.py                    # SQLAlchemy declarative base
│   ├── repositories/              # Repository implementations
│   │   ├── __init__.py            # Exports all repos
│   │   ├── datasets.py            # DatasetRepository
│   │   ├── experiments.py         # ExperimentRepository
│   │   └── training_configs.py    # TrainingConfigRepository
│   └── models/                    # SQLAlchemy ORM models
│       ├── __init__.py            # Exports all models
│       ├── dataset.py
│       ├── experiment.py
│       └── training_config.py
├── services/                      # Business logic layer
│   ├── __init__.py                # Exports all services
│   ├── training.py                # TrainingService
│   ├── datasets.py                # DatasetService
│   └── experiments.py             # ExperimentService
├── api/                           # FastAPI web layer
│   ├── __init__.py                # Exports app factory
│   ├── app.py                     # FastAPI app creation + lifespan (auto-migrate)
│   ├── deps.py                    # FastAPI dependency injection (DB session, god class)
│   ├── v1/                        # Versioned API (/v1/)
│   │   ├── __init__.py            # Exports v1 router
│   │   ├── router.py              # /v1/ prefix router
│   │   ├── datasets.py            # Dataset CRUD endpoints + DTOs
│   │   ├── experiments.py         # Experiment endpoints + DTOs
│   │   ├── training.py            # Training control endpoints + SSE stream
│   │   └── health.py              # /v1/health endpoint
│   ├── templates/                 # Jinja2 templates
│   │   ├── base.html              # Base layout (nav, unicorn header, emojis)
│   │   ├── training.html          # Training dashboard (SSE for loss chart)
│   │   ├── experiments.html       # Experiment history + comparison
│   │   ├── datasets.html          # Dataset upload/management
│   │   ├── inference.html         # Inference/sampling page
│   │   └── operations.html        # Service management dashboard
│   └── static/                    # Static assets (CSS, SVG, icon lib)
│       ├── style.css
│       └── unicorn.svg
├── storage/                       # File storage abstraction
│   ├── __init__.py                # Exports FileStore interface + factory
│   ├── interface.py               # Pluggable async backend interface
│   └── local.py                   # Local filesystem backend (aiofiles)
├── supervisor/                    # Process supervisor (background daemons)
│   ├── __init__.py                # Exports supervisor class
│   ├── supervisor.py              # Service lifecycle management
│   └── services.py               # Service definitions (web, MLflow, training)
└── __init__.py                    # Package exports: MicroGPTWorkbench god class

migrations/                        # Alembic migrations
├── env.py                         # Async Alembic env
├── script.py.mako
└── versions/                      # Migration files

tests/                             # Test suite (TDD, 100% coverage)
├── unit/
│   ├── core/                      # Core engine tests
│   ├── db/                        # Repository tests
│   ├── services/                  # Service layer tests
│   └── api/                       # Route + DTO tests
├── e2e/                           # End-to-end system tests
│   ├── conftest.py               # FastAPI test client fixture, DB setup/teardown
│   └── test_full_lifecycle.py    # Start server → train → verify → stop
└── conftest.py                    # Shared fixtures (pytest-asyncio, session override)

data/                              # Runtime data (gitignored)
logs/                              # Service logs (gitignored)
mlruns/                            # MLflow tracking store (gitignored)

pyproject.toml                     # Package config + deps + entry points + tool config
alembic.ini                        # Alembic configuration
Makefile                           # Build targets (auto-venv, delegate to Python)
.specify/memory/constitution.md    # Project constitution
AGENTS.md                          # Agent behavioral guidelines
README.md                          # Quick-start guide
CONTRIBUTING.md                    # Contribution guidelines
.env.example                       # Environment variable reference
```

**Structure Decision**: Single flat Python package (`anvil/`) using implicit namespace. The package name `anvil` doubles as the module name. Core is stdlib-only. All optional deps (web, db, mlflow, gpu) are import-only-when-activated layers. `__init__.py` files exist ONLY in directories that export a public API (package root, `db/`, `services/`, `api/`, `api/v1/`, `storage/`, `supervisor/`, `core/`, `db/repositories/`, `db/models/`). Internal directories (e.g., utility modules) have NO `__init__.py`.

## Complexity Tracking

> Not applicable — all Constitution Check gates pass. No violations to justify.