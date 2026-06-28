---
title: 039 Model Warm-Start - research
type: spec
tags:
  - type/spec
  - domain/training
  - domain/core
status: draft
created: '2026-06-28'
updated: '2026-06-28'
---

# Research: Model Warm-Start & Run Lineage

## Architecture Summary

### Compute Layer (config dict pipeline)

The compute layer uses a `config: dict[str, Any]` pipeline that flows from `TrainingService.start_training()` → `resolve_backend()` → `backend.run()`. No protocol changes needed — `base_model_ref` passes as a plain config key, exactly like the existing `config["device"] = device` injection at line 531 of `training.py`.

```
TrainingService.start_training(config)
    ├─ config["device"] = device          # existing injection point
    ├─ config["base_model_ref"] = ref     # NEW injection point
    ├─ resolve_backend(config) → { engine, device, backend }
    ├─ get_backend("local-stdlib"|"local-torch"|"modal")
    └─ backend.run(docs, config, progress_callback, stop_check)
```

**Key files**:
- `anvil/services/compute/protocol.py` — `ComputeBackendProtocol.run(config: dict[str, Any])` — no change needed
- `anvil/services/compute/result.py` — `ComputeResult(status, model, final_loss, samples, ...)` — no change needed
- `anvil/services/compute/local_stdlib_backend.py` — reads config keys, passes to `engine.train()`
- `anvil/services/compute/local_torch_backend.py` — reads config keys, passes to `train_torch()`

### Engine Layer

**Stdlib engine** (`anvil/core/engine.py`):
- `train(docs, model=None, ...)` — accepts a model object BUT is **NOT warm-start-safe** (Oracle-confirmed bug)
- **Latent bug**: even when `model` is passed, `train()` rebuilds `uchars = sorted(set("".join(docs)))`,
  `BOS = len(uchars)`, `vocab_size = len(uchars) + 1` from the NEW docs, and the training loop still uses
  the function's `block_size` parameter. Consequences: (1) token-ID drift — `uchars.index(ch)` produces
  IDs that don't match the base model's learned embeddings; (2) matrix overflow — if the new corpus has
  more unique chars, `vocab_size` exceeds the base model's `wte`/`lm_head` dimensions.
- **Fix required (FR-002a)**: in the `model is not None` branch, derive `uchars` from `model.chars`
  (exact order, no re-sort), `vocab_size` from `model.vocab_size`, `BOS` from `len(model.chars)`, and
  `block_size` from `model.block_size`; fail-fast on OOV chars.
- `LlamaModel.load(path)` — classmethod to deserialize from JSON checkpoint; sets `model.chars`
- `LlamaModel.save(path, chars)` — serializes to JSON including `chars`
- `model.chars` is the authoritative vocabulary; `model.vocab_size == len(model.chars) + 1`

**Torch engine** (`anvil/services/training/torch_engine.py`):
- `train_torch(docs, device="cpu", ...)` — **no `model=` parameter yet** — this is the FR-002 parity gap
- Always creates a new `TorchLlamaModel` from scratch
- `TorchLlamaModel` mirrors the stdlib `LlamaModel` architecture with PyTorch tensors
- `TorchLlamaModel.export_weights()` — returns dict of plain Python lists
- `train_torch()` returns `(exported_weights, final_loss, samples, uchars)` — different return shape than stdlib `train()`

### Model Registry & Checkpoint Resolution

**The model registry is MLflow-backed** — there is no anvil SQL table for models. Models are stored as MLflow `registered_models` with `model_versions`.

Registration flow (`on_complete` in `training.py`):
1. Model saved to `data/models/experiment_{experiment_id}.json` (line ~782) AND logged to MLflow as `runs:/{run_id}/model.json`
2. `TrackingService.register_source_model()` creates MLflow registered model + version
3. Model detail served via MLflow API queries reading `run.data.tags`

