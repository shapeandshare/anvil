---
created: '2026-06-15T00:00:00.000Z'
tags:
  - type/reference
  - domain/operations
title: MLflow Integration
type: reference
updated: '2026-06-18'
aliases:
  - mlflow-tracking
  - experiment-management
  - mlflow-pipeline
related:
  - '[[Reference/ContentManagementLandscape]]'
---
# MLflow Integration

## Overview

anvil uses MLflow (v3.1+) as the **primary lineage source of truth** (see [[Decisions/ADR-016-mlflow-primary-lineage|ADR-016]]). Every training run, dataset lifecycle event, and model registration is recorded as an MLflow run or registered model version. MLflow replaces the former local SQLite `experiments` and `registered_models`/`model_versions` tables.

MLflow runs as a **managed subprocess** supervised by anvil's `ProcessSupervisor`. It is auto-started when `make run` starts the web server and runs on the configured port (default 5001).

## Architecture

### Before (dual-write)

```
TrainingService
    │
    ├── Reserve run_id
    ├── Load docs
    ├── Resolve device
    │
    ├── Training loop (CPU or GPU backend)
    │     └── progress_callback() → SSE queue → Browser
    │
    └── on_complete callback:
          ├── tracking.TrackingService.log_params()     → MLflow
          ├── tracking.TrackingService.log_metrics()    → MLflow
          ├── tracking.TrackingService.log_model()      → MLflow (artifact)
          ├── tracking.TrackingService.register_model() → MLflow Model Registry
          ├── ExperimentRepository.save()               → local DB
          └── model.json saved to disk                  → data/models/
```

### After (MLflow primary lineage)

```
TrainingService
    │
    ├── Reserve run_id
    ├── Load docs
    ├── Resolve device
    │
    ├── Training loop (CPU or GPU backend)
    │     └── progress_callback() → SSE queue → Browser
    │
    └── on_complete callback:
          ├── set_tag("anvil.status", "finished")       → MLflow
          ├── set_tag("anvil.final_loss", value)        → MLflow
          ├── log_metric("final_loss", value)           → MLflow
          ├── log_artifact("model.json")                → MLflow
          ├── log_artifact("model.safetensors")         → MLflow
          └── register_source_model()                   → MLflow Model Registry

Dataset/Corpus lifecycle events:
    create / import / curate / delete
          └── log_dataset_lifecycle_event()             → MLflow (short-lived run)
    create / fork / ingest / delete
          └── log_corpus_lifecycle_event()              → MLflow (short-lived run)
```

**Key change**: No `ExperimentRepository`, no local `experiments` table. All experiment and model registry data lives in MLflow. Dataset/corpus lifecycle events create short-lived MLflow runs for lineage. The local SQLite (`anvil-state.db`) holds only genuine mutable state (datasets, samples, corpora, training configs).

```text
TrainingService
    │
    ├── allocate_experiment_id()  →  run_id_seq (SQLite)
    ├── Load docs
    ├── Resolve device
    │
    ├── Training loop (CPU or GPU backend)
    │     └── progress_callback() → SSE queue → Browser
    │
    └── on_complete callback:
          ├── tracking.TrackingService.log_params()     → MLflow
          ├── tracking.TrackingService.log_metrics()    → MLflow
          ├── tracking.TrackingService.log_model()      → MLflow (artifact)
          ├── tracking.TrackingService.register_model() → MLflow Model Registry
          └── model.json saved to disk                  → data/models/
```

**Files**:
- `anvil/services/tracking.py` — `TrackingService` (primary MLflow API wrapper)
- `anvil/services/training.py` — `TrainingService` (training orchestrator, fires `on_complete`)
- `anvil/supervisor/` — `ProcessSupervisor` (manages MLflow subprocess lifecycle)

## What Gets Tracked

### Hyperparameters (logged as MLflow params)

| Param | Source |
|-------|--------|
| `n_embd` | Training config |
| `n_head` | Training config |
| `n_layer` | Training config |
| `block_size` | Training config |
| `learning_rate` | Training config |
| `num_steps` | Training config |
| `temperature` | Training config |
| `beta1`, `beta2` | Training config (Adam) |
| `dataset_id` / `corpus_id` | Source data identifier |

