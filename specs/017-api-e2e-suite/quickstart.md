# Quickstart: Whole-API E2E Test Suite

**Phase**: 1 — Design & Contracts
**Date**: 2026-06-21

## Running Tests

```bash
# Run full test suite (unit + e2e + integration)
make test

# Run only e2e tests (no coverage overhead)
make test-e2e

# Run a single e2e module
python -m pytest tests/e2e/api/test_datasets.py -v

# Run the lifecycle integration test
python -m pytest tests/e2e/api/test_lifecycle_journey.py -v -s
```

## Adding Coverage for a New Endpoint

1. Identify which router the endpoint belongs to (see [interfaces.md](./contracts/interfaces.md))
2. Open the corresponding test module in `tests/e2e/api/`
3. Add a test function following the established patterns:

```python
@pytest.mark.asyncio
async def test_my_new_endpoint(client):
    """Test FR-XXX: description of what's being verified."""
    # Arrange — self-seed if needed
    # Act
    r = await client.get("/v1/my-router/my-endpoint")
    # Assert
    assert r.status_code == 200
    data = r.json()
    # Most routers use {"data": ..., "error": None}
    # Health ops / compute use direct response
    assert "expected_field" in data.get("data", data)
```

## Patterns to Follow

### Happy Path
```python
# For envelope routers (datasets, corpora, experiments, training, etc.)
r = await client.get("/v1/datasets")
assert r.status_code == 200
data = r.json()["data"]
assert "datasets" in data

# For direct-response routers (health, services, compute)
r = await client.get("/v1/health")
assert r.status_code == 200
assert r.json()["status"] == "healthy"
```

### Error Path
```python
r = await client.get("/v1/datasets/99999")
assert r.status_code == 404
detail = r.json()["detail"]
# detail is either {"error": str, ...} dict or plain string
assert isinstance(detail, (str, dict))
```

### Using Factory Fixtures
```python
async def test_training_lifecycle(client, tmp_path):
    corpus = await make_corpus(client, tmp_path)
    dataset = await make_dataset(client, corpus["id"])
    run = await make_trained_run(client, dataset["id"])
    assert run["status"] == "completed"
```

### Reading SSE
```python
events = await read_sse_events(
    client,
    f"/v1/training/stream/{run_id}",
    max_events=5,
    timeout_s=30,
)
assert any(evt[0] == "metrics" for evt in events)
```

## Key Assertions to Avoid

| ❌ Wrong | ✅ Right |
|----------|---------|
| `assert loss == 2.5` | `assert loss > 0 and math.isfinite(loss)` |
| `assert generated == "hello"` | `assert len(generated) > 0` |
| `assert models == 3` | `assert len(models) >= 1` |
| `assert mlflow_run_id is not None` | Skip MLflow assertions in e2e (may be degraded) |

## File Layout

```
tests/e2e/api/
├── conftest.py                  # Shared factories + helpers
├── test_health_ops.py          # 8 endpoints
├── test_datasets.py            # ~20 endpoints
├── test_corpora.py             # ~9 endpoints
├── test_training.py            # 6 endpoints + SSE
├── test_experiments.py         # ~9 endpoints
├── test_registry.py            # 6 endpoints
├── test_inference.py           # ~10 endpoints + sample
├── test_eval.py                # 3 endpoints
├── test_compute.py             # 1 endpoint
├── test_governance.py          # 5 endpoints
├── test_content.py             # ~21 endpoints + SSE
├── test_pages.py               # ~12 HTML routes
└── test_lifecycle_journey.py   # 1 integration test
```

## Vault Enrichment

After completing implementation, follow AGENTS.md:
1. Write session log to `docs/vault/Sessions/`
2. Create discovery notes for any real integration bugs found
3. Use controlled-vocabulary tags from `docs/vault/_meta/tags.md`
4. Run `make vault-audit` — 0 errors required before committing vault changes