**Checkpoint resolution path (reuse — do NOT reinvent)**: `InferenceService.load_model(model_id)` in
`anvil/services/inference/inference.py` (line ~132) is the canonical resolver:
1. Primary: `data/models/experiment_{model_id}.json` → `LlamaModel.load()`
2. Fallback: MLflow registry artifact download (`dataset-{id}`/`corpus-{id}`/`demo`) → `model.json`
3. Returns a `LoadedModel` with the `LlamaModel` and its `chars`
4. Raises `ValueError` if not found — maps cleanly to HTTP 422

**Lineage storage decision (corrected)**: Lineage stored as **MLflow run tags** (NOT version tags),
set via the existing `set_tag()` in `on_complete` alongside the `architectures` tag:
- `anvil.warm_start` → `"true"`
- `anvil.base_model_ref` → experiment ID string
- `anvil.specialization_corpus` → corpus/dataset name

Run tags (not version tags) because the read path (`list_registered_models`, `get_model`) reads
`run.data.tags` via `client.get_run(run_id)`.

**Key files**:
- `anvil/api/v1/registry.py` — registry API routes (resolve `model_id` → MLflow name; read `run.data.tags`)
- `anvil/services/tracking/tracking.py` — `register_source_model()`, `list_registered_models()`, `set_tag()`
- `anvil/services/inference/inference.py` — `InferenceService.load_model()` (checkpoint resolver to reuse)
- `anvil/client/registry/registered_model.py` — SDK DTO

### UI Layer

**Model detail page** (`anvil/api/templates/archetypes/model_detail.html`):
- Shows model info with versions table
- Existing action button pattern: `<a id="md-play-link" href="/v1/inference-page?model_id={id}">Play</a>`
- **Pattern to follow**: Add "Continue Training" button with `href="/v1/training-page?base_model_ref={model_id}"`

**Training page** (`anvil/api/templates/archetypes/training.html`):
- Hyperparameter form: n_embd, n_layer, n_head, block_size, num_steps, learning_rate, temperature
- `startTraining()` reads form values → `POST /v1/training/start`
- `attachExperiment()` pre-fills form from experiment data — **reuse this pattern for warm-start pre-fill**
- On page load: check URL params via `core.getUrlParams()`

**TrainConfig** (`anvil/api/v1/training.py`, ~line 54-108):
- Pydantic model with all hyperparameter fields
- No `base_model_ref` field currently — must be added

**SSE pipeline** (already exists, no changes needed for FR-004):
- `GET /v1/training/stream/{run_id}` — SSE endpoint
- `sse.js` — `SSESession` class, handles metrics/complete/error events

## Decisions

### Decision: Fix stdlib engine vocabulary inheritance (FR-002a) — NEW, from Oracle review

- **Decision**: Fix `engine.train(docs, model=...)` so the warm-start branch derives `uchars`/`BOS`/
  `vocab_size`/`block_size` from the base model (using `model.chars` exact order), and fail-fast on OOV
  chars. From-scratch path unchanged.
- **Rationale**: Oracle confirmed the current `train(model=...)` is only superficially warm-start-capable
  — it reuses weights but rebuilds vocab from new docs, corrupting token IDs and risking matrix overflow.
  The spec's original "already supports warm-start" claim was false. FR-001a (vocabulary inheritance)
  cannot be satisfied without this fix.
- **Alternatives considered**: (a) Auto-union vocab + resize `wte`/`lm_head` matrices — heavier semantics,
  more failure modes, deferred to a future `resize_vocab()` feature (YAGNI). (b) Silently skip OOV chars
  — corrupts the corpus and hides data loss (rejected). Chosen: reuse base vocab, reject OOV.

### Decision: Reuse `InferenceService.load_model()` for checkpoint resolution — NEW

- **Decision**: Resolve `base_model_ref` (int experiment ID) → `LlamaModel` via the existing
  `InferenceService.load_model(model_id)`.
- **Rationale**: That method already implements the full resolution chain (local file → MLflow fallback)
  and returns a `LoadedModel` with `chars`. Reuse-first (Article XI). Avoids duplicating path logic.
- **Alternatives considered**: Hand-rolling `data/models/experiment_{id}.json` loading in the backend —
  duplicates existing logic and misses the MLflow fallback.

### Decision: Lineage stored as MLflow run tags (corrected from version tags)

