---
created: '2026-06-18'
tags:
  - type/decision
  - domain/mlops
  - domain/architecture
title: MLflow as Primary Lineage Source of Truth
type: decision
updated: '2026-06-18'
aliases:
  - ADR-016
  - MLflow Primary Lineage
source: agent
code-refs:
  - anvil/services/tracking/tracking_service.py
  - anvil/db/models/training_config.py
  - anvil/services/inference/inference_service.py
  - anvil/db/repositories/experiments.py
---
# ADR-016: MLflow as Primary Lineage Source of Truth

## Status
Accepted

## Context

Anvil currently maintains **redundant** experiment and model registry state in two places:

1. **Local SQLite DB** (`anvil.db`): `experiments`, `registered_models`, `model_versions` tables — accessed via `ExperimentRepository`, `ModelRepository`, `ExperimentService`, `ModelRegistryService`.
2. **MLflow**: Runs, params, metrics, tags, artifacts, and the Model Registry.

This dual-path architecture has accumulated technical debt:

- Every experiment read (`GET /v1/experiments`, `GET /v1/experiments/{id}`) requires a local DB query AND an MLflow query — inconsistent response shapes when the two drift.
- Every write (training start, finish, model registration) writes to both stores — one can silently fail while the other succeeds.
- The local `Experiment` table duplicates MLflow run metadata (run_name, status, final_loss, engine_backend, device, etc.) — MLflow already stores all of this.
- The local `registered_models`/`model_versions` are a partial cache of the MLflow Model Registry — stale by design since model registration goes through MLflow.
- `ExperimentRepository.find_orphaned()` queries a local Boolean flag (`status == "running"`) that isn't atomically updated — it detects MLflow-side orphans only by coincidence.
- `ModelRegistryService` has a `migrate_local_registry_to_mlflow()` method proving the team already knows the local tables are legacy.

Meanwhile, the remaining SQLite tables (`datasets`, `samples`, `curation_operations`, `corpora`, `training_configs`) are **genuine mutable state** that MLflow cannot model — they stay.

## Decision

**Remove the local `experiments`, `registered_models`, and `model_versions` tables. All experiment and model registry queries go through MLflow directly.**

### What is removed

| Component | Replacement |
|-----------|-------------|
| `anvil/db/models/training_config.py`: `Experiment` ORM class | Deleted — metadata lives as MLflow tags + params on runs |
| `anvil/db/models/registry.py`: `RegisteredModel`, `ModelVersion` ORM classes | Deleted — MLflow Model Registry is authoritative |
| `anvil/db/repositories/experiments.py`: `ExperimentRepository` | Deleted — all queries through `MlflowClient.search_runs()` |
| `anvil/db/repositories/models.py`: `ModelRepository` | Deleted — all queries through `MlflowClient.search_registered_models()` |
| `anvil/services/models.py`: `ModelRegistryService` | Deleted — `TrackingService.register_source_model()` calls MLflow directly |
| `anvil/services/experiments.py`: `ExperimentService` | Deprecated — `TrackingService.list_experiments()` / `get_experiment()` cover the same surface |
| Alembic migration `013`: `experiments`, `registered_models`, `model_versions` tables | Dropped in migration |

### What is added

| Component | Purpose |
|-----------|---------|
| `anvil/db/models/training_config.py`: `run_id_seq` table | Atomic numeric experiment ID allocation (single-row counter: `UPDATE run_id_seq SET next_id = next_id + 1 RETURNING next_id`) |
| `TrackingService.list_experiments()` | Query MLflow runs for the `anvil` experiment, filtered/sorted, returned in the same shape as the old DB-backed endpoint |
| `TrackingService.get_experiment()` | Find a single MLflow run by its `anvil.experiment_id` tag — preserves URL bookmark compatibility |
| `TrackingService.log_dataset_lifecycle_event()` | Non-blocking MLflow run for dataset create/import/curate/delete events |
| `TrackingService.log_corpus_lifecycle_event()` | Non-blocking MLflow run for corpus create/fork/ingest/delete events |

