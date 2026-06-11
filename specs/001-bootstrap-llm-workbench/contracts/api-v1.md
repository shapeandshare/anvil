# API Contracts: Bootstrap LLM Workbench

**Version**: v1 | **Base URL**: `http://<host>:8080/v1/`
**Documentation**: Auto-generated Swagger at `/v1/docs` (when server is running)

---

## Standard Conventions

### Request Headers
- `Content-Type: application/json` (for JSON endpoints)
- `Accept: text/event-stream` (for SSE streaming endpoints)

### Response Envelope
```json
{
  "data": { ... },
  "error": null
}
```
Errors use the same envelope with `data: null`:
```json
{
  "data": null,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Human-readable description",
    "details": {}
  }
}
```

### Error Codes
| Code | HTTP Status | Meaning |
|------|-------------|---------|
| VALIDATION_ERROR | 422 | Request body validation failed |
| NOT_FOUND | 404 | Resource not found |
| CONFLICT | 409 | Resource already exists |
| SERVICE_UNAVAILABLE | 503 | A required service is not running |
| INTERNAL_ERROR | 500 | Unexpected error |

### Pagination
List endpoints support cursor-based pagination:
```json
{
  "data": [...],
  "next_cursor": "eyJpZCI6...",
  "has_more": true
}
```
Query params: `?cursor=<cursor>&limit=20` (default limit: 20, max: 100)

---

## Endpoints

### Datasets

| Method | Path | Description |
|--------|------|-------------|
| POST | `/v1/datasets` | Upload a new dataset (multipart/form-data) |
| GET | `/v1/datasets` | List all datasets |
| GET | `/v1/datasets/{id}` | Get dataset details |
| DELETE | `/v1/datasets/{id}` | Delete a dataset and its file |
| PUT | `/v1/datasets/{id}` | Update dataset metadata (name, description) |

**POST /v1/datasets**
```
Content-Type: multipart/form-data
Body:
  file: (binary .txt or .csv file)
  name: (optional string, defaults to filename)
  description: (optional string)
```

**Response 201**
```json
{
  "data": {
    "id": 1,
    "name": "names",
    "description": "Default names dataset",
    "filename": "input.txt",
    "vocabulary_size": 27,
    "document_count": 32033,
    "created_at": "2026-06-10T12:00:00Z",
    "updated_at": "2026-06-10T12:00:00Z"
  }
}
```

---

### Training

| Method | Path | Description |
|--------|------|-------------|
| POST | `/v1/training/start` | Start a new training run |
| POST | `/v1/training/{id}/stop` | Stop a running training run |
| GET | `/v1/training/stream/{id}` | SSE stream of training metrics |
| GET | `/v1/training/configs` | List saved training configs |
| POST | `/v1/training/configs` | Save a training config |
| GET | `/v1/training/configs/{id}` | Get a training config |
| PUT | `/v1/training/configs/{id}` | Update a training config |
| DELETE | `/v1/training/configs/{id}` | Delete a training config |

**POST /v1/training/start**
```json
{
  "n_layer": 1,
  "n_embd": 16,
  "n_head": 4,
  "block_size": 16,
  "num_steps": 1000,
  "learning_rate": 0.01,
  "beta1": 0.85,
  "beta2": 0.99,
  "temperature": 0.5,
  "use_gpu": false,
  "dataset_id": 1
}
```

**Response 202** (accepted)
```json
{
  "data": {
    "id": 42,
    "status": "running",
    "config": { ... },
    "started_at": "2026-06-10T12:00:00Z"
  }
}
```

**GET /v1/training/stream/{id}** — SSE Stream
```
Content-Type: text/event-stream

event: metrics
data: {"step": 1, "loss": 3.366, "elapsed_seconds": 0.8}

event: metrics
data: {"step": 2, "loss": 3.424, "elapsed_seconds": 1.6}

event: metrics
data: {"step": 3, "loss": 3.178, "elapsed_seconds": 2.4}

event: complete
data: {"final_loss": 2.37, "samples": ["kamon", "ann", "karai", ...]}

event: error
data: {"message": "CUDA unavailable, falling back to CPU"}
```

---

### Experiments

| Method | Path | Description |
|--------|------|-------------|
| GET | `/v1/experiments` | List all experiments |
| GET | `/v1/experiments/{id}` | Get experiment details with samples |
| DELETE | `/v1/experiments/{id}` | Delete an experiment |
| GET | `/v1/experiments/compare` | Compare two experiments |

**GET /v1/experiments/compare?id=1&id=2**
```json
{
  "data": {
    "experiments": [
      {
        "id": 1,
        "config": { "learning_rate": 0.01, "n_embd": 16 },
        "final_loss": 2.37,
        "loss_curve": [3.366, 3.424, 3.178, ...],
        "samples": ["kamon", "ann", ...]
      },
      {
        "id": 2,
        "config": { "learning_rate": 0.001, "n_embd": 16 },
        "final_loss": 2.89,
        "loss_curve": [3.401, 3.521, 3.412, ...],
        "samples": ["zorp", "bleen", ...]
      }
    ]
  }
}
```

---

### Operations & System

| Method | Path | Description |
|--------|------|-------------|
| GET | `/v1/health` | System health check |
| GET | `/v1/operations/services` | List all managed services |
| POST | `/v1/operations/services/{name}/start` | Start a service |
| POST | `/v1/operations/services/{name}/stop` | Stop a service |
| POST | `/v1/operations/services/{name}/restart` | Restart a service |
| GET | `/v1/operations/services/{name}/logs` | Get logs for a service |
| GET | `/v1/operations/services/{name}/logs/stream` | SSE stream of log lines |

**GET /v1/health**
```json
{
  "status": "healthy",
  "services": {
    "web": "running",
    "mlflow": "running"
  },
  "uptime_seconds": 3600,
  "database": "connected",
  "version": "0.1.0"
}
```

**GET /v1/operations/services**
```json
{
  "data": [
    {
      "name": "web",
      "status": "running",
      "pid": 12345,
      "uptime_seconds": 3600,
      "memory_mb": 45.2
    },
    {
      "name": "mlflow",
      "status": "running",
      "pid": 12346,
      "uptime_seconds": 3595,
      "memory_mb": 120.0
    }
  ]
}
```

**GET /v1/operations/services/mlflow/logs?tail=50**
```json
{
  "data": {
    "service": "mlflow",
    "lines": [
      {"timestamp": "2026-06-10T12:00:00Z", "level": "INFO", "message": "Starting MLflow server..."},
      {"timestamp": "2026-06-10T12:00:01Z", "level": "INFO", "message": "Listening on 127.0.0.1:5000"}
    ]
  }
}
```

---

## CLI Entry Points

Defined in `pyproject.toml` under `[project.scripts]`:

| Command | Entry Point | Description |
|---------|------------|-------------|
| `microgpt-workbench` | `microgpt.cli:serve` | Start web server |
| `microgpt-train` | `microgpt.cli:train` | Run training from CLI |
| `microgpt-stop` | `microgpt.cli:stop` | Stop all services |