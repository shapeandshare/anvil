---
title: 054 Fine-Tuned Model Evaluation - quickstart
type: design
tags:
  - type/design
  - domain/training
  - domain/mlops
  - status/draft
created: '2026-07-01'
updated: '2026-07-01'
---

# Quickstart: Fine-Tuned Model Evaluation

## Prerequisites

- A fine-tuned model registered in the model registry (`ExternalModel` with `runnable_status = RUNNABLE`)
- Its base model also registered (`ExternalModel`)
- Either:
  - An MLflow eval-dataset created via `POST /eval-datasets` with prompt records
  - A training dataset associated with the fine-tuned model (auto-derives held-out split)

## Flow

1. **Prepare eval dataset** (optional — skip if using held-out split):
   ```
   POST /v1/eval-datasets
   {"name": "my-eval-set", "tags": {"purpose": "fine-tune-comparison"}}
   
   POST /v1/eval-datasets/my-eval-set/records
   {"records": [{"input": "The capital of France is"}, {"input": "Water freezes at"}]}
   ```

2. **Trigger evaluation**:
   ```
   POST /v1/eval/fine-tuned
   {
     "model_id": 42,
     "base_model_id": 40,
     "adapter_id": "run_42",
     "eval_dataset_name": "my-eval-set"
   }
   ```
   
   Response: `{"run_id": 1, "status": "pending", "sse_url": "/v1/sse/eval/1"}`

3. **Stream progress** (SSE):
   ```
   GET /v1/sse/eval/{run_id}
   ```
   
   Events arrive as each prompt is evaluated. Final `complete` event signals done.

4. **View results**:
   ```
   GET /v1/eval/fine-tuned/{run_id}       # Summary + metrics
   GET /v1/eval/fine-tuned/{run_id}/samples  # Per-prompt side-by-side outputs
   ```

5. **Browse UI**: Navigate to `/v1/models-page`, select a fine-tuned model, click "Evaluate/Compare",
   choose eval dataset, and view the dedicated eval-compare page.

## Testing

```bash
# Unit tests
make test-unit
# E2E tests
make test-e2e
```

Key test scenarios:
- `test_evaluation_run_orm.py` — CRUD lifecycle of EvaluationRun + MetricDelta + EvalSample
- `test_evaluation_repository.py` — repository pattern query methods
- `test_evaluator.py` — per-sample loss computation, tokenizer dispatch, adapter composition
- `test_evaluation.py` (e2e) — full POST → SSE → GET cycle; track-only refusal; cross-tokenizer
