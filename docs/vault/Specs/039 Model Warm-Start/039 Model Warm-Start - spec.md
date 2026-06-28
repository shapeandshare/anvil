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
clarified: '2026-06-28'
---

# Feature Specification: Model Warm-Start & Run Lineage

**Feature Branch**: `014-model-warm-start`
**Created**: 2026-06-28
**Status**: Draft
**Parent Spec**: [[Specs/038 Fine-Tuning Arc/038 Fine-Tuning Arc|038 Fine-Tuning Arc (umbrella)]]

## Overview

The first, fully **native** taste of fine-tuning: continue training one of anvil's own char-level
`LlamaModel` checkpoints on a new corpus and watch it specialize. This is Track A — it reuses the
entire existing stack and adds **zero new dependencies**.

> **Correction (post-codebase-review)**: The stdlib engine's `train(docs, model=...)` accepts a model
> object but is **NOT** warm-start-safe today — it rebuilds `uchars`/`BOS`/`vocab_size`/`block_size`
> from the *new* corpus even when a model is passed, causing token-ID drift and possible embedding/
> lm_head matrix overflow. This feature must therefore (a) **fix the stdlib engine** to inherit
> vocabulary and architecture from the base checkpoint, (b) **close the torch-engine `model=` gap**,
> and (c) surface warm-start end-to-end (service, registry, UI).

### Scope

| Dimension | Scope |
|-----------|-------|
| **Owned FRs** | FR-001, FR-001a, FR-002, FR-002a, FR-003, FR-003a, FR-004 |
| **Owned decisions** | FT-AD-1 (native side), FT-AD-10 (ships with its concept page from 048) |
| **Depends on** | Existing training service, model registry (spec 003), `anvil/core/engine.py`, `anvil/services/training/torch_engine.py` |
| **Invariant risk** | **LOW–MEDIUM** — additive `base_model_ref`; the no-base path must remain byte-for-byte unchanged. Care points: (1) the stdlib engine warm-start branch must inherit vocab/dims from the base checkpoint without touching the from-scratch path; (2) the `torch_engine` `model=` addition (behind `[gpu]`). |

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
5. **Given** a base model trained on vocabulary V, **When** a warm-start run uses a corpus whose
   characters are all within V, **Then** the run tokenizes with the base model's exact char mapping and
   trains successfully.
6. **Given** a base model trained on vocabulary V, **When** a warm-start run uses a corpus containing a
   character not in V, **Then** the run fails fast with a clear error naming the unsupported character(s).

### Edge Cases

- Base checkpoint dims conflict with requested hyperparameters → reject with a clear message (no silent
  re-init).
- Base model file/checkpoint missing or corrupt → fail fast ("re-select or re-train base"), never fall
  back to random init.
- **New corpus contains characters absent from the base model's vocabulary** → fail fast with a
  `ValueError` listing a sample and count of unsupported chars; never silently skip them, never
  auto-grow the vocab (that is a separate future feature).
- Base checkpoint missing its `model.chars` metadata, or `vocab_size != len(model.chars) + 1` → fail
  fast (corrupt/incompatible checkpoint).
- Warm-start requested on the torch engine before the `model=` path exists → must be implemented, not
  silently downgraded to stdlib.
- Concurrent warm-start runs targeting the same base checkpoint → each run loads an independent copy
  of the weights; base checkpoint is read-only.

## Requirements

- **FR-001**: A training run MUST accept an optional `base_model_ref` identifying an existing registered
  anvil checkpoint; when present, training warm-starts from those weights instead of random init.
- **FR-002**: The torch training engine (`anvil.services.training.torch_engine.train_torch`) MUST support warm-start
  from an existing model — adding a `model=` path at parity with the (fixed) stdlib engine's
  `train(docs, model=...)`.
- **FR-002a**: The stdlib engine `train(docs, model=...)` MUST be made warm-start-safe: when a model is
  provided, it MUST derive `uchars`, `BOS`, `vocab_size`, and `block_size` from the base model (using the
  exact stored `model.chars` order, not a re-sort of the new corpus), and MUST NOT rebuild vocabulary
  from the new docs. The from-scratch path (`model=None`) MUST remain byte-for-byte unchanged.
