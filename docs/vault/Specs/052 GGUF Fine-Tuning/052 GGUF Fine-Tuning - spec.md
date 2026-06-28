---
title: 052 GGUF Fine-Tuning - spec
type: spec
tags:
  - type/spec
  - domain/training
  - domain/core
status: draft
spec-refs:
  - docs/vault/Specs/052 GGUF Fine-Tuning/
related:
  - '[[052 GGUF Fine-Tuning]]'
  - '[[038 Fine-Tuning Arc]]'
  - '[[Reference/FineTuningArchitectureDecisions]]'
created: '2026-06-28'
updated: '2026-06-28'
---

# Feature Specification: GGUF Fine-Tuning

**Feature Branch**: `052-gguf-fine-tuning`
**Created**: 2026-06-28
**Status**: Draft
**Parent Spec**: [[Specs/038 Fine-Tuning Arc/038 Fine-Tuning Arc|038 Fine-Tuning Arc (umbrella)]]

> [!NOTE] Deferred — later priority (FT-AD-11)
> GGUF is committed but deferred, and fine-tuning GGUF-sourced models is the **most complex** of the
> three GGUF specs. Authored now to scope the direction; sequenced last, after 050 (import/run) and the
> v1 PEFT engine (044). Not required for any v1 success criterion.

## Overview

Makes GGUF-sourced models first-class for **training/fine-tuning**, not just inference. Because GGUF
weights are typically quantized for the llama.cpp runtime, fine-tuning them is non-trivial: it requires
a defined path from a GGUF source to a trainable representation (e.g. dequantize/convert to a
PEFT-trainable form, train an adapter, then optionally re-export to GGUF via 051). This spec defines
that path and its boundaries.

### Scope

| Dimension | Scope |
|-----------|-------|
| **Owned FRs** | FR-001..FR-004 (spec-local) |
| **Owned decisions** | FT-AD-11 (GGUF roadmap); reuses FT-AD-1/FT-AD-6/FT-AD-7 |
| **Depends on** | 050 (GGUF import/run), 044 (PEFT engine), 045 (adapter results), 051 (GGUF re-export) |
| **Invariant risk** | **LOW** — new path behind the `[gguf]`/`[finetune]` extras; v1 and base install untouched |

---

## User Story

### US — Learner Fine-Tunes a GGUF-Sourced Model (Priority: Later/P2-within-deferred)

A learner takes a GGUF model, fine-tunes it (adapter), and optionally re-exports the result to GGUF.

**Independent Test**: From an imported GGUF model, run a small fine-tune that produces a tracked adapter,
then re-export the merged result to GGUF and run it externally.

**Acceptance Scenarios**:

1. **Given** an imported GGUF model, **When** the learner starts a fine-tune, **Then** the system
   converts it to a PEFT-trainable representation and trains an adapter via the existing engine (044).
2. **Given** a completed GGUF fine-tune, **When** results are viewed, **Then** a tracked adapter linked to
   the GGUF source is produced (FT-AD-7).
3. **Given** a merged GGUF fine-tune, **When** the learner re-exports, **Then** a GGUF artifact is
   produced via 051.
4. **Given** a GGUF model whose quantization cannot be made trainable, **When** fine-tune is attempted,
   **Then** it fails fast with a clear explanation and guidance.

### Edge Cases

- Lossy dequantization affecting quality → surfaced to the learner with expectation-setting (links 049).
- Routing larger GGUF fine-tunes → reuses the local-vs-SaaS routing (046) and envelope rules (FT-AD-8).
- Mismatch between GGUF tokenizer and trainable form → resolved via the tokenizer abstraction (043).

## Requirements (spec-local)

- **FR-001**: The system MUST define and implement a path from a GGUF source to a PEFT-trainable
  representation, then fine-tune via the existing engine (044), producing a tracked adapter.
- **FR-002**: GGUF fine-tuning MUST reuse the compute routing (046) and adapter result shape (045);
  larger jobs route to SaaS (047) under the standard envelope rules.
- **FR-003**: Re-export of a GGUF fine-tune to GGUF MUST go through 051; intermediate trainable artifacts
  MUST be tracked.
- **FR-004**: GGUF models that cannot be made trainable (unsupported quantization) MUST fail fast with a
  clear explanation; no silent quality-destroying conversion.

## Success Criteria

- **SC-001**: A learner fine-tunes a GGUF-sourced model to a tracked adapter and re-exports to GGUF.
- **SC-002**: Untrainable GGUF inputs fail fast with actionable guidance.
- **SC-003 (NMRG)**: v1 arc and base install unchanged; pre-existing tests pass unmodified.

## Key Entities

- **GGUFFineTuneRun**: a fine-tune originating from a GGUF source, producing a tracked adapter.
- **TrainableConversion**: the intermediate representation produced from a GGUF source for training.

## Definition of Done

- GGUF source → trainable conversion → adapter → optional GGUF re-export, all tracked; untrainable inputs
  fail fast; **NMRG (full)**.

## Assumptions

- Import/run (050) and export (051) ship first; this spec composes them with the PEFT engine (044).
- Quality trade-offs of dequantization are acceptable and clearly communicated, not hidden.
