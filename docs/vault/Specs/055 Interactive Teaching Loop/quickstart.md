# Quickstart: Interactive Teaching Loop (055)

> Read research.md §9-§12 and plan.md Complexity Tracking before implementing. The training lifecycle must be extracted into `TrainingRunService` FIRST.

## What It Does

The Interactive Teaching Loop makes "teaching a model" an iterative workflow: add examples → short native fine-tune warm-started from the current checkpoint → inspect outputs → (compare) → repeat. Each round warm-starts from the previous round's **native experiment id** (039). All artifacts are independently accessible outside the teaching context.

**MVP scope**: native full-model teaching. Adapter/LoRA, formal evaluation (054), and imported-model seeds are deferred (see spec Scope).

## Key Concepts

| Concept | What It Is |
|---------|-----------|
| **TeachingSession** | Lightweight DB table — chain container. Holds `current_base_experiment_id` (chain head) + `seed_experiment_id`. Status: Draft → Active → Completed. NO ExternalModel FK. |
| **TeachingRound** | An MLflow run (created via `TrainingRunService`) tagged with teaching metadata + a persisted `data/models/experiment_{id}.json`. Each round = dataset (053) + warm-start training (039) + inspectable outputs (045). |
| **TrainingRunService** | NEW extracted service owning the full training lifecycle (validation → MLflow → run → **model persistence** → registration). Consumed by BOTH `/training/start` and teaching. |

## Files to Create

| File | Purpose |
|------|---------|
| `anvil/db/models/teaching_session_status.py` | TeachingSessionStatus StrEnum |
| `anvil/db/models/teaching_session.py` | TeachingSession ORM model |
| `anvil/db/repositories/teaching_session_repository.py` | TeachingSession CRUD |
| `anvil/services/training/training_run_service.py` | **Extracted** training lifecycle coordinator |
| `anvil/services/teaching/__init__.py` | Package marker (bare docstring) |
| `anvil/services/teaching/teaching_service.py` | Teaching orchestration |
| `anvil/api/v1/teach.py` | `/v1/teach` route handlers |
| `anvil/api/templates/teach.html` | Teaching page Jinja2 template |

## Files to Modify

| File | Change |
|------|--------|
| `anvil/api/v1/training.py` | Route delegates to `TrainingRunService` (behavior preserved) |
| `anvil/api/v1/router.py` | Include `teach_router` |
| `anvil/api/v1/pages.py` | Add `GET /teach` page handler |
| `anvil/api/templates/base.html` | Add "Teach" sidebar entry |
| `anvil/services/datasets/` | Accept + persist `origin` on dataset creation/import |
| `anvil/workbench.py` | Add `training_runs` + `teaching` properties |

## Implementation Order

1. **Setup**: enum + ORM + migration + repository + package scaffold
2. **Extraction (critical)**: write route-parity test → extract `TrainingRunService` → route delegates → re-verify parity (NMRG gate)
3. **Teaching foundation**: TeachingService + dataset origin + `workbench.teaching`
4. **API + Page**: routes, template, sidebar, direct SSE
5. **Tests**: unit (repo, service, TrainingRunService) + e2e (teaching loop + parity)

## Key Integration Points

- Training → `TrainingRunService` (new) — use `workbench.training_runs`. Do NOT call `TrainingService.start_training()` directly (it does not persist the model).
- Warm-start → pass `base_model_ref = session.current_base_experiment_id` into the training config
- Dataset → `DatasetService.create_dataset(origin="teaching")` + `DatasetImportService.commit_docs_import()` — use `workbench.datasets` + `workbench.dataset_import(id)`
- Inference (inspect + compare) → `InferenceService.load_model(experiment_id)` + `.generate()` — use `workbench.inference`
- MLflow tags → `TrackingService.set_tag(mlflow_run_id, key, value)` (check `is_degraded` first) — use `workbench.tracking`
- SSE → frontend connects DIRECTLY to `/v1/training/stream/{run_id}` via `SSESession` from `static/js/sse.js` (no proxy)
- Evaluation (054) → **NOT used in MVP** — compare is side-by-side inference

## Constitution Gates

- No new runtime dependencies
- Simplest viable — TeachingSession one table; TrainingRunService extraction recorded in Complexity Tracking
- NMRG — `/training/start` parity test must stay green
- Layered architecture: Repository → Service → God Class → Routes
- Enums over magic strings (TeachingSessionStatus)
- One class per file

## Quick Command Reference

```bash
make db-revision    # Create migration after adding ORM model
make run            # Start web + MLflow
make test           # Run tests (parity + full suite must pass)
make lint           # Check code quality
make typecheck      # mypy --strict
```
