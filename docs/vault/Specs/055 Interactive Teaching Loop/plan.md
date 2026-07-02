# Implementation Plan: Interactive Teaching Loop

**Branch**: `055-interactive-teaching-loop` | **Date**: 2026-07-02 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `docs/vault/Specs/055 Interactive Teaching Loop/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command.

## Summary

Make "teaching a model" a first-class, iterative experience: add/curate examples → run a short fine-tune (checkpoint-chained via 039) → inspect outputs (045) → repeat. Each iteration reuses the existing training pipeline and is tagged as a TeachingRound (MLflow run), scoped to a lightweight TeachingSession DB table. Dedicated page at `/v1/teach` with session list/selector. All artifacts (datasets, training runs, model checkpoints) are independently visible outside the teaching context.

> **Architecture note (post-review 2026-07-02)**: A codebase-verification pass (research.md §9-§12, Oracle consult) revealed the full training lifecycle — including the critical persistence of the loadable model artifact at `data/models/experiment_{id}.json` — lives inside a ~200-line `on_complete` closure in the `POST /training/start` **route handler**, not the service layer. `TrainingService.start_training()` alone does NOT persist a loadable model. Therefore this feature FIRST extracts that orchestration into a reusable service-layer coordinator (`TrainingRunService`), then has BOTH the existing route and the new teaching flow call it. Teaching chains on the **native integer experiment id** (the identifier warm-start + inference already agree on), NOT `ExternalModel.id`. Formal evaluation (054) is **deferred** — MVP "compare" is side-by-side inference between two experiment ids. See Complexity Tracking.

## Technical Context

**Language/Version**: Python 3.11+ (PEP 604, `StrEnum`, `from __future__ import annotations`)  
**Primary Dependencies**: FastAPI, async SQLAlchemy + aiosqlite, Alembic, Jinja2, MLflow, Pydantic — all existing  
**Storage**: SQLite (anvil-state.db, WAL) — new `teaching_sessions` table (holds `current_base_experiment_id` chain head) via async SQLAlchemy + Alembic migration; MLflow runs + `data/models/experiment_{id}.json` artifacts for TeachingRound data  
**Testing**: pytest + httpx (AsyncClient), e2e HTTP tests in `tests/e2e/`, unit tests in `tests/unit/`  
**Target Platform**: Web (FastAPI + Jinja2 served via uvicorn)  
**Project Type**: Web application (Python pip package with web UI)  
**Performance Goals**: Pedagogical throughput — rounds are short fine-tunes (seconds to minutes). Roundtrip latency dominated by training time. SSE reuses the existing `/v1/training/stream/{run_id}` endpoint (process-local `asyncio.Queue`) — frontend connects directly; teaching does NOT proxy the stream.  
**Constraints**: NMRG on existing tests. All artifacts independently accessible outside teaching. Reuse 039/053/045 without forking; the training-lifecycle extraction (`TrainingRunService`) is a refactor that BOTH the route and teaching consume — the existing route's behavior must be byte-for-byte preserved. No new runtime dependencies. Teaching chains on native experiment id; NO `ExternalModel` FK. Formal evaluation (054) deferred.  
**Scale/Scope**: User-driven sessions (not bulk). Native (full-model) teaching only for MVP — LoRA/adapter deferred (adapter runs don't persist a loadable `experiment_{id}.json` and LoRAAdapter DB rows aren't auto-created). Imported HF/local models as round-1 seed deferred (no experiment artifact). Checkpoint retention default: last 10 per session.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Simplicity First gate (Article XI — hard MUST)**: Confirm this plan favors
the simplest, most boring solution that meets the requirement:

- [x] **Simplest viable** (§11.1) — TeachingSession table + TeachingRound = tagged MLflow run reusing the existing training pipeline. The one non-trivial structural change (extracting the training lifecycle into `TrainingRunService`) is the SIMPLEST correct way to reuse the persistence logic without HTTP-internal calls or duplication (see Complexity Tracking).
- [x] **Boring over novel** (§11.2) — All technology reuses the existing stack (FastAPI, SQLAlchemy, MLflow, Jinja2, Alembic, Pydantic). No new/experimental deps.
- [x] **YAGNI** (§11.3) — TeachingSession schema minimal. Native-only, no formal-eval, no LoRA, no imported-seed for MVP — deferred until a concrete need + unified model-id design exists. No speculative abstraction.
- [x] **Reuse first** (§11.4) — Reuses 039 warm-start, 053 dataset prep, 045 inference, existing training SSE, MLflow run tracking, Jinja2+token CSS. The `TrainingRunService` extraction makes reuse possible where the route previously hid the logic — it is a reuse enabler, not a parallel implementation.
- [x] **Testable** (§11.6) — Each round testable via e2e HTTP (create session → round 1 → inspect → round 2 → verify lineage + `current_base_experiment_id` chain). Unit tests for repository, service, and the extracted `TrainingRunService` (route parity test ensures NMRG).

> Any deviation from the simplest viable solution MUST be recorded in the Complexity Tracking table below (§11.5), or this gate fails.

**Result: PASS with recorded complexity** — the `TrainingRunService` extraction is a justified refactor (see Complexity Tracking). All other gates clear.

## Project Structure

### Documentation (this feature)

```text
docs/vault/Specs/055 Interactive Teaching Loop/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
anvil/                          # Python package
├── db/
│   ├── models/
│   │   ├── teaching_session.py       # NEW: TeachingSession ORM model
│   │   └── teaching_session_status.py # NEW: TeachingSessionStatus StrEnum
│   └── repositories/
│       └── teaching_session_repository.py  # NEW: TeachingSession CRUD
├── services/
│   ├── training/
│   │   └── training_run_service.py   # NEW: TrainingRunService — extracted full
│   │                                 #      training lifecycle (validation, MLflow
│   │                                 #      setup, task, on_complete persistence).
│   │                                 #      Consumed by BOTH route + teaching.
│   └── teaching/                     # NEW: Teaching service domain sub-package
│       ├── __init__.py               # bare docstring (Article VI)
│       └── teaching_service.py       # NEW: Teaching orchestration (uses TrainingRunService)
├── api/
│   ├── v1/
│   │   ├── teach.py                  # NEW: /v1/teach route handlers
│   │   ├── training.py               # UPDATE: route delegates to TrainingRunService
│   │   ├── pages.py                  # UPDATE: add GET /teach page handler
│   │   └── router.py                 # UPDATE: register teach router
│   └── templates/
│       ├── base.html                 # UPDATE: add sidebar entry for Teach
│       └── teach.html                # NEW: Teaching page Jinja2 template
├── workbench.py                      # UPDATE: add `teaching` + `training_runs` properties
tests/
├── unit/
│   ├── db/
│   │   └── test_teaching_session_repository.py  # NEW
│   └── services/
│       ├── test_training_run_service.py         # NEW: parity + persistence
│       └── test_teaching_service.py             # NEW
└── e2e/
    ├── test_training_parity.py       # NEW: existing /training/start behavior unchanged
    └── test_teaching_loop.py         # NEW: HTTP e2e tests for teaching loop
