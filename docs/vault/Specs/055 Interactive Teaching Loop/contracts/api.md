# API Contracts: Interactive Teaching Loop (055)

Base path: `/v1/teach`

> **ID semantics (critical)**: All model references in this API are **native integer experiment ids** — the identifier that persists `data/models/experiment_{id}.json` and is consumed by `InferenceService.load_model(model_id)` and warm-start `TrainConfig.base_model_ref`. These are NOT `ExternalModel.id`. All request/response bodies MUST be Pydantic `BaseModel` (constitution).

## Page Route

### `GET /v1/teach`

Renders the dedicated teaching page.

**Response**: `HTMLResponse` (Jinja2 template `teach.html`)

**Template context**: `{ "sessions": [...], "related_lessons": [...] }`

---

## Session Management

### `POST /v1/teach/sessions`

Create a new teaching session.

**Request body**:
```json
{
  "name": "Teaching to rhyme",
  "description": "Optional",
  "seed_experiment_id": 55
}
```
`seed_experiment_id` is optional. Omit/null = round 1 trains from scratch. When present, it must resolve to an existing loadable artifact (validated via `InferenceService.load_model`).

**Response** `201 Created`:
```json
{
  "id": 1,
  "name": "Teaching to rhyme",
  "description": "Optional",
  "seed_experiment_id": 55,
  "current_base_experiment_id": 55,
  "status": "draft",
  "created_at": "2026-07-02T12:00:00Z",
  "updated_at": "2026-07-02T12:00:00Z"
}
```
(`current_base_experiment_id` initialized to `seed_experiment_id`, or null if training from scratch.)

**Errors**: `422` if `seed_experiment_id` is set but has no loadable artifact.

---

### `GET /v1/teach/sessions`

List teaching sessions.

**Query params**: `status` (draft/active/completed), `limit` (default 20), `offset` (default 0).

**Response** `200`: `{ "sessions": [...], "total": 5 }`

---

### `GET /v1/teach/sessions/{session_id}`

Get a session with its round lineage.

**Response** `200`:
```json
{
  "id": 1,
  "name": "Teaching to rhyme",
  "status": "active",
  "seed_experiment_id": 55,
  "current_base_experiment_id": 57,
  "rounds": [
    {
      "round_index": 1,
      "mlflow_run_id": "abc123",
      "experiment_id": 56,
      "parent_experiment_id": 55,
      "dataset_id": 10,
      "status": "FINISHED",
      "created_at": "2026-07-02T12:00:00Z"
    },
    {
      "round_index": 2,
      "mlflow_run_id": "def456",
      "experiment_id": 57,
      "parent_experiment_id": 56,
      "dataset_id": 11,
      "status": "FINISHED",
      "created_at": "2026-07-02T12:05:00Z"
    }
  ],
  "created_at": "2026-07-02T12:00:00Z",
  "updated_at": "2026-07-02T12:05:00Z"
}
```

Round lineage is derived from MLflow runs tagged `teaching_session_id={id}`.

---

### `PATCH /v1/teach/sessions/{session_id}`

Update session metadata or status.

**Request body** (partial): `{ "name": "...", "status": "completed" }`

**Response** `200`: Updated session.

**Errors**: `409` transitioning FROM `completed`; `409` marking complete while a round is training.

---

### `DELETE /v1/teach/sessions/{session_id}`

Delete a session. MUST respond `204` and MUST NOT cascade to MLflow runs or experiment artifacts (they remain independently accessible). If the session has rounds, include a warning header/log.

**Response** `204 No Content`.

---

## Round Operations

### `POST /v1/teach/sessions/{session_id}/rounds`

Start a new teaching round: create a dataset from the examples (origin=teaching), then start a warm-start training run via `TrainingRunService` (warm-starting from the session's `current_base_experiment_id`).

**Request body**:
```json
{
  "examples": ["line 1", "line 2"],
  "training_config": {
    "num_steps": 200,
    "learning_rate": 0.01,
    "temperature": 0.5,
    "compute_backend": "auto"
  }
}
```
The service populates `dataset_id`, `base_model_ref` (= `current_base_experiment_id`), and `method="full"`. `method` is forced to `full` — LoRA is out of MVP scope and rejected with `422`.

**Response** `201 Created`:
```json
{
  "round_index": 3,
  "run_id": 42,
  "mlflow_run_id": "ghi789",
  "experiment_id": 58,
  "status": "running",
  "stream_url": "/v1/training/stream/42"
}
```

> **SSE**: The frontend connects DIRECTLY to `stream_url` (`/v1/training/stream/{run_id}`) — the existing training stream (process-local `asyncio.Queue`). Teaching does NOT proxy the stream.

`current_base_experiment_id` is updated to the round's `experiment_id` ONLY after training finalizes successfully (observed via the stream `complete` event / round status).

**Errors**: `400` if a round is already training for this session; `422` if `method` is not `full`, or if `current_base_experiment_id` has no loadable artifact.

---

### `GET /v1/teach/sessions/{session_id}/rounds`

List rounds for a session (from MLflow tags). **Response** `200`: array of round descriptors.

---

### `POST /v1/teach/sessions/{session_id}/rounds/{round_index}/inspect`

Generate inference outputs from a finalized round's model via `InferenceService.generate()`.

**Request body**:
```json
{ "prompts": ["Once upon a time"], "temperature": 0.5, "max_tokens": 50 }
```

**Response** `200`:
```json
{ "outputs": [ { "prompt": "Once upon a time", "generated": "..." } ] }
```

**Errors**: `400` if the round is not FINISHED.

---

### `POST /v1/teach/sessions/{session_id}/compare`

**MVP compare = side-by-side inference.** Generate outputs for the same prompts from two rounds' models (or a round vs. the seed) and return them for visual comparison. This does NOT use `EvaluationService` (deferred — needs `ExternalModel.id`).

**Request body**:
```json
{
  "left_experiment_id": 56,
  "right_experiment_id": 58,
  "prompts": ["Test prompt"],
  "temperature": 0.5,
  "max_tokens": 50
}
```

**Response** `200`:
```json
{
  "comparisons": [
    {
      "prompt": "Test prompt",
      "left": { "experiment_id": 56, "generated": "..." },
      "right": { "experiment_id": 58, "generated": "..." }
    }
  ]
}
```

**Errors**: `400` if either experiment id has no loadable artifact.

---

## Errors

All error responses: `{ "detail": "message" }`

| Status | When |
|--------|------|
| `400` | Round not finished, round already training, missing artifact for inspect/compare |
| `404` | Session or round not found |
| `409` | Status transition conflict; complete-while-training |
| `422` | Validation error; `method` != `full`; seed/base experiment id has no artifact |
| `500` | Internal training failure |