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
updated: '2026-07-01'
---

# Feature Specification: Fine-Tuned Model Evaluation

**Feature Branch**: `054-fine-tuned-model-evaluation`
**Created**: 2026-06-28
**Status**: Draft
**Parent Spec**: [[Specs/038 Fine-Tuning Arc/038 Fine-Tuning Arc|038 Fine-Tuning Arc (umbrella)]]

## Overview

Answers the question every fine-tune raises: **did it help?** Provides side-by-side comparison of a
fine-tuned model against its base — qualitative samples on the same prompts (via
`InferenceService.generate`) and quantitative metrics (e.g. eval loss / held-out perplexity, via
`InferenceService.loss_breakdown`) — reusing the existing inference/eval service and surfacing results
in the experiment/registry UI. Applies to native warm-start (039) and external/adapter (044/045)
models alike, dispatching on the recorded tokenizer family (043).

### Scope

| Dimension | Scope |
|-----------|-------|
| **Owned FRs** | FR-035 (+ spec-local FR-001..FR-006) |
| **Owned decisions** | reuses FT-AD-7 (base+adapter), FT-AD-10 (pedagogy) |
| **Depends on** | `InferenceService.generate` + `.loss_breakdown` + `.load_model` (`anvil/services/inference/inference.py`); `TrackingService` (`anvil/services/tracking/tracking.py`); eval-dataset infra (`anvil/api/v1/eval_datasets.py`); 045 (adapter inference); 040 (models); 043 (tokenizer dispatch) |
| **Invariant risk** | **LOW** — extends evaluation; no change to pretraining or base install |

---

## Clarifications

### Session 2026-07-01

- Q: What attributes should an `EvaluationRun` entity carry? → A: **Lineage-complete** — the eval run is a
  lightweight measurement that references the model(s), prompt set, metrics, and metric delta, plus a
  pointer (`mlflow_run_id`) to the MLflow run that holds the full config/hardware/environment snapshot.
  It does **NOT** duplicate training hyperparameters, compute/hardware info, or environment snapshots onto
  the eval run — those already live on `ExternalModel` / `LoRAAdapter` / the MLflow run (Constitution
  Article XI: reuse before introducing, no duplication). This matches the universal industry pattern
  (MLflow, OpenAI Evals, LangSmith, W&B, lm-eval-harness) where the eval run points at the heavy
  experiment record rather than copying it.
- Q: Where does the side-by-side comparison surface, and how is an evaluation triggered? → A: A
  dedicated **Evaluate/Compare** action on the **Models page** (`/v1/models-page`) launches a new
  eval-compare view that shows the side-by-side samples and metric delta. Results are **also recorded**
  to the experiment/registry so they are viewable from the Experiments page. This follows anvil's
  page-per-domain UI convention and the "learner picks a fine-tuned model" user story.
- Q: How does the learner supply the prompt/held-out set for an evaluation? → A: The primary
  mechanism is **selecting an existing named eval-dataset** (reusing the MLflow-backed
  `create_eval_dataset` / `append_eval_records` infra at `POST /eval-datasets`). If no
  eval-dataset is chosen, the system auto-derives a **labeled held-out split** from the model's
  training dataset. Ad-hoc inline prompt entry is not supported — prompts must come from a
  persisted eval-dataset or a held-out split (Constitution Article XI: reuse before introducing).
