# Implementation Plan: Model Registry Tracking

**Branch**: `002-model-registry-tracking` | **Date**: 2026-06-11 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/002-model-registry-tracking/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

Add a local model registry to anvil so users can register trained models from experiments, version them, and select from the registry (not experiments) for inference. The registry stores model artifacts independently from experiment MLflow storage. Users can browse, search, version, and delete registered models via the web UI.

**Design Outputs (Phase 0-1 completed)**:
- `research.md` — Technical decisions documented
- `data-model.md` — RegisteredModel + ModelVersion entity definitions
- `contracts/api.md` — REST API contract for registry endpoints
- `quickstart.md` — User-facing guide
- `AGENTS.md` — Agent context updated

## Technical Context

**Language/Version**: Python 3.11+  
**Primary Dependencies**: FastAPI, SQLAlchemy (async), MLflow, Jinja2, pytest (all existing — no new deps)  
**Storage**: SQLite (async SQLAlchemy) for metadata, local filesystem (`data/models/`) for model artifacts  
**Testing**: pytest with async fixtures (existing test patterns)  
**Target Platform**: macOS/Linux (local web server)  
**Project Type**: Web service (FastAPI) + Python package  
**Performance Goals**: Sub-second model artifact copy on registration; <1s model load for inference from registry  
**Constraints**: Local-only registry (no external service); must coexist with existing MLflow tracking; zero new pip dependencies  
**Scale/Scope**: Single-user local tool supporting up to thousands of registered models

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Article | Check | Notes |
|---------|-------|-------|
| I — Zero-Dependency Core | ✅ PASS | Core engine untouched; registry uses existing deps only (SQLAlchemy, FastAPI) |
| II — Educational Clarity | ✅ PASS | New code is backend infrastructure; follows existing patterns |
| III — Seeded Reproducibility | ✅ PASS | Registry captures metadata from seeded experiments; source experiment available for reproduction |
| IV — TDD Mandatory | ✅ PASS | All new code will have tests written before implementation |
| V — Async-First | ✅ PASS | Registry service/repository/API will follow existing async patterns |
| VI — Implicit Namespace | ✅ PASS | New modules will respect PEP 420; __init__.py only for public exports |
| VII — Layered Architecture | ✅ PASS | Full Repository → Service → God Class → Routes/CLI chain used |
| VIII — Whimsy Without Compromise | ✅ PASS | Registry UI pages will maintain retro whimsical style |

**Gate Result: All articles pass. Proceeding to Phase 0.**

**Re-check after Phase 1 design**: All articles still pass. No violations introduced.

## Complexity Tracking

> No violations to track — feature follows existing architecture patterns without exceptions.

## Project Structure

### Documentation (this feature)

```text
specs/002-model-registry-tracking/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
microgpt/
├── db/
│   ├── models/
│   │   └── training_config.py   # ADD: RegisteredModel, ModelVersion tables
│   └── repositories/
│       ├── experiments.py
│       └── models.py            # NEW: ModelRepository
├── services/
│   ├── experiments.py
│   ├── training.py
│   └── models.py                # NEW: ModelRegistryService
├── api/
│   ├── templates/
│   │   ├── inference.html       # MODIFY: show registered models only
│   │   ├── experiment_detail.html # MODIFY: add "Register Model" button
│   │   ├── models.html          # NEW: model registry browse page
│   │   └── model_detail.html    # NEW: model version history page
│   └── v1/
│       ├── router.py            # MODIFY: inference endpoints use registry
│       ├── training.py
│       ├── experiments.py
│       └── models.py            # NEW: model registry API routes
├── cli.py                       # MODIFY: expose ModelRegistryService through God Class
└── storage/
    ├── interface.py             # REUSE: FileStore for registry artifacts
    └── local.py                 # REUSE: LocalFileStore for registry artifacts

tests/
├── test_db/
│   └── test_model_repository.py  # NEW: repository tests
├── test_services/
│   └── test_model_service.py    # NEW: service tests
├── test_api/
│   └── test_model_routes.py     # NEW: API route tests
└── conftest.py                  # MODIFY: add registry fixtures

migrations/
└── versions/
    └── 002_add_model_registry.py # NEW: migration for RegisteredModel + ModelVersion tables
```

**Structure Decision**: Standard single-project layout following existing microgpt package patterns. All new code follows the established Repository → Service → API → Template architecture. No new top-level directories needed.

## Complexity Tracking

No violations to track — feature follows existing architecture patterns without exceptions.
