---
title: 039 Model Warm-Start - data-model
type: spec
tags:
  - type/spec
  - domain/training
  - domain/core
status: draft
created: '2026-06-28'
updated: '2026-06-28'
---

# Data Model: Model Warm-Start & Run Lineage

## Entities

### BaseModelRef

A reference identifying an existing registered anvil checkpoint to warm-start from.

| Field | Type | Description |
|-------|------|-------------|
| base_model_ref | `int` | The experiment ID of the base model (matching the existing `model_id` convention in inference/registry). |

**Resolution path** (reuse, do NOT reinvent):
- Resolved to a `LlamaModel` via `InferenceService.load_model(model_id=base_model_ref)`, which:
  1. Primary: loads `data/models/experiment_{base_model_ref}.json` via `LlamaModel.load()`
  2. Fallback: downloads `model.json` from the MLflow Model Registry by matching `dataset-{id}`/`corpus-{id}`/`demo`
- The loaded `LlamaModel` carries its own vocabulary as `model.chars` (the authoritative base vocab)

**Notes**:
- Same tokenizer family (char-level) as the new run — external models out of scope for this spec
- Validation: checkpoint must exist and be loadable; fail-fast if missing or corrupt (`ValueError` from `load_model`)
- Vocabulary handling: see "Vocabulary inheritance" below (FR-001a)

### FineTuneRun (native warm-start)

A training run that carries a `base_model_ref` and records lineage.

| Field | Type | Description |
|-------|------|-------------|
| run_id | `int` | Local run ID (allocated by `TrainingService.reserve_run()`) |
| base_model_ref | `int \| None` | Optional experiment ID for warm-start; None = from-scratch |
| engine | `TrainingEngine` | `STDLIB` or `TORCH` (resolved at run time) |
| backend | `ComputeBackendResult` | `LOCAL` or `MODAL` |
| status | `ComputeStatus` | Submitted → Running → Completed/Failed |
| config | `dict[str, Any]` | Full training configuration (hyperparameters + base_model_ref) |

**Validation rules**:
- A FineTuneRun with `base_model_ref=None` is byte-for-byte today's from-scratch behavior (FR-027)
- Architecture dimensions (`n_embd`, `n_head`, `n_layer`, `block_size`) AND vocabulary (`model.chars`) derived from base checkpoint when `base_model_ref` is set (FR-001a)
- Incompatible explicit dim overrides rejected at API boundary with HTTP 422 (FR-001a)
- New-corpus chars absent from `model.chars` rejected at engine layer with `ValueError` (FR-001a)
- Concurrent runs targeting the same base each load an independent copy of weights (clarified)

### Vocabulary inheritance (FR-001a, FR-002a)

The base `LlamaModel` owns its vocabulary as `model.chars` (the ordered char list). On warm-start:

| Rule | Behavior |
|------|----------|
| Vocab source | `model.chars` exactly (preserve order — do NOT re-sort) |
| `vocab_size` | `len(model.chars) + 1` (the `+1` is the BOS token) |
| `BOS` | `len(model.chars)` |
| `block_size` | inherited from `model.block_size`, not the function default |
| OOV char in new corpus | fail-fast `ValueError` listing sample + count |
| Vocab growth (new chars) | OUT OF SCOPE — explicitly deferred to a future `resize_vocab()` feature |
| Checkpoint integrity | require `model.chars` present and `model.vocab_size == len(model.chars) + 1`, else `ValueError` |

### Model (MLflow registered model — extended for lineage)

The model registry is MLflow-backed (no SQL model table). Lineage is stored as **MLflow run tags**, set
via the existing `TrackingService.set_tag()` in the `on_complete` flow (alongside the existing
`architectures` tag at training.py:656), BEFORE `register_source_model()` is called:

| Tag Key | Value | Description |
|---------|-------|-------------|
| `anvil.warm_start` | `"true"` or absent | Presence flag indicating this model was produced by warm-start |
| `anvil.base_model_ref` | Experiment ID string | The parent experiment ID this was warm-started from |
| `anvil.specialization_corpus` | Dataset/corpus name | The corpus or dataset used for warm-start training |

**Why run tags, not version tags**: the registry detail/list endpoints (`list_registered_models`,
`get_model`) read run data via `client.get_run(run_id)` and surface `run.data.tags`. Setting lineage as
run tags makes it immediately visible through the existing read path with no new query.

### TrainConfig (Pydantic — extended)

Existing Pydantic model for the `POST /v1/training/start` endpoint. New field:

| Field | Type | Description |
|-------|------|-------------|
| base_model_ref | `int \| None` | Experiment ID to warm-start from (new) |
| *(existing: n_embd, n_layer, n_head, block_size, num_steps, learning_rate, beta1, beta2, temperature, compute_backend, dataset_id, corpus_id)* | | |

## State Transitions

### Warm-Start Run Lifecycle

```
Configure (with optional base_model_ref)
    │
    ▼
Validate (check base checkpoint exists, dims compatible)
    │
    ▼
Reserve Run ID → Resolve Backend → Load Docs
    │
    ▼
Resolve + Load Base Checkpoint via InferenceService.load_model (if base_model_ref set)
    │
    ▼
Validate vocab (OOV chars → ValueError) + dims (engine inherits from base)
    │
    ▼
Run Training (from-scratch or warm-start)
    │
    ▼
on_complete: set MLflow run tags (anvil.warm_start / base_model_ref / specialization_corpus)
    │
    ▼
Emit Complete SSE Event
```

### From-Scratch Path (unchanged)

```
Configure (no base_model_ref)  →  Run Training  →  Complete
```

## Relationships

```
TrainingRun (FineTuneRun)
    │
    ├─ 0..1 ──► BaseModelRef (the checkpoint this run warm-starts from)
    │
    └─ 1 ──► TrainingConfig (hyperparameters)

Model (MLflow registered model)
    │
    ├─ 1 ──► TrainingRun (produced_by)
    │
    └─ 0..1 ──► BaseModelRef (parent_model — only for warm-started models)
```

## Uniqueness & Identity

- `base_model_ref`: an integer experiment ID referencing an existing anvil checkpoint
- Resolved to `data/models/experiment_{id}.json` (primary) or the MLflow registry (fallback) via `InferenceService.load_model()`
- No new unique constraints needed — MLflow manages model identity