- Q: How should the compare view handle non-comparable metrics across tokenizer families? → A: When
  base and fine-tuned use different tokenizer families (char vs. subword), the eval-compare view shows
  **two metric columns side by side** with a visible caveat label ("Not directly comparable — different
  tokenizers") on the delta row. The numeric delta is replaced with "—". This presents all the data
  without implying a false comparison.
- Q: What is the expected latency/throughput for an evaluation run? → A: **Async job-based** — POST
  triggers the eval, returns a `run_id`, and SSE (served at a separate `GET /v1/sse/eval/{run_id}`
  endpoint) streams progress/metrics as they arrive. Final results are persisted and fetchable via GET.
  This matches the existing training pattern (`run_id` + `asyncio.create_task` + raw
  `StreamingResponse`) and accounts for the non-trivial runtime of evaluating a held-out set on CPU.

---

## User Story

### US — Learner Compares a Fine-Tuned Model to Its Base (Priority: P1)

A learner runs the same prompts through a fine-tuned model and its base, sees outputs side by side, and
views metrics indicating whether the fine-tune improved on the target task. The learner starts this from
an **Evaluate/Compare** action on the Models page (`/v1/models-page`), which opens a dedicated
eval-compare view; the results are also recorded to the experiment/registry.

**Independent Test**: With a base model and a fine-tuned variant (warm-start or adapter), run an
evaluation on a small held-out split; verify side-by-side samples and a metric delta are displayed and
recorded.

**Acceptance Scenarios**:

1. **Given** a fine-tuned model and its base, **When** the learner triggers Evaluate/Compare from the
   Models page and runs an evaluation on a held-out split, **Then** the dedicated eval-compare view shows
   side-by-side sample outputs on identical prompts.
2. **Given** the same evaluation, **When** it completes, **Then** quantitative metrics (e.g. eval loss /
   perplexity) and the base→fine-tuned delta are recorded in the experiment/registry.
3. **Given** an adapter model, **When** evaluated, **Then** inference composes base+adapter (045) and the
   correct tokenizer family is used (043).
4. **Given** a `track-only` model, **When** evaluation is attempted, **Then** it is refused with a clear
   message (consistent with FR-009a).

### Edge Cases

- No eval-dataset selected and no training dataset available → evaluation is refused with a clear
  message; do not proceed without input prompts.
- No eval-dataset selected but a training dataset exists → auto-derive a labeled held-out split;
  clearly label the split as held-out; do not silently evaluate on full training data.
- Base and fine-tuned use different tokenizers (warm-start keeps char-level; external uses subword) →
  metrics are computed per the model's own tokenizer and labeled accordingly.
- Non-comparable metrics across tokenizer families → show two metric columns side by side, replace
  the numeric delta with "—", and display a caveat label ("Not directly comparable — different
  tokenizers") on the delta row. Do not hide data, but do not imply a false comparison.

## Requirements

- **FR-035**: The system MUST support evaluating a fine-tuned model against its base — qualitative
  side-by-side samples on identical prompts (via `InferenceService.generate`, which returns generated
  text) and quantitative metrics (via `InferenceService.loss_breakdown`, which returns per-token loss /
  average loss) — recording results in the experiment/registry via `TrackingService` (MLflow).
  NOTE: `loss_breakdown` produces losses only, NOT text; sample outputs come from `generate`. The two
  are combined by the new `Evaluator` (this feature is net-new orchestration over existing primitives).
- **FR-001** (spec-local): Evaluation MUST dispatch on the model's recorded tokenizer family (043) and,
  for adapter models, compose base+adapter via 045 (`InferenceService.load_model(adapter_id=...)`,
  which is already implemented via PEFT composition).
- **FR-002** (spec-local): Evaluation MUST record the base→fine-tuned metric delta and the prompt set
  used, for reproducibility and lineage. The `EvaluationRun` MUST reference the full config/hardware/
  environment via an `mlflow_run_id` pointer rather than duplicating training hyperparameters,
  compute/hardware, or environment snapshots onto the eval run (those already live on
  `ExternalModel` / `LoRAAdapter` / the MLflow run — Constitution Article XI).
- **FR-003** (spec-local): Evaluation MUST refuse `track-only` models (FR-009a) with a clear message.
- **FR-004** (spec-local): The prompt/hold-out set MUST be sourced from either (a) a user-selected
  named eval-dataset (reusing the existing MLflow-backed `POST /eval-datasets` infra), or (b) an
  auto-derived held-out split of the model's training data. Ad-hoc inline prompt entry is not supported.
  IMPORTANT — no held-out-split capability exists today: `FineTuneDataset` stores a single
  `prepared_file_path` with all records and neither `Dataset` nor `Sample` has any split field.
  Implementing (b) therefore requires NEW work — deriving a deterministic (seeded, per Constitution
  Article III) held-out subset of the prepared records at evaluation time, clearly labeled as held-out.
  For v1, path (a) — a user-selected eval-dataset — is the PRIMARY and REQUIRED mechanism; path (b) is
  the fallback and MAY be deferred if the split-derivation work is scoped out (in which case "no
  eval-dataset selected" refuses with a clear message per the edge cases).
- **FR-005** (spec-local): Evaluation MUST run as an **async job** — POST triggers the evaluation and
  returns a `run_id`; SSE is served at a separate `GET /v1/sse/eval/{run_id}` endpoint (matching the
  training pattern: `run_id` + `asyncio.create_task` + raw `StreamingResponse`, NOT a FastAPI
  `BackgroundTasks` or `job_id` polling model); final results are persisted and fetchable via GET.
- **FR-006** (spec-local): Evaluation MUST resolve the model(s) under evaluation through a path that
  `InferenceService.load_model` can actually service. The current `load_model(model_id, version, ...)`
  resolves via filesystem experiment artifacts and MLflow registry names — it does NOT resolve an
  `ExternalModel` primary key directly. Therefore the eval service MUST either (a) map the referenced
  `ExternalModel` to its `source_identifier`/experiment id before calling `load_model`, or (b) extend
  `load_model` with an explicit `ExternalModel`-lookup path. The chosen resolution path MUST be
  verified against the real `load_model` behavior before implementation is considered complete.

## Success Criteria

- **SC-001**: A learner triggers Evaluate/Compare from the Models page, selects an eval-dataset (or
  uses a held-out split), and sees base-vs-fine-tuned side-by-side samples + metric delta in the
  dedicated eval-compare view.
- **SC-002**: Results are recorded as an `EvaluationRun` with the prompt set, model lineage, and a
  pointer (`mlflow_run_id`) to the MLflow run for full config/environment/hardware provenance.
- **SC-003**: Adapter models evaluate correctly (base+adapter via 045, correct tokenizer via 043).
- **SC-004**: Cross-tokenizer comparisons show two metric columns with "—" delta and a caveat label;
  no false comparison implied.
- **SC-005**: Evaluation runs as an async job (POST → `run_id`) with SSE streaming at
  `GET /v1/sse/eval/{run_id}`; per-sample progress and final metrics are delivered via SSE.
- **SC-006 (NMRG)**: Pre-existing tests pass unmodified; base install unaffected.
- **SC-007**: `track-only` models are refused with a clear message when evaluation is attempted.
- **SC-008**: Sample outputs are produced by `InferenceService.generate` (text) and metrics by
  `InferenceService.loss_breakdown` (loss); the model(s) are resolved through a path `load_model`
  can actually service (per FR-006), verified end-to-end on a real base+fine-tuned pair.

## Key Entities

- **EvaluationRun** (lineage-complete): a comparison of model(s) on a prompt/held-out set. Attributes:
  - **Identity**: `id`, `status`, `started_at`, `finished_at`.
  - **Model references**: `external_model_id` (fine-tuned model under evaluation),
    `base_external_model_id` (nullable — the base it is compared against),
    `adapter_id` (nullable — set for adapter models; resolved to the `LoRAAdapter` via
    `(external_model_id, adapter_id)` for base+adapter composition per 045).
  - **Dispatch**: `tokenizer_family` (the model's recorded tokenizer family per 043).
  - **Inputs/outputs**: the `prompt_set` used and the per-prompt side-by-side samples.
  - **Metrics**: `metrics{}` (e.g. eval loss / perplexity) and the recorded `metric_delta`.
  - **Provenance pointer**: `mlflow_run_id` — points to the MLflow run holding the full
    config/hardware/environment snapshot. The eval run does **not** duplicate training
    hyperparameters, compute/hardware, or environment info (Constitution Article XI).
- **MetricDelta**: the recorded base→fine-tuned change for the chosen metric.

## Definition of Done

- **API**: `POST /v1/eval/fine-tuned` (returns `run_id`, triggers async job) + `GET /v1/sse/eval/{run_id}`
  (SSE) + `GET /v1/eval/fine-tuned/{run_id}` (fetch persisted results) — all with typed request/response
  Pydantic models.
- **Compute**: Sample text via `InferenceService.generate`; metrics via `InferenceService.loss_breakdown`;
  models resolved through a `load_model`-serviceable path (FR-006).
- **Metrics**: Recorded metrics include eval loss and perplexity; the `MetricDelta.metric_name` field
  is extensible to future metrics.
- **UI**: Evaluate/Compare action on the Models page → dedicated eval-compare view with side-by-side
  samples + metric delta; caveat label for cross-tokenizer comparisons.
- **Asynchronicity**: SSE stream for per-sample progress; final results persisted in DB.
- **Dispatch**: Adapter models compose base+adapter (045); correct tokenizer family used (043);
  `track-only` models refused with clear message.
- **Lineage**: `EvaluationRun` records model references, prompt set, metrics/metric_delta, and
  `mlflow_run_id` pointer to the MLflow run for full config/environment/hardware provenance.
- **NMRG (full)**: Pre-existing tests pass unmodified; base install unaffected.

## Assumptions

- Reuses existing inference/tracking primitives (`InferenceService.generate`,
  `InferenceService.loss_breakdown`, `TrackingService`) rather than introducing a new evaluation
  framework. The `Evaluator` / `EvaluationService` orchestration over these primitives is net-new.
- Benchmark-suite / standardized-eval harnesses are out of scope for v1 (qualitative + basic metrics
  first).

## Known Capability Gaps (verified against codebase, 2026-07-01)

These are net-new work items, not existing capabilities the feature can assume:

- **Side-by-side samples require `generate`, not `loss_breakdown`**: `loss_breakdown` returns losses
  only. Text samples come from `InferenceService.generate` (returns `str`). The `Evaluator` combines both.
- **Model resolution is not `ExternalModel.id`-native**: `InferenceService.load_model` resolves via
  filesystem experiment artifacts + MLflow registry names, not `ExternalModel` primary keys. FR-006
  requires an explicit resolution path.
- **No held-out-split mechanism exists**: `FineTuneDataset` stores one `prepared_file_path`; `Dataset`
  and `Sample` have no split field. FR-004 path (b) is net-new work (seeded split derivation) and MAY
  be deferred, with a user-selected eval-dataset (path a) as the required v1 mechanism.
- **Adapter composition already works**: `load_model(adapter_id=...)` performs PEFT base+adapter
  composition — this is the one dependency that is fully implemented today.
