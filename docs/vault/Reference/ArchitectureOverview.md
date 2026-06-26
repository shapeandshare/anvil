---
title: Architecture & Data Flow Overview
type: reference
tags:
  - type/reference
  - domain/architecture
created: 2026-06-15T00:00:00.000Z
updated: '2026-06-18'
aliases:
  - architecture-overview
  - system-architecture
  - layered-architecture
related:
  - '[[Systems/Systems]]'
  - '[[Reference/InfraParadigms]]'
  - '[[Reference/linting-and-testing-tooling]]'
  - '[[Reference/stale-learning-content-llama-migration]]'
  - '[[Reference/ContentManagementLandscape]]'
  - '[[Reference/DecisionLog]]'
  - '[[Reference/overflow-clipping-pattern]]'
---

# Architecture & Data Flow Overview

## System Architecture

anvil follows a strict **layered architecture** with four tiers:

```
┌──────────────────────────────────────────────────────────────┐
│                    Presentation Layer                         │
│  Jinja2 Templates      Vanilla JS Widgets    CSS Design Sys  │
│  (archetypes/*.html)   (js/widgets/*.js)     (css/tokens.css)│
└──────────────────────────┬───────────────────────────────────┘
                           │ HTTP / SSE
┌──────────────────────────▼───────────────────────────────────┐
│                      API Layer (v1 Router)                    │
│  FastAPI APIRouter → Route handlers → TemplateResponse/JSON  │
│  anvil/api/v1/router.py + sub-routers                        │
└──────────────────────────┬───────────────────────────────────┘
                           │
┌──────────────────────────▼───────────────────────────────────┐
│                    Service Layer                              │
│  TrainingService   TrackingService   CorpusService            │
│  DatasetService    ExportService     InferenceService         │
│  anvil/services/*.py                                          │
└──────────────────────────┬───────────────────────────────────┘
                           │
┌──────────────────────────▼───────────────────────────────────┐
│                 Repository / Data Layer                       │
│  DB Repositories (async SQLAlchemy)    FileStore (local/S3)  │
│  anvil/db/repositories/*.py            anvil/storage/*.py    │
└──────────────────────────┬───────────────────────────────────┘
                           │
┌──────────────────────────▼───────────────────────────────────┐
│                      Core Engine                              │
│  LlamaModel     Autograd (Value)     Tokenizer                │
│  train()        train_torch()         export_state_dict()     │
│  anvil/core/*.py  (zero pip deps for CPU path)               │
└──────────────────────────────────────────────────────────────┘
```

### Layer Discipline Rules

1. **Repository → DB only**: No business logic in repositories. Pure data access.
2. **Service → Repository**: Services consume repositories. One service per domain concept.
3. **God Class → Service**: `AnvilWorkbench` exposes all service methods. Routes and CLI call only the God Class.
4. **No shortcuts**: Routes never call repositories directly. Core engine never imports from services.
5. **Async throughout**: Web, DB, storage layers are async (`asyncio`). Core engine is sync (the exception — runs in thread pool).

## Data Flow: Training Request

### High-Level Flow

```
Browser                 FastAPI               TrainingService         Core Engine
   │                       │                       │                     │
   │  POST /v1/training/   │                       │                     │
   │  start {config}       │                       │                     │
   │──────────────────────►│                       │                     │
   │                       │  reserve_run()        │                     │
   │                       │  create_task(         │                     │
   │                       │    start_training)    │                     │
   │                       │──────────────────────►│                     │
   │                       │                       │  _load_docs()       │
   │                       │                       │───────┬─────────────┤
   │                       │                       │       │ (db/filesys)│
   │                       │                       │◄──────┘             │
   │                       │                       │  resolve_device()   │
   │                       │                       │  train() or         │
   │                       │                       │  train_torch()      │
   │                       │                       │  run_in_executor()  │
   │                       │                       │────────────────────►│
   │                       │                       │                     │
   │  SSE /v1/training/    │                       │                     │
   │  stream {run_id}      │◄────── SSE queue ────│◄── progress_cb() ──│
   │◄──────────────────────│                       │                     │
   │  event: metrics       │                       │                     │
   │  event: complete      │                       │  on_complete()      │
   │                       │                       │────┬────┬────┬─────┤
   │                       │                       │    │    │    │     │
   │                       │                       │  MLflow  DB  Disk  │
```

### Detailed Step-by-Step

#### 1. Browser → API
- User configures hyperparameters in the Training Dashboard UI
- POST to `/v1/training/start` with config JSON
- FastAPI route handler delegates to `TrainingService.start_training()`

#### 2. API → TrainingService
- `reserve_run()` allocates a run_id, creates SSE queue and stop event
- `start_training()` creates an `asyncio.create_task()` for the training coroutine
- Returns immediately with `run_id` so the browser can subscribe to the SSE stream

#### 3. TrainingService → Data Layer
- Loads training documents from the configured source:
  - **Dataset**: Uploaded `.txt` file via `DatasetService.load_docs()`
  - **Corpus**: Directory scan with gitignore filtering via `CorpusService.load_docs()`
  - **Default**: Demo corpus via `DemoBootstrapService`
- All data loading runs in a thread pool (`run_in_executor`) to avoid blocking the event loop

#### 4. TrainingService → Core Engine
- Resolves compute device: CUDA > MPS > CPU
- Dispatches to the appropriate backend:
  - **CPU**: `train()` in `anvil/core/engine.py` (pure Python, Value autograd)
  - **GPU**: `train_torch()` in `anvil/core/torch_engine.py` (PyTorch tensors)
- Both run in a thread pool via `run_in_executor(None, lambda: train(...))`

#### 5. Core Engine → TrainingService (real-time)
- The progress callback fires every step:
  ```python
  progress_callback(step, loss.data)
  ```
- Runs in the thread executor thread → uses `asyncio.run_coroutine_threadsafe()` to push events into the asyncio Queue
- Events include: step number, loss, steps/sec, ETA, device

#### 6. TrainingService → Browser (SSE)
- The SSE endpoint `/v1/training/stream/{run_id}` reads from the same Queue
- Events are sent as SSE `event:` frames:
  - `event: metrics` — step/loss/progress every step
  - `event: optimizer_state` — per-step optimizer snapshots (every `optimizer_snapshot_interval` steps)
  - `event: complete` — final loss + generated samples
  - `event: error` — training error (e.g., StopRequested)

#### 7. TrainingService → Persistence (`on_complete`)
After training finishes, `on_complete` fires (in order):

1. **MLflow Tracking** (`TrackingService`):
   - `set_tag()` — anvil.experiment_id, anvil.status, anvil.final_loss, anvil.input_digest, dataset/corpus metadata tags
   - `log_params()` — all hyperparameters (dataset_id, corpus_id, engine_backend, device)
   - `log_metrics()` — final loss, device, elapsed time
   - `log_model()` — upload model.json + samples.txt as artifacts
   - `register_source_model()` — create/update model registry version via MLflow Model Registry

2. **Disk**:
   - Save `data/models/experiment_{experiment_id}.json` for inference loading
   - Safetensors export (if available): `model.safetensors`, `config.json`, `tokenizer.json`

## Data Flow: Inference

```
POST /v1/inference/sample  {model_id, version, temperature, num_samples, prompt, top_k, top_p}
  │
  ├── InferenceService.load_model(model_id, version)
  │     ├── Phase 1: Try local artifact data/models/experiment_{id}.json
  │     ├── Phase 2: Fall back to MLflow Model Registry download
  │     │            (MlflowClient.download_artifacts by run_id)
  │     └── Return LoadedModel(model, chars, model_id, cache_key, name)
  │
  └── Autoregressive sampling:
        ┌─────────────────────────────────────────┐
        │  For each sample:                       │
        │    token = BOS (or prompt[0])           │
        │    For pos in range(block_size):        │
        │      logits = model.forward(...)         │
        │      scaled = logits / temperature       │
        │      Apply top-K / top-P filtering       │
        │      probs = softmax(scaled)             │
        │      token = sample(probs)               │
        │      if token == BOS: break              │
        └─────────────────────────────────────────┘
```

## Data Flow: Learning Walkthroughs

```
GET /v1/learn/{topic}
  │
  └── TemplateResponse("archetypes/concept.html", {"steps": STEPS, ...})
        │
        └── concept.html renders:
              ├── Step navigation (prev/next via arc)
              ├── Step content (title + body HTML)
              └── Widget container (JS initializes widget by name)
                    │
                    └── JS widget loads model data via /v1/inference/models
                        or uses MLflow API for experiment data
```

## Reference Notes

- [[UserRequirements]] — Project charter and user requirements
- [[design-divergence-resolution]] — Design divergence resolution history
- [[ui-link-conventions]] — UI link and button conventions
- [[wizard-tabs-pattern]] — Wizard tabs reuse pattern

## See Also

- [[TrainingDataFlow]] — Detailed training loop with ASCII diagram
- [[Decisions/ADR-002-sync-core-async-bridge|ADR-002]] — Why core engine is sync inside async web layer
- [[Glossary]] — Value, FileStore, Repository, God Class definitions
- [[SafetensorsExport]] — Model artifact pipeline
- [[DualBackend]] — CPU vs GPU training bridge
