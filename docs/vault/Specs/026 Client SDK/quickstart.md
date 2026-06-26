---
title: 'Quickstart: anvil Client SDK'
type: spec
tags:
  - type/spec
  - domain/architecture
status: draft
created: '2026-06-21'
updated: '2026-06-21'
---

Back to [[Specs/026 Client SDK/Spec]].

## 2. Authenticate

```python
# Option A — API key (added as X-API-Key on every request)
async with AnvilClient(api_key="sk-...") as client:
    datasets = await client.datasets.list()

# Option B — session login (captures anvil_session cookie; CSRF handled automatically)
async with AnvilClient() as client:
    await client.login(api_key="sk-...")
    datasets = await client.datasets.list()
    await client.logout()
```

---

## 3. Manage datasets (US-2)

```python
async with AnvilClient(api_key="sk-...") as client:
    ds = await client.datasets.create(name="shakespeare", description="tiny corpus")
    await client.datasets.upload(ds.id, Path("data/shakespeare.txt"))

    all_ds = await client.datasets.list()
    found = await client.datasets.search("shakespeare")

    await client.datasets.update(ds.id, description="updated")
    await client.datasets.delete(ds.id)
```

---

## 4. Train a model & stream progress (US-3)

```python
from anvil.client.training import TrainingConfig
from anvil.client._shared import StreamEventType

async with AnvilClient(api_key="sk-...") as client:
    result = await client.training.start(
        TrainingConfig(n_embd=32, n_layer=2, num_steps=500, dataset_id=ds.id)
    )
    print("run:", result.run_id, "experiment:", result.experiment_id)

    async for event in client.training.stream(result.run_id):
        if event.type is StreamEventType.METRICS:
            print(f"step {event.data['step']}: loss={event.data['loss']:.4f}")
        elif event.type is StreamEventType.COMPLETE:
            print("done")
            break
        elif event.type is StreamEventType.ERROR:
            print("failed:", event.data)
            break

    # or poll instead of stream:
    status = await client.training.status(result.run_id)
```

---

## 5. Experiments, registry, inference (US-4, US-6)

```python
async with AnvilClient(api_key="sk-...") as client:
    experiments = await client.experiments.list()
    comparison = await client.experiments.compare([e.id for e in experiments[:2]])

    model = await client.registry.register(experiment_id=experiments[0].id)
    models = await client.registry.list()

    text = await client.inference.sample(model_id=model.model_id,
                                          prompt="To be", temperature=0.7)

    # download an exported artifact to disk
    await client.experiments.download_artifact(
        experiments[0].id, run_id="...", path="model.safetensors",
        dest=Path("out/model.safetensors"),
    )
```

---

## 6. Error handling (US-1, US-5, SC-004)

```python
from anvil.client._shared.errors import (
    AuthenticationError, NotFoundError, RateLimitError,
    ServerError, ConnectionError,
)

async with AnvilClient(api_key="bad-key") as client:
    try:
        await client.datasets.get(999999)
    except AuthenticationError:
        ...   # 401/403
    except NotFoundError:
        ...   # 404
    except RateLimitError as e:
        ...   # 429 — e.retry_after
    except ServerError as e:
        ...   # 5xx — e.message preserves the server's error text
    except ConnectionError:
        ...   # server unreachable (bounded by timeout, never hangs)
```

---

## 7. Verifying the SDK (developer / CI)

Tests run against the in-process FastAPI app via `httpx.ASGITransport` (no live server, no network):

```bash
make test          # full suite incl. tests/unit/client/ and tests/e2e/api/test_client_*.py
make typecheck     # mypy --strict — SDK must be clean
make lint          # ruff + black + isort + pylint
```

**Smoke check** (after implementation, against a running server):

```bash
make run                                   # start anvil on :8080
python -c "import asyncio; from anvil.client import AnvilClient; \
asyncio.run((lambda: __import__('anvil.client').client.AnvilClient().health.get())())"
```

> All examples are the target public API defined in `contracts/`. They are the acceptance
> surface for the user stories and serve as living documentation once the SDK is implemented.
