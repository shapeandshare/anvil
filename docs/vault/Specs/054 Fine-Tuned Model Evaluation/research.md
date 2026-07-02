---
title: 054 Fine-Tuned Model Evaluation - research
type: research
tags:
  - type/research
  - domain/training
  - domain/mlops
  - status/draft
created: '2026-07-01'
updated: '2026-07-01'
---

# Research: Fine-Tuned Model Evaluation

Research conducted during `/speckit.clarify` and `/speckit.plan` for
[[Specs/054 Fine-Tuned Model Evaluation/054 Fine-Tuned Model Evaluation - spec|054 Fine-Tuned Model Evaluation]].

## 1. Existing Eval Service Structure

Source: `anvil/api/v1/eval.py`, `anvil/api/v1/schemas_eval.py`, `anvil/api/v1/eval_datasets.py`

### Endpoints

| Endpoint | Method | Request Model | Purpose |
|----------|--------|---------------|---------|
| `/eval/perplexity` | POST | `EvalPerplexityBody(model_id, version, text)` | Compute perplexity on a text string |
| `/eval-datasets` | POST | `CreateEvalDatasetBody(name, tags)` | Create MLflow managed eval dataset |
| `/eval-datasets/{name}/records` | POST | `AppendRecordsBody(records)` | Append records to eval dataset |
| `/eval-datasets/{name}` | GET | — | Get eval dataset |

### Decision

Reuse the existing eval-dataset infra (`POST /eval-datasets`) as the prompt source mechanism.
Reuse `POST /eval/perplexity` pattern for per-sample loss computation.

**Rationale**: The eval-dataset infra already creates MLflow managed datasets with append/retrieve
semantics. Creating a parallel prompt storage mechanism would violate Constitution Article XI (§11.4).

## 2. Existing Eval Computation

Source: `anvil/services/inference/inference.py`

### Key Methods

- `InferenceService.loss_breakdown(text, loaded) → dict` — computes per-position losses, average loss,
  random baseline, vocab size. Returns `{model, tokens, losses[], average_loss, random_baseline, vocab_size}`.
- `InferenceService.load_model(model_id, version, adapter_id) → LoadedModel` — loads model with optional
  adapter composition. `LoadedModel` fields: `model, tokenizer, model_id, version, name, adapter_path`.

### Decision

Reuse `InferenceService.loss_breakdown()` for per-sample loss computation on both base and fine-tuned
models. Reuse `load_model()` with `adapter_id` for adapter model evaluation (base+adapter composition).

**Rationale**: loss_breakdown() already computes the core metric (perplexity = exp(avg_loss)) needed for
eval. Writing a parallel loss computation would duplicate logic and risk divergence.

## 3. Existing MLflow Recording Pattern

Source: `anvil/services/tracking/tracking.py`

### Key Methods

- `TrackingService.start_run(run_name, params, engine_backend, device) → run_id`
- `TrackingService.log_metric(run_id, key, value, step)`
- `TrackingService.log_final_metric(run_id, key, value)`
- `TrackingService.set_tag(run_id, key, value)`
- `TrackingService.finish_run(run_id)`
- `TrackingService.fail_run(run_id, reason)`
- `TrackingService.create_eval_dataset(name, tags) → dataset`
- `TrackingService.append_eval_records(name, records) → count`
- `TrackingService.log_artifacts(run_id, local_dir, artifact_path)`

### MLflow Tag Conventions (from merge_service.py)

```python
tags = {
    "anvil.origin": "evaluation",       # NEW: distinguish from "merge" / "training"
    "anvil.entity_type": "evaluation",  # NEW: distinguish from "dataset" / "model"
    "anvil.base_model_ref": str(model_id),
    "anvil.fine_tuned_model_id": str(fine_tuned_model_id),  # NEW
    "anvil.adapter_id": adapter_id,      # nullable — set for adapter models
    "anvil.tokenizer_family": str(tokenizer_family),         # NEW
    "anvil.eval_status": "running",      # NEW: updated on completion
}
```

### Decision

Reuse the same `start_run → log_metric → set_tag → finish_run` pattern. Add evaluation-specific
MLflow tags following the existing `anvil.*` namespace convention.

## 4. Existing ORM Models to Reference

Source: `anvil/db/models/external_model.py`, `anvil/db/models/lora_adapter.py`

### ExternalModel (model registry)

Key fields: `id`, `display_name`, `source_type` (SourceType), `source_identifier`, `architecture_family`,
`tokenizer_family` (raw HF string), `runnable_status` (RunnableStatus — `RUNNABLE`/`TRACK_ONLY`),
`runnable_reason`, `asset_availability` (AssetState)

### LoRAAdapter (fine-tuned adapter)

