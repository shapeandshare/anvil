# Test Interface Contracts: Whole-API E2E Test Suite

**Phase**: 1 — Design & Contracts
**Date**: 2026-06-21
**Spec**: [spec.md](../spec.md)

## 1. Factory Fixture Contracts

### `make_corpus(client, tmp_path) → dict`

Creates and ingests a tiny corpus.

| Parameter | Type | Description |
|-----------|------|-------------|
| `client` | `httpx.AsyncClient` | Test client fixture |
| `tmp_path` | `pathlib.Path` | Pytest tmp_path for temporary files |

**Returns** (corpus record dict):
```json
{"id": 1, "name": "e2e-test-corpus", ...}
```

**Side effects**: One corpus created in DB. One file ingested on filesystem.

**Contract**:
```python
r = await client.post("/v1/corpora", json={"name": "e2e-test-corpus"})
assert r.status_code == 200
data = r.json()
assert "id" in data.get("data", data)
```

### `make_dataset(client) → dict`

Creates a ready-to-use dataset.

**Parameters**: `client` only (no upload needed — uses tiny seed text).

**Returns** (dataset record dict):
```json
{"id": 1, "name": "e2e-test-dataset", ...}
```

**Contract**:
```python
r = await client.post("/v1/datasets", json={"name": "e2e-test-dataset"})
assert r.status_code == 200
```

### `make_trained_run(client) → dict`

Full tiny training run to terminal success.

**Parameters**: `client` only (self-seeds corpus + dataset internally).

**Returns**:
```json
{
    "run_id": "uuid-string",
    "experiment_id": 1,
    "status": "completed",
    "final_loss": 2.34
}
```

**Contract** — training start:
```python
r = await client.post("/v1/training/start", json={**TINY_CONFIG, "dataset_id": ds_id})
assert r.status_code == 200
run_id = r.json()["data"]["run_id"]
```

**Contract** — poll to terminal:
```python
import asyncio
for _ in range(60):
    r = await client.get(f"/v1/training/{run_id}/status")
    status = r.json()["data"]["status"]
    if status in ("completed", "failed"):
        break
    await asyncio.sleep(1)
assert status == "completed"
```

### `make_registered_model(client) → dict`

Trains + registers a model.

**Returns**:
```json
{"model_id": 1, "version": 1}
```

**Contract**:
```python
r = await client.post("/v1/registry/models", json={"run_id": trained_run["run_id"]})
assert r.status_code == 201
model_id = r.json()["data"]["model"]["id"]
```

### `make_eval_dataset(client) → dict`

Creates eval dataset with records.

**Returns**:
```json
{"name": "e2e-test-eval"}
```

**Contract**:
```python
r = await client.post("/v1/eval-datasets", json={"name": "e2e-test-eval"})
assert r.status_code == 200
```

---

## 2. Helper Function Contracts

### `poll_until_terminal(client, run_id, timeout_s=60) → str`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `client` | `httpx.AsyncClient` | — | Test client |
| `run_id` | `str` | — | Training run UUID |
| `timeout_s` | `int` | `60` | Max wait seconds |

**Returns**: Terminal status string (`"completed"` or `"failed"`).

**Raises**: `asyncio.TimeoutError` if not terminal within timeout.

**Polling endpoint**: `GET /v1/training/{run_id}/status`
**Response shape**: `{"data": {"status": "completed"|"failed"|"running"|"submitted", ...}, "error": None}`

### `read_sse_events(client, url, max_events=5, timeout_s=30) → list[tuple[str, dict]]`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `client` | `httpx.AsyncClient` | — | Test client |
| `url` | `str` | — | SSE endpoint path (e.g., `/v1/training/stream/{run_id}`) |
| `max_events` | `int` | `5` | Stop after this many events |
| `timeout_s` | `int` | `30` | Max wait seconds |

**Returns**: `[(event_name, payload_dict), ...]`

**Raises**: `asyncio.TimeoutError` if `max_events` not received within timeout.

**SSE wire format**:
```
event: metrics
data: {"step": 1, "loss": 2.34, "device": "cpu", ...}

event: milestone
data: {"step": 1}

event: complete
data: {"final_loss": 2.34, "samples": [...], "device": "cpu"}
```

