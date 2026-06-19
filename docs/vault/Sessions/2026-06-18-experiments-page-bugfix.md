---
created: '2026-06-18'
tags:
  - type/session-log
  - domain/tracking
  - domain/mlops
  - domain/ui
title: 'Experiments Page Bugfix — Null IDs, Status Casing, Lifecycle Filter'
type: session
updated: '2026-06-18'
aliases:
  - 2026-06-18-experiments-page-bugfix
source: agent
---
# Session: Experiments Page Bugfix — Null IDs, Status Casing, Lifecycle Filter

**Date**: 2026-06-18

## Summary

Fixed the Experiments page displaying `null` for run IDs, empty status badges, and "—" for dataset names. Diagnosed three root causes in the `TrackingService`/API pipeline and backfilled the existing demo-warmup MLflow run.

## What Was Done

### Root Cause Analysis

1. **Missing `anvil.experiment_id` tag** — The demo-warmup MLflow run had no `anvil.experiment_id` tag, causing `list_experiments()` to return `id: None`. Frontend rendered this as `null` in the ID column and `selectRun(null)` failed silently.

2. **Status case mismatch** — MLflow returns `run.info.status` in UPPERCASE (`FINISHED`, `RUNNING`, `FAILED`). The frontend template at `experiment.html:100` checked `exp.status === 'finished'` (lowercase). No run ever matched.

3. **Lifecycle runs polluting the experiments list** — 39 internal dataset/corpus lifecycle event runs (`log_dataset_lifecycle_event`, `log_corpus_lifecycle_event`) share the same MLflow experiment as training runs. They all have `engine_backend='dataset'` or `'corpus'` and lacked `anvil.experiment_id` tags, so they appeared as null-ID rows.

4. **Timestamp-based ID generation** — `training.py:149` used `int(datetime.now(UTC).timestamp() * 1000)` instead of `allocate_experiment_id()` from the `run_id_seq` table. IDs were non-sequential and not tied to the DB sequence.

5. **`anvil.dataset.name` MLflow tag never set** — Neither the dataset nor corpus branch of the training endpoint set this tag. `list_experiments()` fell back to `params.get("dataset_id")` which returned the numeric ID string (e.g. `"1"`), not a human-readable name.

### Changes Applied

**`anvil/services/tracking.py`**:
- Normalized `run.info.status` to lowercase via `.lower()` in both `list_experiments()` and `get_experiment()`
- Added lifecycle run filter: skip runs where `engine_backend in ("dataset", "corpus")`
- Removed `params.get("dataset_id")` fallback for `dataset_name`

**`anvil/api/v1/training.py`**:
- Replaced timestamp-based ID with `svc.allocate_experiment_id()` (uses `run_id_seq` table)
- Set `anvil.dataset.name` tag for both dataset and corpus training runs

**`anvil/api/v1/experiments.py`**:
- Added `CorpusRepository` lookup in `list_experiments()` enrichment (falls back to corpus name when no dataset_id)
- Added corpus name lookup in `get_experiment()` detail endpoint

**MLflow DB / `run_id_seq` (one-time backfill)**:
- Backfilled `anvil.experiment_id=1` on the demo-warmup run (`3e61d16c...`)
- Advanced `run_id_seq` from (1,1) to (1,2)

### Files Changed

| File | Insertions | Deletions |
|------|-----------|-----------|
| `anvil/services/tracking.py` | 13 | 3 |
| `anvil/api/v1/experiments.py` | 48 | 16 |
| `anvil/api/v1/training.py` | 10 | 6 |

### Verification

- 469 tests pass (8 pre-existing failures unrelated)
- Demo-warmup run now has `id=1`, `status="finished"` (lowercase), `final_loss=2.7812`
- 39 lifecycle runs excluded from experiments list
- Only 2 training runs (`engine_backend='stdlib'` and `'torch'`) appear on the experiments page

## References

- [[005-mlflow-experiment-tracking-implementation]] — context on MLflow tracking architecture
- [[ADR-016-mlflow-primary-lineage]] — MLflow primary lineage decision
- `anvil/services/tracking.py` — `list_experiments()`, `get_experiment()`
- `anvil/api/v1/training.py` — `start_training()` endpoint
- `anvil/api/v1/experiments.py` — experiment list and detail endpoints
- `anvil/api/templates/archetypes/experiment.html` — frontend template