### How numeric experiment IDs work

Training endpoints generate experiment IDs from `run_id_seq` (not auto-increment). The ID is stored as the `anvil.experiment_id` tag on the MLflow run. `GET /v1/experiments/{id}` searches by this tag — no local DB lookup needed.

### Lifecycle event runs

Dataset and corpus operations create short MLflow runs tagged with `anvil.entity_type` and `anvil.event`. These are purely for lineage — every create/import/curate/delete action is recorded as an MLflow run with relevant params. Failures are silently caught; MLflow being down never breaks the API.

### Inference model loading

`InferenceService.load_model()` uses two paths:
1. **Local fallback**: `data/models/experiment_{experiment_id}.json` for legacy artifacts
2. **MLflow primary**: `MlflowClient.download_artifacts()` from the Model Registry for newer models

This ensures backward compatibility with pre-migration saved models while moving all new registrations to MLflow-only.

## Consequences

**Easier:**
- Single source of truth for experiment data — MLflow runs with full tag/param/metric history
- No DB-MLflow drift — all writes go through MLflow, the local DB is genuine mutable state only
- `reconcile_orphans()` runs entirely via `MlflowClient.search_runs()` — no `ExperimentRepository` dependency
- `list_experiments()` returns richer data (params, metrics, tags) that the old DB-backed endpoint couldn't provide
- Model registry CRUD goes through `MlflowClient` — version deletion and model deletion work on MLflow directly
- Simpler testing — `TrackingService` can be mocked at the `MlflowClient` boundary instead of mocking both DB and MLflow

**Harder:**
- MLflow being down means the experiments page goes into degraded mode — acceptable (already existed via `TrackingService.is_degraded`)
- Migration script must run BEFORE deployment to copy existing data from old tables into MLflow
- `anvil.experiment_id` tag lookup is slower than a primary key lookup — mitigated by pagination and the fact that experiment pages load once per navigation
- Inference loading from MLflow requires artifact download (network I/O) — mitigated by two-phase loading: try local first, fall back to MLflow

**Explicitly preserved:**
- `training_configs` table — these are reusable config templates, not a cache of MLflow data (see ADR-015 evaluation)
- `datasets`, `samples`, `curation_operations`, `corpora`, `corpus_files` — genuine mutable state MLflow cannot model

## Compliance

1. `migrations/scripts/migrate_to_mlflow_primary.py` exits 0 with all experiments migrated
2. Alembic migration `013` drops `experiments`, `registered_models`, `model_versions` tables clean
3. `GET /v1/experiments` returns runs from MLflow only — no DB-backed queries
4. `GET /v1/experiments/{id}` with legacy experiment IDs returns the correct MLflow run via `anvil.experiment_id` tag lookup
5. `POST /v1/training/start` with dataset/corpus → MLflow run has `anvil.dataset.*` or `anvil.corpus.*` tags
6. `DELETE /v1/datasets/{id}` → MLflow run appears with `anvil.event=dataset-delete`
7. Inference load_model works for both legacy local artifacts and MLflow Model Registry models
8. `grep -r 'ExperimentRepository' anvil/` returns zero results
9. `grep -r 'ModelRepository' anvil/` returns zero results
10. `grep -r 'ModelRegistryService' anvil/` returns zero results

## See Also
- [[Decisions/README|Decisions]]

- [[Reference/MlflowIntegration]] — Updated MLflow architecture for primary lineage
- [[Decisions/ADR-004-mlflow-3x-and-canonical-uri|ADR-004]] — MLflow 3.x migration
- [[Decisions/ADR-005-source-keyed-registry-consolidation|ADR-005]] — Source-keyed registry consolidation
- [[Decisions/ADR-009-mlflow-pyfunc-model-compliance|ADR-009]] — MLflow PyFunc model compliance
- [[Decisions/ADR-014-ml-infrastructure-tier-strategy|ADR-014]] — ML infrastructure tier strategy
