# Testing Guide — anvil

**Last updated**: 2026-06-14

## Quick Start

```bash
make test       # Run all tests
make test-e2e   # Run end-to-end tests only
make lint       # Run ruff → black --check → isort --check → pylint
make typecheck  # Run mypy/pyright
make format     # Auto-format with black + isort
```

---

## Test Suites

### 1. Unit Tests — `tests/unit/`

Tests for individual components in isolation. Currently covers:

| Test file | What it tests | How to run |
|-----------|---------------|------------|
| `tests/unit/core/test_engine.py` | Autograd (Value backward + operations), Tokenizer (encode/decode roundtrip), LlamaModel param count, training loop (loss decreases) | `pytest tests/unit/ -v` |

**To add new unit tests:**
1. Create `tests/unit/<module>/test_<name>.py`
2. Write test functions prefixed with `test_`
3. Import the module under test directly (no server needed)

### 2. End-to-End Tests — `tests/e2e/`

Tests that exercise the full stack through HTTP endpoints.

| Test file | What it tests | How to run |
|-----------|---------------|------------|
| `tests/e2e/test_setup.py` | Package imports resolve (`import anvil`, `import anvil.core.engine`) | `pytest tests/e2e/test_setup.py -v` |
| `tests/e2e/test_endpoints.py` | HTTP API endpoints (`/v1/health`, `/v1/datasets`, `/v1/experiments`) return 200 with correct JSON | `pytest tests/e2e/test_endpoints.py -v` |

**How e2e tests work:**
- Fixture in `tests/conftest.py` creates all tables before the test run and drops them after (isolated per session)
- Uses `httpx.AsyncClient` with `ASGITransport` to hit FastAPI routes in-process (no server process needed)
- Database is SQLite-in-memory (clean state every test run)

### 3. Manual Integration Tests

These aren't automated but verify the system end-to-end:

```
# Start the server
make run
# → Opens http://0.0.0.0:8080 in browser

# Test training via CLI
make train
# → Downloads names dataset, trains for 1000 steps, prints 20 samples

# Test the API directly
curl http://localhost:8080/v1/health
# → {"status":"healthy","version":"0.1.0"}

curl http://localhost:8080/v1/datasets
# → {"datasets":[]}  (empty DB on first run)

curl http://localhost:8080/v1/experiments
# → {"experiments":[]}
```

---

## Testing the Core Engine

The LlamaModel training engine at `anvil/core/` is the heart of the project. Here's how to test it manually:

### Autograd (Value class)

```python
from anvil.core.autograd import Value

a = Value(2.0)
b = Value(3.0)
c = a * b
L = c + a
L.backward()

print(a.grad)  # Should be 4.0 (dL/da = b + 1 = 3 + 1)
print(b.grad)  # Should be 2.0 (dL/db = a = 2)
```

### LlamaModel forward pass

```python
from anvil.core.engine import LlamaModel
model = LlamaModel(vocab_size=27, n_embd=16, n_head=4, n_layer=1, block_size=16)
print(f"Parameters: {model.num_params()}")  # Should be 4192
```

### Full training

```python
from anvil.core.engine import train
docs = ["emma", "olivia", "ava", "isabella", "sophia"]
# Train for just 5 steps to verify it runs
model, loss, samples = train(docs, num_steps=5, n_embd=8, n_head=2)
print(f"Final loss: {loss:.4f}")
print(f"Samples: {samples}")
```

### Progressive walkthrough

```bash
python examples/train0.py   # Bigram count table
python examples/train1.py   # MLP stub
python examples/train2.py   # Autograd verification
python examples/train3.py   # Attention stub
python examples/train4.py   # Multi-head stub (delegates to anvil core)
python examples/train5.py   # Full Llama training (delegates to anvil core)
```

---

## Testing the API

Start the server:

```bash
make setup   # One-time (creates venv, installs deps, runs migrations)
make run     # Starts server at http://0.0.0.0:8080
```

### Endpoints

