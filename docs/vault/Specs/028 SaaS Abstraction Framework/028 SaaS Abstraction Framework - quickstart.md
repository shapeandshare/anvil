---
title: 028 SaaS Abstraction Framework - quickstart
type: quickstart
tags:
  - type/spec
spec-refs:
  - docs/vault/Specs/028 SaaS Abstraction Framework/
related:
  - '[[028 SaaS Abstraction Framework]]'
created: '2026-06-27'
updated: '2026-06-27'
---

# Quickstart: SaaS Abstraction Framework Development

## Prerequisites

- Python 3.11+
- `make` + `bash`
- Git

## Local Development (Unchanged)

```bash
make setup           # Create venv, install deps
make run             # Start web UI + MLflow locally
make test            # Run tests (includes contract tests)
```

The abstraction layer is transparent in local mode. All existing workflows work identically:

```bash
pip install anvil
anvil serve
# → http://localhost:8080
# No SaaS code loaded. SQLite, in-process MLflow, local filesystem, in-process compute.
```

## What This Feature Changes

After this feature lands, the internal architecture shifts from direct file I/O and in-process execution to a clean interface-based design:

| Before | After |
|--------|-------|
| `LocalFileStore` (ad-hoc) | `LocalFileStore` implements `FileStore` ABC |
| Direct `asyncio.Queue` usage | `InProcessEventBus` wraps `asyncio.Queue` |
| Ad-hoc job dispatch | `InProcessJobQueue` via `asyncio.create_task` |
| Direct compute invocation | `LocalStdlibBackend` / `LocalTorchBackend` implement `ComputeBackend` |
| `make run` starts web + MLflow | Same — no behavioral change |

## Key Files

| File | Purpose |
|------|---------|
| `anvil/storage/filestore.py` | `FileStore` ABC |
| `anvil/storage/event_bus.py` | `EventBus` ABC |
| `anvil/storage/job_queue.py` | `JobQueue` ABC + `TrainingJob` + `JobStatus` + `ResourceSpec` |
| `anvil/storage/compute_backend.py` | `ComputeBackend` ABC |
| `anvil/storage/local.py` | Refactored `LocalFileStore` |
| `anvil/storage/in_process_event_bus.py` | `InProcessEventBus` |
| `anvil/storage/in_process_job_queue.py` | `InProcessJobQueue` |
| `anvil/config.py` | `ANVIL_MODE` selector + guards |
| `tests/contract/test_storage_interfaces.py` | Contract tests for all 4 interfaces |

## Working with the Mode Selector

```bash
# Local mode (default)
make run                              # ANVIL_MODE unset → local wiring

# SaaS mode (requires cloud deps + config)
ANVIL_MODE=saas DATABASE_URL=... \
  uvicorn anvil._saas.app:app --reload

# Mode mismatch → fails fast with clear error
ANVIL_MODE=saas uvicorn anvil.api.app:app --reload
# → "FATAL: entrypoint 'anvil.api.app:app' does not match ANVIL_MODE=saas"

# Missing SaaS config → fails fast with list
ANVIL_MODE=saas uvicorn anvil._saas.app:app --reload
# → "FATAL: ANVIL_MODE=saas requires: DATABASE_URL, REDIS_URL, ..."
```

## Verifying Local-Mode Safety

```bash
# Import isolation check
python - <<'PY'
import importlib, sys
import anvil.api.app
for forbidden in ("boto3", "redis", "aws_jwt_verify", "opentelemetry", "prometheus_client"):
    assert forbidden not in sys.modules, f"{forbidden} loaded by local entrypoint"
print("import isolation OK")
PY
```

## Running Contract Tests

```bash
# Run all contract tests
python -m pytest tests/contract/ -v

# Run specific interface tests
python -m pytest tests/contract/test_storage_interfaces.py -v
```

## Architecture Cheatsheet

| Abstraction | Local Impl | SaaS Impl (future) |
|-------------|-----------|-------------------|
| `FileStore` | `LocalFileStore` (disk) | `S3FileStore` (boto3) |
| `EventBus` | `InProcessEventBus` (asyncio.Queue) | `RedisEventBus` (redis.asyncio) |
| `JobQueue` | `InProcessJobQueue` (create_task) | `BatchJobQueue` (boto3 batch) |
| `ComputeBackend` | `LocalStdlibBackend`, `LocalTorchBackend` | `BatchComputeBackend` |