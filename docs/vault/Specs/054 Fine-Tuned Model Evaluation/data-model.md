---
title: 054 Fine-Tuned Model Evaluation - data model
type: design
tags:
  - type/design
  - domain/training
  - domain/mlops
  - status/draft
created: '2026-07-01'
updated: '2026-07-01'
---

# Data Model: Fine-Tuned Model Evaluation

## Entities

### EvaluationRun

A single evaluation comparison of a fine-tuned model against its base model on a shared prompt set.

**Table**: `evaluation_runs`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | `Integer` | PK, autoincrement | Unique identifier |
| `external_model_id` | `Integer` | FK → `external_models.id`, NOT NULL | The fine-tuned model under evaluation |
| `base_external_model_id` | `Integer` | FK → `external_models.id`, NULLABLE | The base model compared against (NULL for from-scratch) |
| `adapter_id` | `String(255)` | NULLABLE | Scoped adapter ID if evaluating an adapter model |
| `tokenizer_family` | `String(100)` | NOT NULL | Tokenizer family of the fine-tuned model (043 dispatch) |
| `base_tokenizer_family` | `String(100)` | NULLABLE | Tokenizer family of the base model (for cross-tokenizer comparison) |
| `eval_dataset_name` | `String(255)` | NULLABLE | Name of the MLflow eval-dataset used (NULL if held-out split used) |
| `status` | `String(20)` | NOT NULL, default `"pending"` | Run status: `pending` → `running` → `completed`/`failed` |
| `mlflow_run_id` | `String(255)` | NULLABLE | Pointer to the MLflow run holding full config/environment/hardware snapshot |
| `prompt_count` | `Integer` | NOT NULL, default 0 | Number of prompts evaluated |
| `meta` | `Text` | NULLABLE | JSON-encoded metadata (not for query — use mlflow_run_id for full context) |
| `started_at` | `DateTime` | NULLABLE | When evaluation started |
| `finished_at` | `DateTime` | NULLABLE | When evaluation completed/failed |
| `error_message` | `Text` | NULLABLE | Error detail if `status = "failed"` |
| `created_at` | `DateTime` | NOT NULL, auto | TimestampMixin |
| `updated_at` | `DateTime` | NOT NULL, auto | TimestampMixin |

**Indexes**:
- `(external_model_id)` — find all evaluations for a model
- `(base_external_model_id)` — find all evaluations comparing against a base
- `(status)` — filter by lifecycle state
- `(created_at)` — chronological listing

**Uniqueness**: None — a model may be evaluated multiple times with different prompt sets.

### MetricDelta

A recorded base→fine-tuned metric comparison within an evaluation run.

**Table**: `metric_deltas`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | `Integer` | PK, autoincrement | Unique identifier |
| `evaluation_run_id` | `Integer` | FK → `evaluation_runs.id`, NOT NULL, CASCADE | Parent evaluation run |
| `metric_name` | `String(100)` | NOT NULL | Metric name, e.g. `"eval_loss"`, `"perplexity"` |
| `fine_tuned_value` | `Float` | NOT NULL | Metric value for the fine-tuned model |
| `base_value` | `Float` | NOT NULL | Metric value for the base model |
| `delta` | `Float` | NOT NULL | `fine_tuned_value - base_value` (pre-computed for queryability) |
| `comparable` | `Boolean` | NOT NULL, default true | Whether the metrics are directly comparable (false when tokenizer families differ) |
| `created_at` | `DateTime` | NOT NULL, auto | TimestampMixin |

**Indexes**:
- `(evaluation_run_id)` — all deltas for a run
- `(evaluation_run_id, metric_name)` — find a specific metric in a run

**Uniqueness**: `(evaluation_run_id, metric_name)` — one delta per metric per run.

### EvalSample

A single per-prompt sample output within an evaluation run.