Key fields: `id`, `external_model_id` (FK→base model), `run_id`, `adapter_id`, `label`, `method`
(`"lora"`/`"qlora"`), `storage_path`, `final_loss`, `final_step`, `merged_at`

### Decision

- `EvaluationRun.external_model_id` → FK to `ExternalModel.id` (fine-tuned model under evaluation)
- `EvaluationRun.base_external_model_id` → FK to `ExternalModel.id` (nullable — base model compared against)
- `EvaluationRun.adapter_id` → string reference to `LoRAAdapter.adapter_id` (nullable)
- `RunnableStatus.TRACK_ONLY` → refusal gate before starting any eval (FR-003)

## 5. Tokenizer Family Dispatch

Source: `anvil/services/_shared/tokenizer_family.py`, `anvil/db/models/external_model.py`

### Types

```python
class TokenizerFamily(StrEnum):
    CHAR = "char"
    SUBWORD = "subword"

class SerializationType(StrEnum):
    CHAR_JSON = "char_json"
    HF_FAST = "hf_fast"
    SENTENCEPIECE = "sentencepiece"
```

DB stores raw HF tokenizer class name strings (e.g. `"sentencepiece"`) in
`ExternalModel.tokenizer_family`. Mapping to `TokenizerFamily` happens at dispatch boundary
in `TokenizerFactory`.

### Decision

- Read `ExternalModel.tokenizer_family` as str from the model being evaluated
- Map to `TokenizerFamily` at dispatch boundary (not in DB)
- If base and fine-tuned use different families → two-column display (see spec)

## 6. Industry Eval-Run Data Model Survey

### Tools Surveyed

| Tool | Eval Run Model | Key Distinction |
|------|---------------|-----------------|
| MLflow | `EvaluationResult {metrics{}, artifacts{}, run_id, tables{}}` | Eval run is a lightweight sibling to training run; config/hardware on the parent Run |
| OpenAI Evals | `Run {id, eval_id, model, status, result_counts, per_model_usage, metadata{}}` | Model + sampling params on the run; hardware NOT captured |
| HuggingFace Evaluate | Flat metrics dict with `_git_commit_hash`, `_python_version` | Minimal — no Run concept; metadata optional |
| EleutherAI lm-eval-harness | `EvalResults {results{}, configs{}, versions{}, samples[], config{}}` | Most comprehensive — captures git_hash, seeds, model args, but NOT hardware |
| LangSmith | `TracerSession {id, name, description, reference_dataset_id}` | Explicit comparative eval support; hardware in traced runs, not eval-level |
| W&B Weave | `EvaluationRun {id, evaluation_id, model_ref, status, summary}` | EvaluationRun is lightweight; parent Run holds config/system_metrics |

### Universal Core Fields

`run_id`, `model_ref`, `dataset_ref`, `metrics{}`, `samples[]`, `status`, `created_at`, eval-level `config`

### Hardware/Environment: Delegated to Parent, Never on Eval Run

No surveyed tool stores hardware or environment info on the eval run itself. This is universally
delegated to the parent training run or model artifact metadata.

### Decision

Follow the industry pattern: **lineage-complete** eval run with `mlflow_run_id` pointer to the MLflow
run that holds full config/hardware/environment. Do NOT duplicate training hyperparameters,
compute/hardware, or environment snapshots onto `EvaluationRun`.

## 7. Async Evaluation Pattern

### Existing SSE Pattern

The training view (`/v1/training-page`) uses SSE to stream `StepMetrics` live. The SSE endpoint
pattern is: POST to trigger job → returns job_id → SSE endpoint at `/sse/{job_id}` streams events.

### Decision

Follow the same async SSE pattern:
- `POST /eval/fine-tuned` → triggers eval job, returns `{run_id, job_id}`
- `GET /sse/eval/{job_id}` → SSE stream of per-sample progress and metrics
- `GET /eval/fine-tuned/{run_id}` → fetch persisted final results

## 8. Key Design Decisions Summary

| Decision | Choice | Rationale |
|----------|--------|-----------|
| EvaluationRun schema | Lineage-complete with mlflow_run_id pointer | Industry pattern; no duplication (Art. XI) |
| Eval entry point | Dedicated Evaluate/Compare action on Models page | Follows anvil's page-per-domain convention |
| Prompt source | Existing eval-dataset infra + held-out split fallback | Reuse before introducing (Art. XI §11.4) |
| Cross-tokenizer display | Two columns with "—" delta + caveat label | Presents all data without false comparison |
| Async pattern | SSE job-based (matches training pattern) | Existing SSE infra; non-trivial CPU eval time |
| New domain service | `services/evaluation/` sub-package | Follows DDD decomposition (Art. X) |
| No new dependencies | All existing stack | Constitution Articles I, XI |
| Track-only refusal | Gate on `RunnableStatus.TRACK_ONLY` before eval starts | Reuses existing FR-009a enforcement |