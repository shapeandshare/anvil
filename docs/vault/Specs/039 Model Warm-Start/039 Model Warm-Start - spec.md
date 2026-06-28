---
title: 039 Model Warm-Start - spec
type: spec
tags:
  - type/spec
  - domain/training
  - domain/core
status: draft
spec-refs:
  - docs/vault/Specs/039 Model Warm-Start/
related:
  - '[[039 Model Warm-Start]]'
  - '[[038 Fine-Tuning Arc]]'
  - '[[Reference/FineTuningArchitectureDecisions]]'
created: '2026-06-28'
updated: '2026-06-28'
---

# Feature Specification: Model Warm-Start & Run Lineage

**Feature Branch**: `039-model-warm-start`
**Created**: 2026-06-28
**Status**: Draft
**Parent Spec**: [[Specs/038 Fine-Tuning Arc/038 Fine-Tuning Arc|038 Fine-Tuning Arc (umbrella)]]

## Overview

The first, fully **native** taste of fine-tuning: continue training one of anvil's own char-level
`LlamaModel` checkpoints on a new corpus and watch it specialize. This is Track A — it reuses the
entire existing stack and adds **zero new dependencies**. The stdlib engine already supports warm-start
(`anvil.core.engine.train(docs, model=...)`); this feature surfaces it end-to-end (service, registry,
UI) and closes the torch-engine parity gap.

### Scope

| Dimension | Scope |
|-----------|-------|
| **Owned FRs** | FR-001, FR-002, FR-003, FR-004 |
| **Owned decisions** | FT-AD-1 (native side), FT-AD-10 (ships with its concept page from 048) |
| **Depends on** | Existing training service, model registry (spec 003), `anvil/core/engine.py`, `anvil/core/torch_engine.py` |
| **Invariant risk** | **LOW** — additive `base_model_ref`; the no-base path is unchanged. Only care point is the `torch_engine` `model=` addition (behind `[gpu]`). |

---

## User Story

### US — Learner Specializes a Model They Already Trained (Priority: P1)

A learner who has trained a char-level model from scratch selects that checkpoint and continues training
it on a new, narrower corpus, watching it specialize in real time.

**Independent Test**: Train from scratch (existing flow), register it, then start a new run with that
model as `base_model_ref` on a different small corpus. Verify warm-start (loss begins below a
from-scratch run) and that lineage links the new model to its parent.

**Acceptance Scenarios**:

1. **Given** a registered anvil checkpoint, **When** the learner starts a run selecting it as the base
   model, **Then** training resumes from those weights (not random init) and live metrics stream as
   usual.
2. **Given** a fine-tune run completes, **When** the learner views the registry, **Then** the new model
   records its parent `base_model_ref` and the corpus it was specialized on.
3. **Given** no base model is selected, **When** the learner starts a run, **Then** behavior is exactly
   today's from-scratch pretraining.
4. **Given** a base model trained with architecture dims X, **When** a warm-start run is configured,
   **Then** the run inherits those dims and rejects incompatible overrides with a clear error.

### Edge Cases

- Base checkpoint dims conflict with requested hyperparameters → reject with a clear message (no silent
  re-init).
- Base model file/checkpoint missing or corrupt → fail fast ("re-select or re-train base"), never fall
  back to random init.
- Warm-start requested on the torch engine before the `model=` path exists → must be implemented, not
  silently downgraded to stdlib.

## Requirements

- **FR-001**: A training run MUST accept an optional `base_model_ref` identifying an existing registered
  anvil checkpoint; when present, training warm-starts from those weights instead of random init.
- **FR-002**: The torch training engine (`anvil.core.torch_engine.train_torch`) MUST support warm-start
  from an existing model — adding a `model=`/checkpoint-load path at parity with the stdlib engine's
  existing `train(docs, model=...)`.
- **FR-003**: A fine-tuned model MUST record its lineage — parent `base_model_ref`, the corpus/dataset
  it was specialized on, and a `warm_start` provenance flag — in the model registry.
- **FR-004**: Warm-start runs MUST stream live metrics through the existing training/SSE pipeline
  unchanged.
- **FR-001a**: The architecture dimensions (`n_embd`, `n_head`, `n_layer`, `block_size`, vocabulary)
  of a warm-start run MUST be derived from the base checkpoint; incompatible explicit overrides MUST be
  rejected, not coerced.
- **FR-003a**: The registry/experiment UI MUST expose a "continue training / specialize" affordance on a
  registered model that pre-fills `base_model_ref`.

## Success Criteria

- **SC-001**: A learner specializes a previously trained model via warm-start and sees the new model's
  lineage to its parent — with zero new dependencies installed.
- **SC-002**: A warm-start run measurably begins below an equivalent from-scratch run's initial loss.
- **SC-003**: Torch and stdlib engines produce equivalent warm-start behavior (parity test).
- **SC-004 (NMRG)**: Pre-existing tests pass unmodified; a no-base run is byte-for-byte today's
  behavior; base (no-extras) install imports no ML deps.

## Key Entities

- **BaseModelRef**: reference to the anvil checkpoint a run starts from.
- **FineTuneRun (native)**: a training run carrying a `base_model_ref`; records lineage.

## Definition of Done

- Lineage visible in the registry; warm-start parity between engines proven; the "continue training"
  UI affordance works; **NMRG (full)** per [[Reference/FineTuningArchitectureDecisions|FT-AD-2]].

## Assumptions

- The base model and the new run share the char-level tokenizer family (external models are out of
  scope here — see 040+).
- Registry lineage extends spec 003 rather than introducing a new store.