- **FR-003**: A fine-tuned model MUST record its lineage — parent `base_model_ref`, the corpus/dataset
  it was specialized on, and a `warm_start` provenance flag — in the model registry. The anvil model
  registry is MLflow-backed (no SQL table), so lineage is stored as MLflow tags on the training run
  (`anvil.warm_start`, `anvil.base_model_ref`, `anvil.specialization_corpus`), set in the existing
  `on_complete` flow alongside the current `architectures` tag — no new store.
- **FR-004**: Warm-start runs MUST stream live metrics through the existing training/SSE pipeline
  unchanged.
- **FR-001a**: The architecture dimensions (`n_embd`, `n_head`, `n_layer`, `block_size`) and the
  vocabulary (`model.chars`) of a warm-start run MUST be derived from the base checkpoint. Enforcement is
  two-layered: (1) at the API boundary, explicit hyperparameter overrides conflicting with the base
  checkpoint dims MUST be rejected with HTTP 422 (engine callers can bypass the API, so the engine also
  enforces); (2) at the engine layer, new-corpus characters absent from `model.chars` MUST cause a
  fail-fast `ValueError` listing a sample/count — never silently skipped, mapped, or normalized, and
  never auto-unioned/resized (vocab growth is a separate future feature).
- **FR-003a**: The registry/experiment UI MUST expose an action button on the model detail page labeled
  "Continue Training" or "Specialize" that navigates to the training page with `base_model_ref`
  pre-filled.

## Success Criteria

- **SC-001**: A learner specializes a previously trained model via warm-start and sees the new model's
  lineage to its parent — with zero new dependencies installed.
- **SC-002**: A warm-start run's initial loss MUST be ≥10% below an equivalent from-scratch run's initial
  loss (with a deliberately undertrained base to ensure headroom).
- **SC-003**: Torch and stdlib engines produce equivalent warm-start behavior (parity test).
- **SC-004 (NMRG)**: Pre-existing tests pass unmodified; a no-base run is byte-for-byte today's
  behavior; base (no-extras) install imports no ML deps.
- **SC-005**: A warm-start run reuses the base model's exact vocabulary (`model.chars`); a corpus with an
  out-of-vocabulary character fails fast with a clear error (no silent token corruption).

## Key Entities

- **BaseModelRef**: the integer experiment ID identifying the anvil checkpoint a run warm-starts from;
  resolved to `data/models/experiment_{id}.json` at run time (the same resolution path used by
  `InferenceService.load_model()`), with an MLflow Model Registry artifact-download fallback.
- **FineTuneRun (native)**: a training run carrying a `base_model_ref`; records lineage.

## Definition of Done

- Stdlib engine warm-start inherits vocab + dims from the base checkpoint and rejects OOV chars
  (FR-002a); torch engine reaches parity (FR-002); lineage visible in the registry via MLflow run tags;
  warm-start parity between engines proven; the "Continue Training" UI affordance works; **NMRG (full)**
  per [[Reference/FineTuningArchitectureDecisions|FT-AD-2]] (including `model=None` byte-for-byte
  unchanged).

## Clarifications

### Session 2026-06-28

- Q: How should lineage be stored in the registry? → A: As MLflow run tags (`anvil.warm_start`, `anvil.base_model_ref`, `anvil.specialization_corpus`). The anvil model registry is MLflow-backed — there is NO SQL model table — so MLflow tags are the registry-native equivalent of "columns". Set in the existing `on_complete` flow alongside the `architectures` tag. (Corrected from the initial "new columns" answer after codebase verification: no SQL model registry table exists.)
- Q: What form does the "continue training / specialize" UI affordance take? → A: Action button on the model registry detail page that navigates to training page with `base_model_ref` pre-filled.
- Q: What threshold counts as "measurably below" for warm-start initial loss? → A: ≥10% below an equivalent from-scratch run's initial loss.
- Q: What does `base_model_ref` contain? → A: The integer experiment ID of the base model (matching the existing `model_id` convention used by the inference/registry layer). Resolved to `data/models/experiment_{id}.json` at run time via the same path `InferenceService.load_model()` uses.
- Q: How should concurrent warm-start runs targeting the same base checkpoint be handled? → A: Each run loads an independent copy of the weights from the base checkpoint (read-only on the base, no sharing or locking).

## Assumptions

- The base model and the new run share the char-level tokenizer family (external models are out of
  scope here — see 040+).
- Registry lineage extends spec 003 (MLflow-backed registry) via MLflow tags rather than introducing a
  new store. There is no SQL model registry table — models live in MLflow `registered_models` /
  `model_versions`, and lineage is recorded as run tags.
