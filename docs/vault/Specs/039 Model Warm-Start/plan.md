---
title: 039 Model Warm-Start - plan
type: plan
tags:
  - type/spec
  - domain/training
  - domain/core
status: draft
spec-refs:
  - docs/vault/Specs/039 Model Warm-Start/
related:
  - '[[039 Model Warm-Start]]'
  - '[[039 Model Warm-Start - spec]]'
created: '2026-06-28'
updated: '2026-06-28'
---

# Implementation Plan: Model Warm-Start & Run Lineage

**Branch**: `014-model-warm-start` | **Date**: 2026-06-28 | **Spec**: [[039 Model Warm-Start - spec]]
**Input**: Feature specification from `docs/vault/Specs/039 Model Warm-Start/039 Model Warm-Start - spec.md`

## Summary

Add an optional `base_model_ref` (int experiment ID) to training runs so a learner can continue training
an existing anvil checkpoint on new data (warm-start).

> **Post-review correction**: The stdlib engine `train(docs, model=...)` is NOT warm-start-safe today
> (Oracle-confirmed). It reuses weights but rebuilds vocab/`block_size` from the new corpus → token-ID
> drift + matrix-overflow risk. So this feature must FIX the engine, not merely surface it.

This feature delivers warm-start by:

1. **Fixing the stdlib engine** (`engine.train`) to inherit vocab + dims from the base model (FR-002a)
2. Adding `model=` to `torch_engine.train_torch` at parity with the fixed stdlib engine (FR-002)
3. Resolving `base_model_ref` → `LlamaModel` by reusing `InferenceService.load_model()`
4. Adding `base_model_ref` to `TrainConfig`, the training service, and both compute backends, with
   API-boundary dim-conflict validation + engine-layer OOV-char validation (FR-001a)
5. Recording lineage (parent ref, corpus, `warm_start` flag) as MLflow **run tags** via the existing
   `set_tag()` in `on_complete` (FR-003)
6. Adding a "Continue Training" button on the model detail page that pre-fills the training page (FR-003a)

**Zero new dependencies.** No anvil DB schema changes — lineage is MLflow run tags (the model registry
is MLflow-backed, not a SQL table).

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: FastAPI, async SQLAlchemy, Jinja2, MLflow (existing — no new deps)
**Storage**: MLflow Model Registry (registered_models / model_versions tables) — lineage via tags
**Testing**: pytest (existing), mypy --strict
**Target Platform**: Linux/macOS server (same as anvil)
**Project Type**: pip-installable Python package + FastAPI web service
**Performance Goals**: Warm-start adds <500ms overhead for checkpoint loading; SSE streaming unchanged; warm-start initial loss ≥10% below from-scratch
**Constraints**: Zero new dependencies; no changes to from-scratch training path (NMRG); base install must not import torch/transformers/peft
**Scale/Scope**: Single-user / small-team; char-level anvil models only (no external models in this spec)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Simplicity First gate (Article XI — hard MUST)**:

- [x] **Simplest viable** (§11.1) — `base_model_ref` passes as a plain `config` dict key through the existing compute pipeline. No new protocol, enum, or result type. Lineage is MLflow run tags via the existing `set_tag()`. Checkpoint resolution reuses `InferenceService.load_model()`. The engine fix is the minimal change to make warm-start correct (reuse base vocab; reject OOV).
- [x] **Boring over novel** (§11.2) — No new dependencies. Reuses existing MLflow tagging, compute backend protocol, SSE pipeline, and inference checkpoint resolver.
- [x] **YAGNI** (§11.3) — No speculative abstractions. `base_model_ref` is an optional field; the no-base path is unchanged. Vocab GROWTH (resize matrices) is explicitly deferred to a future feature — v1 rejects OOV chars.
- [x] **Reuse first** (§11.4) — Reuses `TrainingService` config flow, `ComputeBackendProtocol.run()`, `set_tag()`, `InferenceService.load_model()`, `Vocabulary.from_chars()`, existing SSE endpoint.
- [x] **Testable** (§11.6) — Warm-start tested via initial-loss comparison (≥10%), torch/stdlib parity, vocab-inheritance + OOV-rejection tests, NMRG.

> No deviations from the simplest viable solution. Complexity Tracking table is empty. The stdlib engine
> fix (FR-002a) is corrective, not additive complexity — it makes an existing-but-broken path correct.

## Project Structure

### Documentation (this feature)

```text
docs/vault/Specs/039 Model Warm-Start/
├── 039 Model Warm-Start.md              # Vault index note
├── 039 Model Warm-Start - spec.md        # Feature spec (clarified)
├── plan.md                               # This file
├── research.md                           # Phase 0 output
├── data-model.md                         # Phase 1 output
├── quickstart.md                         # Phase 1 output
├── contracts/
│   ├── service-lineage.md                # Lineage service contract
│   └── api-warm-start.md                 # API contract for warm-start
└── tasks.md                              # Phase 2 output (not created by /speckit.plan)
```

### Source Code (repository root)

