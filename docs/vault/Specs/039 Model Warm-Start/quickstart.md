---
title: 039 Model Warm-Start - quickstart
type: spec
tags:
  - type/spec
  - domain/training
  - domain/core
status: draft
created: '2026-06-28'
updated: '2026-06-28'
---

# Quickstart: Model Warm-Start & Run Lineage

## Developer Setup

```bash
# Check you're on the feature branch
git branch  # should show 014-model-warm-start

# Install deps (no new deps for this feature)
make setup

# Run existing tests to verify baseline (NMRG)
make test
```

> **Heads-up**: `anvil/core/engine.py` is the zero-dependency core (Constitution Article I). The
> warm-start fix MUST stay stdlib-only — no imports of torch/transformers/etc.

## Implementation Order

> **Critical**: Step 1 FIXES a latent bug. `train(model=...)` is NOT warm-start-safe today (it rebuilds
> vocab from the new corpus). Do this first — everything else builds on correct vocab inheritance.

### Step 1: Fix stdlib engine warm-start vocab inheritance (FR-002a) — FOUNDATIONAL

**File**: `anvil/core/engine.py`, `train()`

In the `model is not None` branch: require `model.chars`, assert `model.vocab_size == len(model.chars) + 1`,
derive `uchars`/`BOS`/`vocab_size`/`block_size` from the base model (exact `model.chars` order — no
re-sort), pre-scan docs for OOV chars → `ValueError`. Guard ALL changes inside the `else` branch so
`model=None` stays byte-for-byte unchanged.

### Step 2: Add `model=` to `torch_engine.train_torch()` (FR-002)

**File**: `anvil/services/training/torch_engine.py`

Add `model: TorchLlamaModel | None = None`. When provided, reuse the model's params and derive
vocab/dims/block_size from the model (mirror the stdlib fix); reject OOV chars.

### Step 3: Resolve `base_model_ref` + thread through backends (FR-001)

**Files**:
- `anvil/services/compute/local_stdlib_backend.py` — read `config.get("base_model_ref")`, resolve via `InferenceService.load_model()`, pass `model=` to `engine.train()`
- `anvil/services/compute/local_torch_backend.py` — resolve base model, build `TorchLlamaModel` from BASE dims, pass `model=` to `train_torch()`
- `anvil/services/training/training.py` — `base_model_ref` already flows via `config.model_dump()`; verify it reaches the backend

### Step 4: Extend + validate API (FR-001, FR-001a)

**File**: `anvil/api/v1/training.py` — add `base_model_ref: int | None` to `TrainConfig`; in `start_training()` resolve base model, reject conflicting dim overrides (422), map `ValueError` → 422

### Step 5: Record lineage as run tags (FR-003)

**File**: `anvil/api/v1/training.py`, `on_complete()` — alongside the `architectures` tag, add three
`set_tag()` calls (`anvil.warm_start`, `anvil.base_model_ref`, `anvil.specialization_corpus`) when
`base_model_ref` is set. Surface them in `anvil/api/v1/registry.py`. **No new `TrackingService` method.**

### Step 6: UI affordance (FR-003a)

**Files**:
- `anvil/api/templates/archetypes/model_detail.html` — add "Continue Training" button
- `anvil/api/templates/archetypes/training.html` — handle `base_model_ref` URL param, pre-fill form, send in payload

### Step 7: Tests

- Unit: vocab inheritance (subset reuses base chars), OOV rejection, missing-`chars` rejection
- Unit: warm-start initial loss ≥10% below from-scratch
- Unit: torch/stdlib parity test
- e2e: warm-start run via API + lineage tag verification + dim-conflict 422
- NMRG: pre-existing tests pass unmodified; `model=None` byte-for-byte unchanged

## Verification

```bash
# Unit tests (engine-layer warm-start)
pytest tests/unit/core/test_warm_start.py -v

# e2e tests (API-layer warm-start)
pytest tests/e2e/test_warm_start.py -v

# Lint + typecheck
make lint && make typecheck

# Full test suite (NMRG)
make test

# Dependency isolation check
python -c "import sys, anvil.core.engine; assert 'torch' not in sys.modules"
```

## Key Files

| File | Action |
|------|--------|
| `anvil/core/engine.py` | **FIX** `train(model=...)` warm-start: inherit vocab+dims, reject OOV (FR-002a) |
| `anvil/services/training/torch_engine.py` | Add `model=` param to `train_torch()` (FR-002) |
| `anvil/services/inference/inference.py` | **REUSE** `load_model()` as checkpoint resolver (no change) |
| `anvil/services/compute/local_stdlib_backend.py` | Resolve `base_model_ref`, pass `model=` |
| `anvil/services/compute/local_torch_backend.py` | Resolve `base_model_ref`, build TorchLlamaModel from base dims |
| `anvil/services/training/training.py` | Verify `base_model_ref` passthrough |
| `anvil/api/v1/training.py` | Add `base_model_ref` (int) to `TrainConfig`; validate; set lineage tags in `on_complete` |
| `anvil/api/v1/registry.py` | Surface `anvil.*` lineage run tags |
| `anvil/api/templates/archetypes/model_detail.html` | Add "Continue Training" button |
| `anvil/api/templates/archetypes/training.html` | Handle `base_model_ref` param, pre-fill |
| `tests/unit/core/test_warm_start.py` | New engine-layer warm-start tests |
| `tests/e2e/test_warm_start.py` | New API-layer warm-start + lineage tests |