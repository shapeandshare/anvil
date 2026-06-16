---
title: MLflow Integration
type: reference
tags:
  - type/reference
  - domain/services
created: 2026-06-15
updated: 2026-06-15
aliases:
  - mlflow-tracking
  - experiment-management
  - mlflow-pipeline
---

# MLflow Integration

## Overview

anvil uses MLflow (v3.1+) for experiment tracking and model registry. When training runs, MLflow captures hyperparameters, metrics, model artifacts, and system metrics (GPU utilization, memory) — making every training run auditable and comparable.

MLflow runs as a **managed subprocess** supervised by anvil's `ProcessSupervisor`. It is auto-started when `make run` starts the web server and runs on the configured port (default 5001).

## Architecture

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

**Files**:
- `anvil/services/tracking.py` — `TrackingService` (MLflow API wrapper)
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
| `dataset_name` / `corpus_name` | Source data identifier |

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

MLflow's Model Registry is used to version and track trained models. The registration flow:

1. Training completes → `log_model()` uploads artifacts to MLflow
2. `register_model()` creates a new model version under a name derived from the dataset/corpus:
   - `dataset-{id}` for dataset-sourced training
   - `corpus-{id}` for corpus-sourced training
   - `default-source` for demo/default training
3. Each version is registered with the MLflow run ID for full traceability
4. The inference endpoint (`/v1/inference/sample`) loads models by their registry name + version

**Source-keyed consolidation** (see ADR-005): Models trained from the same data source (dataset or corpus) are grouped under the same registry name, creating a version history for that source.

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

When `ANVIL_MLFLOW_DISABLE_LOCAL` is set, the ProcessSupervisor skips starting MLflow, and all tracking goes to the external URI. This is useful for team deployments where a shared MLflow server is preferred.

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
                                        │  log_params() ──────┼──► MLflow
                                        │  log_metrics() ─────┼──► MLflow
                                        │  log_model() ───────┼──► MLflow
                                        │  register_model() ──┼──► Model Registry
                                        └─────────────────────┘
```

## See Also

- [[TrainingDataFlow]] — Full training pipeline
- [[SafetensorsExport]] — Model artifact generation
- [[Decisions/ADR-004-mlflow-3x-and-canonical-uri|ADR-004]] — MLflow 3.x migration
- [[Decisions/ADR-005-source-keyed-registry-consolidation|ADR-005]] — Registry consolidation
- [[Decisions/ADR-012-mlflow-browser-url-from-request-host|ADR-012]] — Browser URL resolution