```

**Structure Decision**: Follows the layered architecture (Repository → Service → God Class → Routes). The pivotal change is extracting the training lifecycle from `api/v1/training.py`'s route closure into `services/training/training_run_service.py` — a single new class (one-class-per-file). The existing route becomes a thin delegate; a parity test guarantees NMRG. Teaching gets a `services/teaching/` sub-package. `TeachingRound` needs no ORM model or helper file — it is an MLflow run created by `TrainingRunService` and tagged by `TeachingService`. Both `training_runs` and `teaching` are exposed via `AnvilWorkbench`.

## Complexity Tracking

| Deviation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| **Extract training lifecycle into `TrainingRunService`** (refactor `api/v1/training.py`) | The loadable-model persistence (`data/models/experiment_{id}.json`) + MLflow setup live in a ~200-line route-handler closure. Teaching MUST reuse this exact logic to produce inspectable models. | (a) **Internal HTTP call** to `/v1/training/start` — preserves the wrong layer boundary, hides persistence behind a route, adds an HTTP client dependency for service-to-service calls. (b) **Duplicate the orchestration** in TeachingService — guaranteed to drift; the first thing it will miss is the model-artifact write, silently breaking inspect. Extraction is the only correct reuse path. Guarded by a route-parity test (NMRG). |
| **Chain on native experiment id, not `ExternalModel.id`** | Warm-start (`TrainConfig.base_model_ref`), `InferenceService.load_model()`, and the persisted artifact ALL key on the native experiment id. It is the only model reference training + inference agree on. | An `ExternalModel` FK would require a new experiment_id→ExternalModel registration bridge (none exists — ExternalModel rows are import-only). Building that bridge now cements a bad abstraction rather than simplifying. |

**Deferred (YAGNI — out of MVP, not gaps):**

| Deferred item | Reason | Re-open when |
|---------------|--------|--------------|
| Formal evaluation via 054 (`EvaluationService`) | Requires `ExternalModel.id`; teaching models have only experiment id. MVP "compare" = side-by-side inference between two experiment ids. | Model-identity unification project happens |
| LoRA/adapter teaching rounds | Adapter runs don't persist a loadable `experiment_{id}.json`; LoRAAdapter DB rows aren't auto-created by training. | Adapter persistence + auto-registration exists |
| Imported HF/local model as round-1 seed | An imported ExternalModel has no experiment artifact to warm-start from. | Import-to-native artifact generation exists |