- **Decision**: Store lineage (`anvil.base_model_ref`, `anvil.specialization_corpus`, `anvil.warm_start`)
  as MLflow **run** tags via the existing `set_tag()` in `on_complete`.
- **Rationale**: The model registry is MLflow-backed, not a SQL table. The read path
  (`list_registered_models`, `get_model`) reads `run.data.tags` via `client.get_run(run_id)` — so run
  tags are immediately visible with no new query. `set_tag()` already exists and handles degraded mode.
- **Alternatives considered**: (a) A new `ModelLineage` SQL table — adds a table/repo/service for a
  key-value store MLflow already provides (YAGNI). (b) Model *version* tags — not on the existing read
  path; would need a new query. (c) A new `record_warm_start_lineage()` service method — three `set_tag()`
  calls are simpler (Reuse-first).

### Decision: `base_model_ref` is a plain config dict key

- **Decision**: `base_model_ref` flows through the existing `config: dict[str, Any]` pipeline — no new protocol, enum, or result type.
- **Rationale**: The compute layer already forwards the full config dict to `backend.run()`. Because `base_model_ref` originates in `TrainConfig` (the API config), it reaches the backend automatically via `config.model_dump()` — unlike `device`, which is *resolved* and injected at line ~531. No explicit injection or protocol change needed. The backend reads `config.get("base_model_ref")`.
- **Alternatives considered**: Adding `base_model_ref` as a typed field on `ComputeBackendProtocol.run()` — would require updating every backend implementation and the protocol definition. Unnecessary complexity for a single optional parameter.

### Decision: `model=` parameter on `train_torch()`

- **Decision**: Add `model: TorchLlamaModel | None = None` to `train_torch()`. When present, reuse the model's params and inherit vocab/dims/block_size (mirroring the stdlib fix); when None, existing behavior unchanged.
- **Rationale**: Matches the (fixed) stdlib `train(docs, model=...)` signature for FR-002 parity. The backend resolves the base `LlamaModel` and constructs a `TorchLlamaModel` from the BASE model's dims, then loads weights via the existing `_load_weights_into_model` round-trip pattern.
- **Alternatives considered**: Loading via a separate checkpoint-load path — adds an unnecessary file I/O step during warm-start. The base model object is resolved once and passed directly.
- **Caveat**: `train_torch()` must inherit vocab/dims from the base model, NOT rebuild from new docs — the same bug class fixed in the stdlib engine (FR-002a). The torch path must not regress this.

### Decision: UI pre-fill via URL query parameter

- **Decision**: "Continue Training" button uses `href="/v1/training-page?base_model_ref={id}"` pattern. Training page reads `base_model_ref` from URL params on load, fetches model details, pre-fills hyperparams.
- **Rationale**: Simplest, most transparent pattern. Matches existing `attachExperiment()` pre-fill pattern. URL param is visible, shareable, and survives page refresh.
- **Alternatives considered**: sessionStorage — less transparent, lost on browser restart. POST redirect — requires server-side session state.

## References

- `anvil/core/engine.py` — `train(docs, model=None, ...)` and `LlamaModel.load(path)`
- `anvil/services/training/torch_engine.py` — `train_torch()` and `TorchLlamaModel`
- `anvil/services/training/training.py` — `TrainingService.start_training()` config flow
- `anvil/services/compute/protocol.py` — `ComputeBackendProtocol`
- `anvil/services/compute/local_stdlib_backend.py` — stdlib backend
- `anvil/services/compute/local_torch_backend.py` — torch backend
- `anvil/api/v1/training.py` — `TrainConfig`, `POST /v1/training/start`, SSE streaming
- `anvil/api/v1/registry.py` — model registry API
- `anvil/services/tracking/tracking.py` — `TrackingService.register_source_model()`
- `anvil/api/templates/archetypes/model_detail.html` — model detail page template
- `anvil/api/templates/archetypes/training.html` — training page template, `attachExperiment()`
- `anvil/api/static/js/sse.js` — SSE client
- `anvil/api/static/js/core.js` — `core.getUrlParams()`