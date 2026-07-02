---
title: 054 Fine-Tuned Model Evaluation - API contracts
type: design
tags:
  - type/design
  - domain/training
  - domain/mlops
  - status/draft
created: '2026-07-01'
updated: '2026-07-01'
---

# API Contracts: Fine-Tuned Model Evaluation

## Endpoints

### POST /v1/eval/fine-tuned

Trigger an async fine-tuned model evaluation.

**Request**:

```json
{
  "model_id": 42,
  "base_model_id": 40,
  "adapter_id": "run_42",
  "eval_dataset_name": "my-eval-set"
}
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `model_id` | `int` | Yes | — | ExternalModel.id of the fine-tuned model |
| `base_model_id` | `int` | Yes | — | ExternalModel.id of the base model |
| `adapter_id` | `str\|None` | No | `null` | LoRAAdapter.adapter_id for adapter models |
| `eval_dataset_name` | `str\|None` | No | `null` | Name of existing MLflow eval-dataset. If null, auto-derive held-out split |

**Response** (201 Created):

```json
{
  "run_id": 1,
  "status": "pending",
  "sse_url": "/v1/sse/eval/1"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `run_id` | `int` | EvaluationRun.id for the created run |
| `status` | `str` | `"pending"` — initial state |
| `sse_url` | `str` | Relative URL for SSE streaming endpoint |

**Errors**:

| Status | Condition |
|--------|-----------|
| 400 | `model_id` references a `track-only` model (refused per FR-003) |
| 400 | `eval_dataset_name` not found AND no training dataset for held-out split |
| 404 | `model_id` or `base_model_id` not found |
| 404 | `adapter_id` not found for `(model_id, adapter_id)` combination |

---

### GET /v1/sse/eval/{run_id}

SSE stream for evaluation progress.

**Events**:

| Event | Data | When |
|-------|------|------|
| `status` | `{"status": "running"}` | Stream opens, evaluation starts |
| `progress` | `{"prompt_index": 5, "total": 20, "base_loss": 2.1, "fine_tuned_loss": 1.8}` | Per-sample progress update |
| `metric` | `{"metric_name": "eval_loss", "fine_tuned_value": 1.75, "base_value": 2.1, "delta": -0.35, "comparable": true}` | Final aggregated metric |
| `complete` | `{"run_id": 1, "status": "completed", "samples_url": "/v1/eval/fine-tuned/1/samples"}` | All prompts evaluated, results persisted |
| `error` | `{"message": "Failed to load model: ..."}` | Unrecoverable error |

---

### GET /v1/eval/fine-tuned/{run_id}

Fetch persisted evaluation run details.

**Response** (200 OK):

```json
{
  "run_id": 1,
  "model_id": 42,
  "model_name": "My Fine-Tuned Model",
  "base_model_id": 40,
  "base_model_name": "Base Model",
  "adapter_id": "run_42",
  "tokenizer_family": "subword",
  "base_tokenizer_family": "char",
  "status": "completed",
  "prompt_count": 20,
  "metrics": [
    {
      "metric_name": "eval_loss",
      "fine_tuned_value": 1.75,
      "base_value": 2.1,
      "delta": -0.35,
      "comparable": false
    }
  ],
  "created_at": "2026-07-01T12:00:00Z",
  "started_at": "2026-07-01T12:00:01Z",
  "finished_at": "2026-07-01T12:00:45Z",
  "mlflow_run_id": "abc123..."
}
```

---

### GET /v1/eval/fine-tuned/{run_id}/samples

Fetch per-prompt sample outputs.

**Response** (200 OK):

```json
{
  "run_id": 1,
  "samples": [
    {
      "prompt_index": 0,
      "input": "Once upon a",
      "base_output": "time there was",
      "fine_tuned_output": "time in a land far",
      "base_loss": 2.1,
      "fine_tuned_loss": 1.8
    }
  ]
}
```

---

### GET /v1/eval/fine-tuned

List evaluation runs. Supports pagination.

**Query params**: `?limit=20&offset=0&model_id=42&status=completed`

**Response** (200 OK):

```json
{
  "runs": [
    {
      "run_id": 1,
      "model_id": 42,
      "model_name": "My Fine-Tuned Model",
      "status": "completed",
      "prompt_count": 20,
      "created_at": "2026-07-01T12:00:00Z",
      "mlflow_run_id": "abc123..."
    }
  ],
  "total": 5,
  "limit": 20,
  "offset": 0
}
```

## SSE Event Format (non-standard — anvil convention)

```
event: {event_type}
data: {json_payload}
\n\n
```

`event` field is type `str`. `data` is a single JSON line. This matches the existing anvil training SSE
convention (not the Server-Sent Events standard `event:` / `data:` wrapping, but the simpler approach
already used in the codebase).

## God Class Integration

```python
class AnvilWorkbench:
    async def evaluate_fine_tuned(
        self,
        *,
        model_id: int,
        base_model_id: int,
        adapter_id: str | None = None,
        eval_dataset_name: str | None = None,
    ) -> EvaluationRunResponse:
        ...

    async def get_evaluation_run(
        self,
        run_id: int,
    ) -> EvaluationRunResponse:
        ...

    async def get_evaluation_samples(
        self,
        run_id: int,
    ) -> list[EvalSampleResponse]:
        ...

    async def list_evaluation_runs(
        self,
        *,
        model_id: int | None = None,
        status: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> EvaluationRunListResponse:
        ...
```

## Pydantic Models

All new models in `anvil/api/v1/schemas_eval.py`:

```python
class EvalFineTunedBody(BaseModel):
    model_id: int
    base_model_id: int
    adapter_id: str | None = None
    eval_dataset_name: str | None = None

class MetricDeltaResponse(BaseModel):
    metric_name: str
    fine_tuned_value: float
    base_value: float
    delta: float
    comparable: bool = True

class EvalSampleResponse(BaseModel):
    prompt_index: int
    input: str
    base_output: str | None = None
    fine_tuned_output: str | None = None
    base_loss: float | None = None
    fine_tuned_loss: float | None = None

class EvaluationRunResponse(BaseModel):
    run_id: int
    model_id: int
    model_name: str
    base_model_id: int
    base_model_name: str
    adapter_id: str | None = None
    tokenizer_family: str
    base_tokenizer_family: str | None = None
    status: str
    prompt_count: int
    metrics: list[MetricDeltaResponse] = []
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    mlflow_run_id: str | None = None

class EvaluationRunListResponse(BaseModel):
    runs: list[EvaluationRunResponse]
    total: int
    limit: int
    offset: int
```