### Tags (logged on each MLflow run)

| Tag | Purpose |
|-----|---------|
| `anvil.experiment_id` | Numeric experiment ID for URL bookmark compatibility |
| `anvil.status` | `running` / `finished` / `failed` |
| `anvil.input_digest` | Content hash of training data |
| `anvil.input_role` | `training` or other role |
| `anvil.dataset.vocab_size` | Dataset vocabulary size (enriched on training start) |
| `anvil.dataset.sample_count` | Dataset sample count |
| `anvil.dataset.document_count` | Dataset document count |
| `anvil.corpus.file_count` | Corpus file count |
| `anvil.corpus.language_map` | Corpus language distribution (JSON) |
| `anvil.final_loss` | Final training loss |
| `anvil.error` | Error message on failed runs |

### Metrics (logged at end of run)

| Metric | Source |
|--------|--------|
| `loss` | Final training loss |
| `device` | Device string (cpu/cuda/mps) |
| `elapsed_sec` | Wall-clock training duration |

### System Metrics (optional, periodic)

When GPU monitoring is enabled (requires `nvidia-ml-py` on CUDA or `MPSMetricsCollector` on Apple Silicon):

| Metric | Source |
|--------|--------|
| `gpu_utilization_pct` | GPU compute utilization |
| `gpu_memory_used_mb` | GPU memory consumption |
| `gpu_temperature_c` | GPU temperature |
| `system_cpu_percent` | CPU utilization |
| `system_memory_percent` | RAM utilization |

### Artifacts (logged per run)

| Artifact | Format | Purpose |
|----------|--------|---------|
| `model.json` | JSON | Full model state dict (all weights) |
| `samples.txt` | Text | Generated text samples from trained model |
| `model.safetensors` | Safetensors | HF-compatible weight file |
| `config.json` | JSON | LlamaConfig-compatible config |
| `tokenizer.json` | JSON | Character-level tokenizer metadata |

## Model Registry

MLflow's Model Registry is the **sole** model versioning system. Registration flow:

1. Training completes → `log_model()` uploads artifacts to MLflow
2. `register_source_model()` creates/updates a model version under a name derived from the data source:
   - `dataset-{id}` for dataset-sourced training
   - `corpus-{id}` for corpus-sourced training
   - `default-source` for demo/default training
3. Each version is registered with the MLflow run ID for full traceability
4. The inference endpoint loads models by registry name + version, downloading artifacts from MLflow

**Source-keyed consolidation** (see ADR-005): Models trained from the same data source are grouped under the same registry name, creating a version history for that source. The old local `registered_models`/`model_versions` tables have been removed — the MLflow Model Registry is authoritative.

## Lifecycle Events

In addition to training runs, anvil logs **entity lifecycle events** as MLflow runs:

### Dataset Lifecycle Events

| Event | MLflow Run Tag `anvil.event` | Params Logged |
|-------|------------------------------|---------------|
| Dataset created | `dataset-create` | name, source, vocab_size, sample_count |
| Dataset import | `dataset-import` | format, row_count |
| Dataset curation | `dataset-curate` | operation, removed_count |
| Dataset deletion | `dataset-delete` | — |

### Corpus Lifecycle Events

| Event | MLflow Run Tag `anvil.event` | Params Logged |
|-------|------------------------------|---------------|
| Corpus created | `corpus-create` | file_count, language_map |
| Corpus forked | `corpus-fork` | parent_corpus_id (as tag) |
| Corpus ingest | `corpus-ingest` | file_count, document_count |
| Corpus deletion | `corpus-delete` | — |

All lifecycle events are non-blocking — failures are silently caught. MLflow being down never breaks the API. Each event run is tagged with `anvil.entity_type` (dataset|corpus) and `anvil.entity_id` for queryability.

## Experiment Queries

Experiment listing and detail endpoints (`GET /v1/experiments`, `GET /v1/experiments/{id}`) now query MLflow **only** — the old `ExperimentRepository` and `ExperimentService` have been removed.

