---
title: 2026-07-02 spec-055-implementation
type: session-log
tags:
  - type/session-log
  - domain/training
  - domain/content
status: draft
source: agent
aliases: 2026-07-02 spec-055-implementation
created: '2026-07-02'
updated: '2026-07-02'
---

# Session: 055 Interactive Teaching Loop — full implementation

## Summary

Implemented spec 055 Interactive Teaching Loop: TeachingSession ORM + repository + migration 011, TrainingRunService extraction from the route handler, TeachingService orchestration, `/v1/teach` API and UI, 91 tests (all passing), lint/UX pass.

## Key Decisions

- **Training lifecycle extracted** into `TrainingRunService` (ADR-045). The route becomes a thin delegate; teaching reuses the same persistence logic. Route-parity test guards NMRG.
- **Teaching chains on native experiment id** (`current_base_experiment_id`), not `ExternalModel.id`. The session row is the chain head — MLflow tags provide lineage but are NOT the source of truth for "next base."
- **Compare = side-by-side inference** between two experiment ids. Formal evaluation via 054 deferred — it needs `ExternalModel.id` which teaching models lack.
- **Native full-model only in MVP.** LoRA/adapter and imported-model seeding deferred (broken in the current pipeline — no loadable artifact, no adapter DB auto-registration).
- **Dataset origin support**: `DatasetService.create_dataset()` now accepts an `origin` parameter. Teaching datasets are tagged `origin="teaching"`.

## Verification

- 91 tests passing: parity (7), existing training mocks (42), repo unit (9), TeachingService unit (14), TrainingRunService unit (8), teaching loop e2e (11)
- Ruff lint: PASS (1 inherited ASYNC230 suppressed)
- UX lint: PASS (24 files, S4:0)
- Coverage: 29.54% (above 23% threshold)

## Files Changed

- `anvil/_resources/migrations/versions/011_add_teaching_sessions.py` — new migration
- `anvil/api/templates/base.html` — Teach sidebar entry
- `anvil/api/templates/teach.html` — new teaching page template (424 lines)
- `anvil/api/v1/pages.py` — GET /teach handler
- `anvil/api/v1/router.py` — teach_router registration
- `anvil/api/v1/teach.py` — new route file (session CRUD, rounds, inspect, compare, rollback)
- `anvil/api/v1/training.py` — route now delegates to TrainingRunService (-863 lines)
- `anvil/db/models/teaching_session.py` — new ORM model
- `anvil/db/models/teaching_session_status.py` — new StrEnum
- `anvil/db/repositories/teaching_session_repository.py` — new repository
- `anvil/db/registry.py` — model registration
- `anvil/services/datasets/datasets.py` — origin parameter support
- `anvil/services/teaching/__init__.py` — domain sub-package
- `anvil/services/teaching/teaching_service.py` — new orchestration service
- `anvil/services/training/training_run_config.py` — new service-layer Pydantic model
- `anvil/services/training/training_run_service.py` — extracted lifecycle (1107 lines)
- `anvil/workbench.py` — training_runs + teaching properties
- `tests/conftest.py` — ANVIL_MLFLOW_URI env var for test infra
- `tests/e2e/test_teaching_loop.py` — 11 e2e tests
- `tests/e2e/test_training_parity.py` — 7 parity tests (NMRG guard)
- `tests/unit/api/v1/test_training.py` — updated mocks for extraction
- `tests/unit/db/test_teaching_session_repository.py` — 9 tests
- `tests/unit/services/test_teaching_service.py` — 14 tests
- `tests/unit/services/test_training_run_service.py` — 8 tests