**Table**: `eval_samples`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | `Integer` | PK, autoincrement | Unique identifier |
| `evaluation_run_id` | `Integer` | FK → `evaluation_runs.id`, NOT NULL, CASCADE | Parent evaluation run |
| `prompt_index` | `Integer` | NOT NULL | Positional index in the prompt set |
| `input` | `Text` | NOT NULL | The prompt text |
| `base_output` | `Text` | NULLABLE | Base model's generated output |
| `fine_tuned_output` | `Text` | NULLABLE | Fine-tuned model's generated output |
| `base_loss` | `Float` | NULLABLE | Per-sample loss for base model (if computed) |
| `fine_tuned_loss` | `Float` | NULLABLE | Per-sample loss for fine-tuned model |
| `created_at` | `DateTime` | NOT NULL, auto | TimestampMixin |

**Indexes**:
- `(evaluation_run_id)` — all samples for a run
- `(evaluation_run_id, prompt_index)` — ordered retrieval

**Uniqueness**: `(evaluation_run_id, prompt_index)` — one entry per prompt per run.

## Enums

### EvaluationRunStatus (StrEnum)

```python
class EvaluationRunStatus(StrEnum):
    PENDING = "pending"     # Created but not started
    RUNNING = "running"     # Evaluation in progress (SSE active)
    COMPLETED = "completed" # All prompts evaluated, results persisted
    FAILED = "failed"       # Evaluation failed with error_message
```

**File**: `anvil/services/_shared/evaluation_status.py` (in `_shared/` since it's consumed by both
`evaluation/` service and `api/v1/` routes — cross-domain per §10.3).

## Relationships

```
EvaluationRun ──1:N──→ MetricDelta  (via evaluation_run_id, CASCADE delete)
EvaluationRun ──1:N──→ EvalSample   (via evaluation_run_id, CASCADE delete)
EvaluationRun ──N:1──→ ExternalModel  (via external_model_id = fine-tuned model)
EvaluationRun ──N:1──→ ExternalModel  (via base_external_model_id = base model, nullable)
EvaluationRun ──?...?──→ LoRAAdapter  (via external_model_id + adapter_id composite lookup, not a DB FK)
```

## State Transitions

```
[PENDING] ──start()──→ [RUNNING] ──complete()──→ [COMPLETED]
                                    ──fail()─────→ [FAILED]
```

- `PENDING → RUNNING`: When SSE stream starts
- `RUNNING → COMPLETED`: When all prompts evaluated and results written
- `RUNNING → FAILED`: On unrecoverable error (model load failure, adapter resolution failure)
- No other transitions valid; no re-running of a completed run

## Validation Rules

1. **FR-003 (track-only refusal)**: Before creating an `EvaluationRun`, verify
   `ExternalModel.runnable_status != RunnableStatus.TRACK_ONLY`. If track-only, refuse with
   `ExternalModel.runnable_reason`.
2. **FR-001 (tokenizer dispatch)**: Read `ExternalModel.tokenizer_family` for both models at
   evaluation time. Store on `EvaluationRun` for later comparison display.
3. **FR-002 (lineage)**: `mlflow_run_id` MUST be non-NULL on completion (set when MLflow run finishes).
4. **FR-004 (prompt source)**: If `eval_dataset_name` is NULL, evaluation MUST validate that a
   held-out split can be derived from the model's training data. NOTE: no split field exists on
   `FineTuneDataset` / `Dataset` / `Sample` today — deriving a split is NET-NEW seeded work (Article III)
   and MAY be deferred, in which case a NULL `eval_dataset_name` refuses with a clear message.
5. **FR-005 (async)**: Status MUST be `RUNNING` while SSE stream is active.
   Results MUST be fully persisted before transition to `COMPLETED`.
6. **FR-006 (model resolution)**: `external_model_id` / `base_external_model_id` reference
   `ExternalModel.id`, but `InferenceService.load_model` does NOT resolve `ExternalModel` PKs directly
   (it uses filesystem experiment artifacts + MLflow registry names). The service MUST map the
   `ExternalModel` to a `load_model`-serviceable identifier (e.g. `source_identifier`/experiment id)
   OR extend `load_model` — verified against real behavior before completion.
7. **Cross-tokenizer**: If `tokenizer_family != base_tokenizer_family`, all `MetricDelta` rows for
   this run MUST have `comparable = false`.
