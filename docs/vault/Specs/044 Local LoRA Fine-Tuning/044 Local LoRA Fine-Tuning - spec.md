---
title: 044 Local LoRA Fine-Tuning - spec
type: spec
tags:
  - type/spec
  - domain/training
  - domain/core
status: draft
spec-refs:
  - docs/vault/Specs/044 Local LoRA Fine-Tuning/
related:
  - '[[044 Local LoRA Fine-Tuning]]'
  - '[[038 Fine-Tuning Arc]]'
  - '[[Reference/FineTuningArchitectureDecisions]]'
created: '2026-06-28'
updated: '2026-06-28'
---

# Feature Specification: Local LoRA/QLoRA Fine-Tuning Engine

**Feature Branch**: `044-local-lora-fine-tuning`
**Created**: 2026-06-28
**Status**: Draft
**Parent Spec**: [[Specs/038 Fine-Tuning Arc/038 Fine-Tuning Arc|038 Fine-Tuning Arc (umbrella)]]

## Overview

The headline Track B capability: fine-tune a real pretrained model (TinyLlama-class) **locally** with
parameter-efficient methods (LoRA/QLoRA), producing a small adapter — using the model's own subword
tokenizer (043) and assets (042). The engine is a new compute backend behind the existing
`ComputeBackendProtocol`, with all heavy deps in the `[finetune]` extra. Local runs are gated to the
curated resource envelope; anything larger is guided to SaaS (046/047).

### Scope

| Dimension | Scope |
|-----------|-------|
| **Owned FRs** | FR-016, FR-017, FR-018, FR-019 |
| **Owned decisions** | FT-AD-1 (external side), FT-AD-9 (execution scope) |
| **Depends on** | 042 (assets), 043 (tokenizer); `anvil/services/compute/` protocol+registry; `torch`/`transformers`/`peft` (`[finetune]`) |
| **Invariant risk** | **LOW** — new backend behind the existing protocol + optional extra; no existing path modified |

---

## User Story

### US — Learner Fine-Tunes a Small Model Locally with LoRA (Priority: P1)

A learner picks an imported TinyLlama-class model with assets available, configures a LoRA/QLoRA run on a
small dataset, runs it locally (GPU if present), and gets a tracked adapter.

**Independent Test**: With a downloaded TinyLlama-class model and a tiny instruction dataset, start a
LoRA run with minimal settings; verify the subword tokenizer is used, training progresses with live
metrics, and a tracked LoRA adapter is produced.

**Acceptance Scenarios**:

1. **Given** a catalog model with assets, **When** the learner starts a LoRA run, **Then** the model's
   subword tokenizer encodes the data and training runs via the torch/PEFT backend.
2. **Given** the `[finetune]` extra is not installed, **When** an external fine-tune is started, **Then**
   the system fails fast with "install `anvil[finetune]`" and never silently degrades.
3. **Given** a completed LoRA run, **When** the learner views results, **Then** a LoRA adapter (not a full
   model copy) is stored, linked to its base model.
4. **Given** a model larger than the local catalog envelope, **When** local fine-tune is attempted,
   **Then** the learner is guided to offload to SaaS rather than OOM.

### Edge Cases

- GPU absent → CPU LoRA permitted only for envelope-eligible tiny models; otherwise guided to SaaS.
- QLoRA requested but bitsandbytes/quantization unavailable on the host → fail fast naming the missing
  capability.
- Base assets missing/corrupt → fail fast (links 042), no random-init fallback.
- Base model marked `track-only` (non-allow-list architecture or unsupported format, FR-009a) → refuse
  to start with a clear message and a link to the architecture-differences lesson (049).
- Divergence/NaN loss → surfaced via the existing divergence detection in the training service.

## Requirements

- **FR-016**: The system MUST provide a compute backend that fine-tunes external pretrained models using
  parameter-efficient methods (`lora`, `qlora`) and optionally `full`, built on
  `torch`/`transformers`/`peft`, registered behind the existing `ComputeBackendProtocol`.
- **FR-017**: A fine-tune MUST be configured by a `FineTuneSpec` (method, target modules, rank/alpha,
  learning rate, steps, quantization) plus a `base_model_ref` and a dataset — for instruction tuning, a
  dataset prepared by spec 053 (SFT/chat-templated), consumed unchanged.
- **FR-018**: Local fine-tuning MUST be restricted to catalog models within the local resource envelope
  (FT-AD-8); attempts beyond it MUST guide the user to SaaS rather than OOM.
- **FR-018a**: The engine MUST refuse to start on a base model whose recorded runnable status is
  `track-only` (non-allow-list architecture or unsupported weight format, FR-009a/FR-030/FR-032),
  failing fast rather than attempting a best-effort load.
- **FR-019**: All heavy fine-tuning dependencies MUST be optional extras; absence MUST fail fast with an
  install hint and MUST NOT be importable in a base install.
- **FR-016a**: The PEFT backend MUST emit live progress through the existing progress-callback / SSE
  pipeline, consistent with the stdlib and torch backends.
- **FR-017a**: `FineTuneSpec` defaults MUST be sensible for a TinyLlama-class LoRA run so a learner can
  start with minimal configuration.

## Success Criteria

- **SC-001**: A catalog model LoRA-fine-tunes locally with its subword tokenizer, producing a tracked
  adapter, on a machine within the documented envelope.
- **SC-002**: Missing `[finetune]` extra fails fast with an install hint (no silent downgrade).
- **SC-003**: Over-envelope attempts guide to SaaS rather than OOM.
- **SC-004 (NMRG)**: Pre-existing tests pass unmodified; base install imports no `torch`/`transformers`/
  `peft`.

## Key Entities

- **FineTuneSpec**: method (`full`/`lora`/`qlora`), target modules, rank/alpha, quantization, LR, steps.
- **FineTuneRun (external)**: a run with `base_model_ref` + `FineTuneSpec`; produces an adapter.
- **Adapter**: the LoRA delta artifact, linked to its base model (result shape detailed in 045).

## Definition of Done

- Local LoRA run on a catalog model yields a tracked adapter via the model's subword tokenizer;
  fail-fast extra probe; envelope gating with SaaS guidance; live metrics; **NMRG (full)**.

## Assumptions

- The adapter result shape and inference/merge/export are owned by spec 045; this spec produces the
  adapter and registers it.
- Routing local-vs-SaaS by size is owned by spec 046; this spec enforces the local envelope boundary.
