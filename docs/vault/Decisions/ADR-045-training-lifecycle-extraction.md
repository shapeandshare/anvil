---
title: 'ADR-045: Training Lifecycle Extraction — TrainingRunService for Reusable Orchestration'
type: decision
tags:
  - type/decision
  - domain/training
  - domain/training
status: draft
code-refs:
  - anvil/services/training/training_run_service.py
  - anvil/services/training/training_run_config.py
  - anvil/api/v1/training.py
  - anvil/workbench.py
created: '2026-07-02'
updated: '2026-07-02'
aliases:
  - ADR-045
  - training-lifecycle-extraction
source: 'Spec 055 Interactive Teaching Loop'
---

# ADR-045: Training Lifecycle Extraction — TrainingRunService for Reusable Orchestration

## Status

Draft

## Context

The `POST /training/start` route handler in `anvil/api/v1/training.py` contained the full training lifecycle (~700 lines), including hyperparameter validation, compute backend resolution, MLflow run setup, async task creation, and a ~200-line `on_complete` closure that wrote the loadable model artifact (`data/models/experiment_{id}.json`). The `TrainingService.start_training()` method only handled document loading and backend dispatch — it did NOT persist a loadable model.

Spec 055 (Interactive Teaching Loop) needed to produce loadable models from teaching rounds. Three reuse strategies were considered:

1. **Internal HTTP call** to `POST /training/start` — preserves the wrong layer boundary, hides persistence behind a route, adds HTTP client dependency.
2. **Duplicate the orchestration** in `TeachingService` — guaranteed to drift; the first thing it would miss is the model-artifact write.
3. **Extract** the lifecycle into a reusable service-layer class consumed by both the route and teaching.

## Decision

Extract the training lifecycle into `TrainingRunService` at `anvil/services/training/training_run_service.py`. Key properties:

- **Single public method** `start_training_run()` that handles validation → MLflow setup → async task creation → model persistence → MLflow registration.
- **Helper methods**: `_validate_hparams`, `_validate_method`, `_validate_warm_start`, `_resolve_training_backend`, `_estimate_memory`, `_setup_mlflow_run`, `_log_dataset_metadata`, `_on_complete` — all extracted from the route handler.
- **Config** via `TrainingRunConfig` Pydantic model (mirrors `TrainConfig` fields but lives in the service layer, not the HTTP layer).
- **Task tracking** via a shared `_tasks: dict[int, asyncio.Task]` dict, enabling the SSE stream handler to check if a run is still active.
- **Route becomes a thin delegate**: parses the HTTP request, converts `TrainConfig` → `TrainingRunConfig`, calls the service, returns the response.

A **route-parity test** (`tests/e2e/test_training_parity.py`) was written BEFORE the refactor and verified to pass on the original code. After extraction, the same test confirms the route's observable behavior (response shape, MLflow tags, model artifact path) is identical. The test is permanently part of the test suite.

## Consequences

**Easier:**
- Teaching can now produce loadable models without duplicating or HTTP-calling the training route.
- The extracted methods are testable in isolation (unit tests in `tests/unit/services/test_training_run_service.py`).
- Future consumers of the training lifecycle (e.g. CLI, scheduled jobs) can call `TrainingRunService` directly.
- Route file went from ~1236 lines to ~415 lines.

**Harder:**
- The extraction required updating ~300 lines of existing unit tests (`tests/unit/api/v1/test_training.py`) to patch the service-level imports instead of route-level imports.
- The `on_complete` closure captures several route-local variables (`mlflow_run_id`, `run_id`, `experiment_id`, `dataset_id`, `corpus_id`); these are now instance state on `TrainingRunService`.

**Not changed:**
- No observable change to `POST /training/start` behavior (NMRG verified by parity test).
- `TrainingService.start_training()` unchanged — it remains the low-level executor.
- No new runtime dependencies.

## Compliance

- Route-parity test (`tests/e2e/test_training_parity.py`) must pass on every commit that touches the training route or service.
- `TestTrainingStart` in `tests/unit/api/v1/test_training.py` must continue to pass.

## See Also

- [[Decisions/README|Decisions]]
- [[Specs/055 Interactive Teaching Loop/spec|055 Interactive Teaching Loop spec]]