**Implementation pattern**:
```python
async with client.stream("GET", url) as response:
    events = []
    async for line in response.aiter_lines():
        if line.startswith("event: "):
            current_event = line[7:]
        elif line.startswith("data: "):
            events.append((current_event, json.loads(line[6:])))
            if len(events) >= max_events:
                break
```

---

## 3. Response Shape Contracts (per router)

### Health Ops
| Endpoint | Status | Response shape |
|----------|--------|----------------|
| `GET /health` | 200 | `{"status": "healthy", "version": str, "uptime_seconds": int, "system": {...}, "gpu": {...}}` |
| `GET /services` | 200 | `{"services": [{"name": "web", "status": "running"}, {"name": "mlflow", ...}]}` |
| `POST /demo/bootstrap` | 200 | `{"corpora_created": int, "datasets_created": int, "corpora_skipped": int, "datasets_skipped": int, "errors": [...], "total_time_ms": float}` (direct, no envelope) |
| `POST /demo/bootstrap` (concurrent) | 409 | `{"detail": {"status": "busy", "message": "Bootstrap already in progress"}}` (FastAPI exception) |

### Datasets (envelope: `{"data": ..., "error": None}`)
| Endpoint | Status | Key response field |
|----------|--------|-------------------|
| `GET /datasets` | 200 | `data.datasets` (list) |
| `GET /datasets/{id}` | 200 | `data.id`, `data.name` |
| `POST /datasets` | 200 | `data.id`, `data.name` |
| `DELETE /datasets/{id}` | 200 | `data.message` |
| `GET /datasets/{id}` (unknown) | 404 | FastAPI `HTTPException` |

### Training
| Endpoint | Status | Key response field |
|----------|--------|-------------------|
| `POST /training/start` | 200 | `data.run_id`, `data.status` |
| `GET /training/{run_id}/status` | 200 | `data.status` |
| `GET /training/stream/{run_id}` | 200 | SSE stream (see §2 above) |
| `POST /training/{run_id}/stop` | 200 | `data.message` |
| `GET /forward-pass/graph` | 200 | `data.model`, `data.nodes`, `data.edges` |

### Experiments (envelope: `{"data": ..., "error": None}`)
| Endpoint | Status | Key response field |
|----------|--------|-------------------|
| `GET /experiments` | 200 | `data.experiments` (list) |
| `GET /experiments/{id}` | 200 | `data.id`, `data.name` |
| `GET /experiments/compare` | 200 | `data` (list of experiments) |
| `DELETE /experiments/{id}` | 200 | `data.message` |

### Compute
| Endpoint | Status | Response shape |
|----------|--------|----------------|
| `GET /compute/backends` | 200 | `[{"value": str, "label": str, "available": bool, "reason": str|None}, ...]` (direct list, no envelope) |

### Governance
| Endpoint | Status | Key response field |
|----------|--------|-------------------|
| `GET /governance/licenses` | 200 | List of license entries |
| `GET /governance/audit` | 200 | Audit events list |
| `GET /governance/audit/verify` | 200 | Verification result |
| `POST /datasets/{id}/takedown` | 200 | Status message |

### HTML Pages (learning.py, pages.py, router.py)
| Endpoint | Status | Assertion |
|----------|--------|-----------|
| `GET /` | 200 | `"anvil"` in HTML or expected landmark |
| `GET /v1/*-page` | 200 | Expected heading/title string |

---

## 4. Error Response Shape Contract

All FastAPI HTTP exceptions return:
```json
{"detail": <string or dict>}
```

| Status | Common detail shape | Example |
|--------|--------------------|---------|
| 404 Not Found | `{"detail": {"error": "Dataset not found", "id": 999}}` | Unknown resource lookup |
| 422 Validation | `{"detail": [{"loc": [...], "msg": "...", "type": "..."}]}` | Missing/invalid request body |
| 409 Conflict | `{"detail": {"status": "busy", "message": "..."}}` | Concurrent bootstrap |

**Contract for error path tests**:
```python
r = await client.get("/v1/datasets/99999")
assert r.status_code == 404
# May be either {"detail": str} or {"detail": {"error": str}}
detail = r.json()["detail"]
assert isinstance(detail, str) or "error" in detail
```