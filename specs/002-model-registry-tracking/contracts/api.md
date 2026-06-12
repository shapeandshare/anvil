# API Contracts: Model Registry

**Date**: 2026-06-11 | **Feature**: [spec.md](../spec.md)

## Overview

REST API endpoints for the model registry feature. All endpoints are under the `/v1/registry/` prefix and return JSON responses. Follows existing FastAPI patterns in `microgpt/api/v1/`.

---

## Endpoints

### `POST /v1/registry/models`

Register a new model version from a completed experiment.

**Request Body**:
```json
{
  "experiment_id": 42,
  "name": "shakespeare-gpt",
  "description": "GPT trained on Shakespeare corpus (optional)"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `experiment_id` | integer | yes | ID of completed experiment |
| `name` | string | yes | Model name (max 255 chars) |
| `description` | string | no | Optional description (max 1000 chars) |

**Success Response (201)**:
```json
{
  "id": 1,
  "name": "shakespeare-gpt",
  "version": 1,
  "experiment_id": 42,
  "artifact_path": "data/models/registry/shakespeare-gpt/v1/model.json",
  "final_loss": 1.2345,
  "dataset_name": "shakespeare.txt",
  "created_at": "2026-06-11T14:30:00Z"
}
```

**Error Responses**:
| Status | Condition |
|--------|-----------|
| 400 | Experiment not found or not completed |
| 409 | Model name conflict (should not happen with versioning, but reserved) |
| 500 | Artifact copy failure |

---

### `GET /v1/registry/models`

List all registered models, sorted by most recently registered.

**Query Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `search` | string | no | Filter by model name (substring match) |

**Success Response (200)**:
```json
{
  "models": [
    {
      "id": 1,
      "name": "shakespeare-gpt",
      "description": "GPT trained on Shakespeare corpus",
      "latest_version": 3,
      "total_versions": 3,
      "latest_loss": 1.2345,
      "created_at": "2026-06-11T14:30:00Z"
    }
  ]
}
```

---

### `GET /v1/registry/models/{model_id}`

Get details of a specific registered model and its version history.

**Success Response (200)**:
```json
{
  "id": 1,
  "name": "shakespeare-gpt",
  "description": "GPT trained on Shakespeare corpus",
  "versions": [
    {
      "version": 1,
      "experiment_id": 42,
      "dataset_name": "shakespeare.txt",
      "final_loss": 2.3456,
      "hyperparameters": {
        "n_layer": 1,
        "n_embd": 16,
        "n_head": 4,
        "block_size": 128,
        "num_steps": 1000,
        "learning_rate": 0.01
      },
      "created_at": "2026-06-11T14:30:00Z"
    },
    {
      "version": 2,
      "experiment_id": 45,
      "dataset_name": "shakespeare.txt",
      "final_loss": 1.2345,
      "hyperparameters": { "...": "..." },
      "created_at": "2026-06-11T15:00:00Z"
    }
  ],
  "created_at": "2026-06-11T14:30:00Z"
}
```

---

### `DELETE /v1/registry/models/{model_id}`

Delete an entire registered model and all its versions.

**Error Responses**:
| Status | Condition |
|--------|-----------|
| 409 | Model is currently selected for inference (warning returned, user must confirm) |

**Success Response (200)**:
```json
{
  "message": "Model 'shakespeare-gpt' and all 3 versions deleted"
}
```

---

### `DELETE /v1/registry/models/{model_id}/versions/{version}`

Delete a specific version of a registered model.

**Success Response (200)**:
```json
{
  "message": "Version 2 of 'shakespeare-gpt' deleted"
}
```

---

### `GET /v1/registry/models/{model_id}/versions/{version}`

Get metadata for a specific version.

**Success Response (200)**:
```json
{
  "version": 2,
  "experiment_id": 45,
  "dataset_name": "shakespeare.txt",
  "final_loss": 1.2345,
  "hyperparameters": {
    "n_layer": 1,
    "n_embd": 16,
    "n_head": 4,
    "block_size": 128,
    "num_steps": 1000,
    "learning_rate": 0.01
  },
  "artifact_path": "data/models/registry/shakespeare-gpt/v2/model.json",
  "created_at": "2026-06-11T15:00:00Z"
}
```

---

### Modified Endpoint: `GET /v1/inference/models`

**Change**: Now pulls from registry instead of experiments table.

**Success Response (200)**:
```json
{
  "models": [
    {
      "id": 1,
      "name": "shakespeare-gpt",
      "version": 3,
      "experiment_id": 48,
      "final_loss": 1.2345,
      "created_at": "2026-06-11T15:00:00Z"
    }
  ]
}
```

If no models registered:
```json
{
  "models": [],
  "message": "No models registered. Train an experiment and register it first."
}
```

### Modified Endpoint: `POST /v1/inference/sample`

**Request Body**:
```json
{
  "model_id": 1,
  "version": 3,
  "temperature": 0.5,
  "max_new_tokens": 100
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `model_id` | integer | yes | Registered model ID |
| `version` | integer | yes | Specific version to use |
| `temperature` | float | no | Override default temperature |
| `max_new_tokens` | integer | no | Override default token count |