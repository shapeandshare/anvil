---
created: '2026-06-18'
tags:
  - type/session-log
  - domain/mlops
  - domain/architecture
title: MLflow Primary Lineage Implementation
type: session
updated: '2026-06-18'
---
# Session: MLflow Primary Lineage Implementation

**Date**: 2026-06-18

## Summary

Implemented the MLflow Primary Lineage plan (Phases 1–2) — removed redundant local SQLite experiment and model registry tables, migrated all consumers to query MLflow directly, added dataset/corpus lifecycle event tracking, and consolidated the inference model loading path.

## What Was Done

### Database Layer
- Removed `Experiment`, `RegisteredModel`, `ModelVersion` ORM models
- Deleted `ExperimentRepository`, `ModelRepository`
- Added Alembic migration `013` dropping `experiments`, `registered_models`, `model_versions` tables
- Added `run_id_seq` table for atomic numeric experiment ID allocation
- Added one-shot data migration script `migrations/scripts/migrate_to_mlflow_primary.py`

### Service Layer
- Deleted `ModelRegistryService` (`anvil/services/models.py`)
- Deprecated `ExperimentService` (`anvil/services/experiments.py`) — replaced by `TrackingService`
- Enhanced `TrackingService`:
  - `list_experiments()` — queries MLflow runs for the `anvil` experiment, paginated, with dataset name enrichment
  - `get_experiment()` — finds a single run by `anvil.experiment_id` tag lookup
  - `log_dataset_lifecycle_event()` — non-blocking MLflow run for dataset CRUD lineage
  - `log_corpus_lifecycle_event()` — non-blocking MLflow run for corpus lifecycle lineage
  - Removed orphan reconciliation code path referencing `ExperimentRepository`
  - Updated `list_registered_models()` to remove local DB experiment_id lookup
- Updated `InferenceService.load_model()` — two-phase loading: local artifact first, MLflow download fallback
- Added `TrainingService.allocate_experiment_id()` — `run_id_seq`-based ID generation

### API Layer
- Rewrote all 10 experiment endpoints to use `TrackingService` + `MlflowClient` (no `ExperimentRepository`/`ExperimentService` dependency)
- Rewrote all registry endpoints to accept string model names (MLflow) or int IDs (dataset-{id}/corpus-{id} convention), all CRUD through `MlflowClient`
- Training flow: replaced `ExperimentRepository.create_running()`/`mark_finished()`/`mark_failed()` with MLflow run tags
- Dataset/corpus lifecycle event hooks on create, import, curate, clone, delete
- Inference model loading consolidated through `InferenceService.load_model()`

### CLI / Config
- Removed experiment/registry CLI commands
- Config cleanup for MLflow-only path

### Tests
- Deleted 7 legacy test files for removed repos and services
- Updated 5 test files to use `TrackingService` MLflow-based response shapes and mocks

## Key Decisions

| Decision | Rationale |
|----------|-----------|
| Timestamp-based experiment IDs (fallback) when `run_id_seq` unavailable | Prevents training from failing if DB migration hasn't run yet |
| Non-blocking lifecycle hooks (try/except pass) | MLflow being down should never break dataset CRUD operations |
| Two-phase inference model loading (local → MLflow) | Backward compatibility with pre-migration saved artifacts |
| Lifecycle events logged as MLflow runs (not tags on existing runs) | Clean separation of concerns — each entity event is independently queryable |

## Files Changed

- `anvil/db/models/__init__.py`, `registry.py`, `training_config.py`
- `anvil/db/repositories/__init__.py`, `experiments.py` (del), `models.py` (del)
- `anvil/services/__init__.py`, `experiments.py`, `models.py` (del), `tracking.py`, `training.py`, `inference.py`, `datasets.py`
- `anvil/api/v1/experiments.py`, `registry.py`, `training.py`, `datasets.py`, `corpora.py`, `eval.py`, `router.py`
- `anvil/cli.py`, `anvil/config.py`
- `migrations/versions/013_drop_experiment_registry_tables_add_run_id_seq.py`
- `migrations/scripts/migrate_to_mlflow_primary.py`
- 12 test files (7 deleted, 5 updated)

## Vault Enrichments

- Created [[Decisions/ADR-016-mlflow-primary-lineage|ADR-016: MLflow as Primary Lineage Source of Truth]]
- Updated [[Reference/MlflowIntegration]] — removed ExperimentRepository/DB references, updated diagrams
- Updated [[Reference/ArchitectureOverview]] — step 7.2 no longer references ExperimentRepository
- Updated [[Reference/TrainingDataFlow]] — completion section no longer mentions DB INSERT Experiment
- Updated [[Reference/DecisionLog]] — added ADR-016 entry

## See Also

- [[Decisions/ADR-016-mlflow-primary-lineage|ADR-016]] — Full architecture decision record
- [[Reference/MlflowIntegration]] — Updated MLflow tracking reference