| Method | Endpoint | Expected result |
|--------|----------|-----------------|
| GET | `/v1/health` | `{"status":"healthy","version":"0.1.0"}` |
| GET | `/v1/datasets` | `{"datasets":[]}` or list of datasets |
| GET | `/v1/experiments` | `{"experiments":[]}` or list of experiments |
| POST | `/v1/training/start` | Starts a training run, returns `{"run_id": N, "status": "started"}` |
| GET | `/v1/training/stream/{run_id}` | SSE stream of training metrics |
| POST | `/v1/training/{run_id}/stop` | Stops a training run |
| GET | `/v1/` | Training dashboard HTML page |
| GET | `/v1/experiments-page` | Experiment history HTML page |
| GET | `/v1/datasets-page` | Dataset management HTML page |
| GET | `/v1/operations-page` | Operations dashboard HTML page |
| GET | `/v1/inference-page` | Inference HTML page |

### Testing SSE streaming

```bash
# Terminal 1: Start the server
make run

# Terminal 2: Start training and watch SSE events
curl -N http://localhost:8080/v1/training/start \
  -H "Content-Type: application/json" \
  -d '{"num_steps": 100, "n_embd": 8, "n_head": 2}'
# → {"run_id":0,"status":"started"}

# Then open the SSE stream in a browser or curl (use the run_id from above):
curl -N http://localhost:8080/v1/training/stream/0
# → event: metrics
# → data: {"step": 1, "loss": 3.366}
# → ...
# → event: complete
# → data: {"final_loss": 2.37, "samples": ["kamon", "ann", ...]}
```

---

## Testing the Database

```python
import asyncio
from anvil.db.session import async_engine, AsyncSessionLocal
from anvil.db.base import Base
from anvil.db import models  # Register models
from anvil.db.repositories import DatasetRepository, ExperimentRepository, TrainingConfigRepository

async def test_db():
    # Create tables
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Test CRUD
    async with AsyncSessionLocal() as session:
        ds_repo = DatasetRepository(session)
        ds = Dataset(name="test", filename="test.txt", file_path="/tmp/test.txt")
        await ds_repo.add(ds)
        await session.commit()
        
        all_ds = await ds_repo.get_all()
        print(f"Datasets: {len(all_ds)}")  # → 1

asyncio.run(test_db())
```

---

## Testing the CLI

```bash
# These entry points are defined in pyproject.toml [project.scripts]
# They can't run without pip install -e ., but the Makefile handles this:

make train    # Runs full training (1000 steps, outputs 20 samples)
make stop     # Stops background services
```

---

## Test Coverage

Run with coverage to see gaps:

```bash
make test   # Runs pytest with --cov=anvil --cov-report=term-missing
```

Current coverage: ~41% (improvement needed — tests are minimal; the TDD mandate targets 100%)

---

## Writing New Tests

### Pattern for unit tests

```python
"""Unit tests for <module name>."""

from anvil.<module> import <Class>


def test_<behavior>():
    result = <Class>.<method>()
    assert result == <expected>
```

### Pattern for e2e HTTP tests

```python
"""e2e tests for <endpoint>."""

import pytest


@pytest.mark.asyncio
async def test_<endpoint>(client):
    r = await client.get("/v1/<endpoint>")
    assert r.status_code == 200
    assert "<key>" in r.json()
```

The `client` fixture is defined in `tests/conftest.py` and provides an `httpx.AsyncClient` connected to the FastAPI app with a clean database per test session.

---

## Quality Gates (CI Pipeline)

```bash
make lint      # ruff → black --check → isort --check → pylint
make typecheck # mypy anvil/
make test      # pytest + coverage
make format    # auto-fix formatting
```

All must pass before merging. The current state:

| Gate | Status |
|------|--------|
| ruff | ✅ All checks passed |
| black | ✅ 38 files left unchanged |
| isort | ✅ All imports sorted |
| pylint | ✅ 0 errors (1 known false positive: `func.now` in SQLAlchemy) |
| mypy | ✅ Run via `make typecheck` |
| pytest | ✅ 10/10 tests pass |
| Alembic | ✅ migrations up/down verified |