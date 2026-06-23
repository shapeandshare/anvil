---
title: 021 API E2E Suite - research
type: research
tags:
  - type/spec
spec-refs:
  - docs/vault/Specs/021 API E2E Suite/
related:
  - '[[021 API E2E Suite]]'
created: ~
updated: ~
---
# Research: Whole-API E2E Test Suite

**Phase**: 0 — Research & Pattern Discovery
**Date**: 2026-06-21
**Sources**: `tests/conftest.py`, `tests/e2e/*.py`, `pyproject.toml`, router source files in `anvil/api/v1/`, service enums and models

## 1. Test Infrastructure Patterns

### Conftest Fixture Contract (`tests/conftest.py`)

```python
@pytest.fixture
async def client():
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
```

**Decision**: New `tests/e2e/api/conftest.py` will access `app`, `AsyncClient`, `ASGITransport` the same way, and add factory fixtures on top.

**Decision**: `make test-e2e` runs `tests/e2e/` without coverage. New tests live under `tests/e2e/api/` and are auto-discovered via pytest's `testpaths = ["tests"]`.

### pytest Configuration
- `asyncio_mode = "auto"` — async def test functions are auto-detected
- `addopts = "-v --cov=anvil --cov-report=term-missing --ignore=tests/system"`
- Coverage gate: `fail_under = 23`

### Existing E2E Test Patterns
- All use `@pytest.mark.asyncio` (convention even with auto mode)
- `client` fixture is the only dependency
- Self-seed data inline (no shared state)
- MLflow may be degraded in e2e tests — do not assert `mlflow_run_id` non-null

---

## 2. Response Envelope Patterns

### Pattern A — `{"data": ..., "error": None}` (most routers)
Used by: datasets, corpora, experiments, training POST, governance, content, registry, inference

Example from `GET /datasets`:
```python
return {"data": {"datasets": [...]}, "error": None}
```

### Pattern B — Direct dict (health, services)
Used by: `GET /health`, `GET /services`, `GET /compute/backends`

```python
# health
{"status": "healthy", "version": ..., "uptime_seconds": ..., "system": {...}, "gpu": {...}}
# services
{"services": [{"name": "web", "status": "running"}, {"name": "mlflow", "status": ...}]}
```

### Error Responses
- FastAPI `HTTPException` → `{"detail": {"error": "...", ...}}` or plain `{"detail": "..."}`
- 404, 422, 409 status codes

### HTML Pages
- Return `HTMLResponse` (`text/html`) with 200
- Assert specific HTML landmark strings (page titles, headings)

---

## 3. Training Service Enums & State Machine

### ComputeStatus (authoritative enum)
```python
class ComputeStatus(StrEnum):
    SUBMITTED = "submitted"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
```
- Terminal states: `COMPLETED`, `FAILED`
- API `POST /training/start` response: `{"status": "running", "run_id": "..."}`

### SSE Stream Events (GET /training/stream/{run_id})
| Event | Payload | Terminal? |
|-------|---------|-----------|
| `submitted` | `{"backend": str, "device": str}` | No |
| `metrics` | `StepMetrics JSON` | No |
| `milestone` | `{"step": int}` | No |
| `complete` | `{"final_loss": float, "samples": [...], "device": str}` | Yes |
| `error` | `{"message": str}` | Yes |
| `divergence` | `{"step": int, "reason": "loss_nan"|"loss_inf"|"grad_explosion"}` | Yes |
| `export_error` | `{"error": str}` | No (post-complete) |
| `heartbeat` | `{}` | No |

### StepMetrics Model
```python
class StepMetrics(BaseModel):
    step: int; loss: float; device: str
    elapsed_sec: float; steps_per_sec: float | None
    eta_sec: float | None; grad_norm: float | None
    tokens_per_sec: float | None
```

---

## 4. Tiny Model Test Config

**Decision**: Use the established unit test config:
```python
{
    "n_layer": 1,
    "n_embd": 16,
    "n_head": 4,
    "block_size": 16,
    "num_steps": 5,         # E2E-viable minimum
    "learning_rate": 0.01,
    "beta1": 0.85,
    "beta2": 0.99,
    "temperature": 0.5,
    "compute_backend": "local-stdlib",
}
```
- Valid: `head_dim = 16 // 4 = 4` (even ✅, RoPE requirement)
- `n_head <= n_embd` ✅, `n_embd % n_head == 0` ✅

---

## 5. Demo Bootstrap Idempotency

**Endpoint**: `POST /demo/bootstrap`

**Behavior**:
| Call | Response code | corpora_created | corpora_skipped |
|------|--------------|-----------------|-----------------|
| First (fresh DB) | 200 | 4 | 0 |
| Second (data exists) | 200 | 0 | 4 |
| Concurrent | 409 | N/A (conflict) | N/A |

**Guard**: `asyncio.Lock` at module level — returns 409 if locked.

---

## 6. Compute Backends

`GET /compute/backends` returns:
```json
[
    {"value": "local-stdlib", "label": "...", "available": true, "reason": null},
    {"value": "local-torch", "label": "...", "available": false, "reason": "..."},
    {"value": "modal", "label": "...", "available": false, "reason": "..."}
]
```

`RegistryBackend` enum: `local-stdlib`, `local-torch`, `modal`

---

## 7. Forward-Pass Graph

`GET /forward-pass/graph` returns:
```json
{
    "model": {"id": ..., "version": ..., "name": "demo", "is_demo": true},
    "nodes": [{"id": str, "op": str, "label": str, "value": float, "depth": int}, ...],
    "edges": [{"from": str, "to": str}, ...]
}
```

---

## 8. Key Router-Specific Details

### Governance
- `GET /governance/licenses` → list of seeded OSI/CC licenses
- `GET /governance/audit` → audit events
- `GET /governance/audit/verify` → hash chain verification
- `POST /datasets/{id}/takedown` → marks dataset, creates audit event

### Content Repository
- Full lifecycle: create corpus → create source → open session → stage → validate → accept → freeze
- `IngestStatus`: OPEN, VALIDATING, ACCEPTED, FAILED
- SSE streams: `/content/stream/composition`, `/content/stream/injection`, `/content/stream/locks`, `/content/stream/import`

### Eval
- `POST /eval/perplexity` → finite numeric perplexity
- `POST /eval-datasets` + `POST /eval-datasets/{name}/records` + `GET /eval-datasets/{name}`

### Inference
- `POST /inference/tokenize|embeddings|attention|sampling-distribution|backward-graph|autograd-example|loss-breakdown`
- `POST /inference/sample` → non-empty generated text
- Uses demo model if no trained model loaded