```text
anvil/
├── api/
│   ├── v1/
│   │   ├── training.py              # [MODIFY] TrainConfig: add base_model_ref (int); validate dims vs base; resolve base model; set lineage tags in on_complete
│   │   └── registry.py              # [MODIFY] Model detail/list: surface anvil.warm_start/base_model_ref/specialization_corpus run tags
│   └── templates/archetypes/
│       ├── model_detail.html         # [MODIFY] Add "Continue Training" button
│       └── training.html             # [MODIFY] Handle base_model_ref URL param, pre-fill, send in payload
├── core/
│   └── engine.py                     # [MODIFY] FIX train(model=...) warm-start: inherit vocab+dims from base, reject OOV (FR-002a)
├── services/
│   ├── training/
│   │   └── torch_engine.py          # [MODIFY] train_torch(): add model= parameter + vocab inheritance (FR-002)
│   ├── inference/
│   │   └── inference.py             # [REUSE] InferenceService.load_model() — checkpoint resolver (no change)
│   └── compute/
│       ├── local_stdlib_backend.py  # [MODIFY] Read base_model_ref from config, resolve+load model, pass model=
│       └── local_torch_backend.py   # [MODIFY] Read base_model_ref, resolve+load, build TorchLlamaModel from base dims, pass model=
├── db/
│   └── models/                      # [UNCHANGED] No new DB models — lineage via MLflow run tags

tests/
├── unit/
│   └── core/
│       └── test_warm_start.py       # [NEW] Engine-layer warm-start: vocab inheritance, OOV rejection, parity, initial-loss
└── e2e/
    └── test_warm_start.py           # [NEW] API-layer: warm-start run + lineage tags + dim-conflict 422
```

**Structure Decision**: Follows the existing anvil project structure. No new directories. NOTE: `training.py` does NOT pass `base_model_ref` end-to-end today, and `local_stdlib_backend` does NOT pass `model=` today — both are gaps this feature closes (verified against codebase).

## Implementation Plan (Phase 2 — will be decomposed into tasks.md)

### Layer 0 (Foundational): Fix stdlib engine warm-start (FR-002a) — BLOCKING

- **File**: `anvil/core/engine.py`, `train()` function
- In the `model is not None` branch: require `model.chars`; assert `model.vocab_size == len(model.chars) + 1` (else `ValueError`)
- Derive `uchars = model.chars` (exact order, NO re-sort), `BOS = len(model.chars)`, `vocab_size = model.vocab_size`, `block_size = model.block_size`
- Pre-scan new docs for OOV chars (not in `model.chars`) → `ValueError` listing sample + count
- Keep the `model is None` (from-scratch) path byte-for-byte unchanged — guard all changes inside the `else` branch
- Zero-dependency: engine stays stdlib-only (Article I)

### Layer 1: Engine — Add `model=` to torch_engine (FR-002)

- **File**: `anvil/services/training/torch_engine.py`
- Add `model: TorchLlamaModel | None = None` to `train_torch()` signature
- When `model` is provided: skip random init, reuse the model's params; derive vocab/dims/block_size from the model (mirror the stdlib fix); reject OOV chars
- Reset Adam optimizer state (fresh, matching stdlib behavior)
- Keep from-scratch path unchanged when `model=None`

### Layer 2: Checkpoint resolution + Service threading (FR-001, FR-004)

- **File**: `anvil/services/compute/local_stdlib_backend.py`
- Read `config.get("base_model_ref")` — if present, resolve to a `LlamaModel` via `InferenceService.load_model()` (or load `data/models/experiment_{id}.json` directly) and pass `model=` to `engine.train()`

- **File**: `anvil/services/compute/local_torch_backend.py`
- Read `config.get("base_model_ref")` — if present, resolve the base `LlamaModel`, build a `TorchLlamaModel` using the BASE model's dims (not config dims), load its weights, and pass `model=` to `train_torch()`

- **File**: `anvil/services/training/training.py`
- `start_training()` already forwards the full `config` dict to `backend.run()` — `base_model_ref` flows automatically once it's in `TrainConfig.model_dump()`. (Unlike `device`, no explicit injection is needed because `base_model_ref` originates in the API config, not resolution.) Verify it reaches the backend.

### Layer 3: API — Accept + validate `base_model_ref` (FR-001, FR-001a)

- **File**: `anvil/api/v1/training.py`
- Add `base_model_ref: int | None = Field(default=None)` to `TrainConfig` (note `ConfigDict(extra="forbid")` requires explicit field)
- In `start_training()`: when `base_model_ref` is set, resolve the base model, validate explicit dim overrides don't conflict (HTTP 422), surface engine OOV `ValueError` as HTTP 422

### Layer 4: Registry — Record + surface lineage (FR-003)

- **File**: `anvil/api/v1/training.py`, `on_complete()`
- Alongside the existing `architectures` tag (~line 656), when `config.base_model_ref is not None`, call `set_tag()` three times: `anvil.warm_start`, `anvil.base_model_ref`, `anvil.specialization_corpus` (corpus name resolved as `registry_name` already is)
- **File**: `anvil/api/v1/registry.py`
- In `get_model()` / `list_registered_models()` response, map the three `anvil.*` run tags into the response dict (read path already loads `run.data.tags`)
- **No new `TrackingService` method** — reuse `set_tag()`

### Layer 5: UI — "Continue Training" affordance (FR-003a)

- **File**: `anvil/api/templates/archetypes/model_detail.html`
- Add `<a href="/v1/training-page?base_model_ref={model_id}" class="btn btn-accent btn-sm">Continue Training</a>` next to the Play button

- **File**: `anvil/api/templates/archetypes/training.html`
- On page load (`DOMContentLoaded` or existing init), detect `base_model_ref` URL param
- Fetch model details, pre-fill hyperparameters from the model version's stored hyperparams (reuse `attachExperiment()` pattern)
- Include `base_model_ref` in the `startTraining()` JSON payload

## Complexity Tracking

> No violations — all approaches are the simplest viable solution.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |