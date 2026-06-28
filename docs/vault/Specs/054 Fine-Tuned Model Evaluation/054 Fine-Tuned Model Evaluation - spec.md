---
title: 054 Fine-Tuned Model Evaluation - spec
type: spec
tags:
  - type/spec
  - domain/training
  - domain/mlops
status: draft
spec-refs:
  - docs/vault/Specs/054 Fine-Tuned Model Evaluation/
related:
  - '[[054 Fine-Tuned Model Evaluation]]'
  - '[[038 Fine-Tuning Arc]]'
  - '[[Reference/FineTuningArchitectureDecisions]]'
created: '2026-06-28'
updated: '2026-06-28'
---

# Feature Specification: Fine-Tuned Model Evaluation

**Feature Branch**: `054-fine-tuned-model-evaluation`
**Created**: 2026-06-28
**Status**: Draft
**Parent Spec**: [[Specs/038 Fine-Tuning Arc/038 Fine-Tuning Arc|038 Fine-Tuning Arc (umbrella)]]

## Overview

Answers the question every fine-tune raises: **did it help?** Provides side-by-side comparison of a
fine-tuned model against its base — qualitative samples on the same prompts and quantitative metrics
(e.g. eval loss / held-out perplexity) — reusing the existing evaluation service and surfacing results
in the experiment/registry UI. Applies to native warm-start (039) and external/adapter (044/045)
models alike, dispatching on the recorded tokenizer family (043).

### Scope

| Dimension | Scope |
|-----------|-------|
| **Owned FRs** | FR-035 (+ spec-local FR-001..FR-003) |
| **Owned decisions** | reuses FT-AD-7 (base+adapter), FT-AD-10 (pedagogy) |
| **Depends on** | existing eval service (`anvil/services/.../eval`, `anvil/api/v1/eval.py`); 045 (adapter inference); 040 (models); 043 (tokenizer dispatch) |
| **Invariant risk** | **LOW** — extends evaluation; no change to pretraining or base install |

---

## User Story

### US — Learner Compares a Fine-Tuned Model to Its Base (Priority: P1)

A learner runs the same prompts through a fine-tuned model and its base, sees outputs side by side, and
views metrics indicating whether the fine-tune improved on the target task.

**Independent Test**: With a base model and a fine-tuned variant (warm-start or adapter), run an
evaluation on a small held-out set; verify side-by-side samples and a metric delta are displayed and
recorded.

**Acceptance Scenarios**:

1. **Given** a fine-tuned model and its base, **When** the learner runs an evaluation on a held-out set,
   **Then** side-by-side sample outputs on identical prompts are shown.
2. **Given** the same evaluation, **When** it completes, **Then** quantitative metrics (e.g. eval loss /
   perplexity) and the base→fine-tuned delta are recorded in the experiment/registry.
3. **Given** an adapter model, **When** evaluated, **Then** inference composes base+adapter (045) and the
   correct tokenizer family is used (043).
4. **Given** a `track-only` model, **When** evaluation is attempted, **Then** it is refused with a clear
   message (consistent with FR-009a).

### Edge Cases

- No held-out set provided → use a clearly labeled split or prompt the learner; do not silently evaluate
  on training data.
- Base and fine-tuned use different tokenizers (warm-start keeps char-level; external uses subword) →
  metrics are computed per the model's own tokenizer and labeled accordingly.
- Non-comparable metrics across tokenizer families → present qualitatively side-by-side, label
  quantitative caveats.

## Requirements

- **FR-035**: The system MUST support evaluating a fine-tuned model against its base — qualitative
  side-by-side samples on identical prompts and quantitative metrics — reusing the existing evaluation
  service, and recording results in the experiment/registry.
- **FR-001** (spec-local): Evaluation MUST dispatch on the model's recorded tokenizer family (043) and,
  for adapter models, compose base+adapter via 045.
- **FR-002** (spec-local): Evaluation MUST record the base→fine-tuned metric delta and the prompt set
  used, for reproducibility and lineage.
- **FR-003** (spec-local): Evaluation MUST refuse `track-only` models (FR-009a) with a clear message.

## Success Criteria

- **SC-001**: A learner compares a fine-tuned model to its base on identical prompts and sees whether it
  improved (samples + metric delta).
- **SC-002**: Results are recorded with the prompt set and lineage.
- **SC-003**: Adapter models evaluate correctly (base+adapter, correct tokenizer).
- **SC-004 (NMRG)**: Pre-existing tests pass unmodified; base install unaffected.

## Key Entities

- **EvaluationRun**: a comparison of model(s) on a prompt/held-out set, with samples + metrics.
- **MetricDelta**: the recorded base→fine-tuned change for the chosen metric.

## Definition of Done

- Side-by-side base-vs-fine-tuned samples + metric delta recorded; adapter + tokenizer-family handling
  correct; `track-only` refused; **NMRG (full)**.

## Assumptions

- Reuses the existing eval service rather than introducing a new evaluation framework.
- Benchmark-suite / standardized-eval harnesses are out of scope for v1 (qualitative + basic metrics
  first).