- `list_experiments()` uses `MlflowClient.search_runs()` on the `anvil` experiment, ordered by start time DESC
- `get_experiment(id)` searches by `tags.anvil.experiment_id` tag — preserves URL bookmark compatibility for legacy numeric experiment IDs
- Dataset name enrichment happens via a lightweight `DatasetRepository` lookup in the route handler

## Experiment ID Allocation

Since the `experiments` table (with its auto-increment `id` column) has been dropped, new training runs need stable numeric IDs for URL compatibility. A dedicated `run_id_seq` table provides atomic allocation:

```sql
CREATE TABLE run_id_seq (
    next_id INTEGER NOT NULL DEFAULT 1
);
```

On training start, `TrainingService.allocate_experiment_id()` atomically increments via:
```sql
UPDATE run_id_seq SET next_id = next_id + 1 RETURNING next_id - 1 AS allocated_id
```

The allocated integer is stored as the `anvil.experiment_id` tag on the MLflow run — no local DB row needed.

## Lifecycle

### Starting MLflow

```
make run
  │
  └── supervisor.py → ProcessSupervisor
        └── mlflow server --host 127.0.0.1 --port 5001
              --backend-store-uri sqlite:///mlruns/mlflow.db
              --default-artifact-root ./mlruns
```

### Stopping MLflow

```
make stop
  │
  └── ProcessSupervisor → SIGTERM → SIGKILL (after grace period)
```

### External MLflow Server

MLflow can be configured to use an **external** (not locally managed) tracking server:

```bash
export ANVIL_MLFLOW_URI=https://my-mlflow-server.example.com
export ANVIL_MLFLOW_DISABLE_LOCAL=true
```

When `ANVIL_MLFLOW_DISABLE_LOCAL` is set, the ProcessSupervisor skips starting MLflow, and all tracking goes to the external URI.

## URL Resolution

The browser-facing MLflow URL is resolved dynamically from the incoming HTTP request:

```python
def get_mlflow_browser_uri(request: Request) -> str:
    # Uses request's Host header to construct a reachable URL
    # Handles proxies, port mappings, and external servers
```

This ensures the "Open in MLflow" link in the UI works regardless of network topology (see ADR-012).

## Data Flow Diagram

```
┌─────────────┐     Training Config     ┌─────────────────┐
│  Browser UI  │ ──────────────────────► │  TrainingService │
│  (Jinja2)    │                         │                  │
│              │ ◄──── SSE stream ────── │  run_in_executor │
└─────────────┘                         └────────┬─────────┘
                                                  │
                                                  ▼
                                        ┌─────────────────────┐
                                        │   Core Engine       │
                                        │  (train/train_torch)│
                                        └──────────┬──────────┘
                                                   │ on_complete
                                                   ▼
                                        ┌─────────────────────┐
                                        │  TrackingService    │
                                        │                     │
                                        │  log_params()       ├──► MLflow
                                        │  log_metrics()      ├──► MLflow
                                        │  log_model()        ├──► MLflow
                                        │  register_model()   ├──► MLflow Model Registry
                                        │  set_tag()          ├──► MLflow (anvil.* tags)
                                        └─────────────────────┘

┌─────────────┐     Lifecycle Event     ┌─────────────────┐
│  API Route  │ ──────────────────────► │ TrackingService │
│  (datasets, │                         │                 │
│   corpora)  │                         │ log_lifecycle   │
│             │                         │ _event()        ├──► MLflow
└─────────────┘                         └─────────────────┘
```

## See Also

- [[TrainingDataFlow]] — Full training pipeline
- [[SafetensorsExport]] — Model artifact generation
- [[Decisions/ADR-004-mlflow-3x-and-canonical-uri|ADR-004]] — MLflow 3.x migration
- [[Decisions/ADR-005-source-keyed-registry-consolidation|ADR-005]] — Registry consolidation
- [[Decisions/ADR-012-mlflow-browser-url-from-request-host|ADR-012]] — Browser URL resolution
- [[Decisions/ADR-016-mlflow-primary-lineage|ADR-016]] — MLflow primary lineage (removed dual-write)
- [[Decisions/ADR-016-mlflow-primary-lineage|ADR-016]] — MLflow as primary lineage source of truth
