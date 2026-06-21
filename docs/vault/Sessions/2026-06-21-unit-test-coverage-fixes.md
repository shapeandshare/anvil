---
created: '2026-06-21'
tags:
  - test
  - coverage
  - ddd-restructure
  - pytest-asyncio
title: Unit test coverage fixes — pytest-asyncio 1.4 + DDD path repair
type: session
updated: '2026-06-21'
---
# Unit Test Coverage Fixes

**Date:** 2026-06-21

## Summary

Increased unit test coverage from 25% → **37.55%** by fixing 39 test failures and 107 fixture-level errors. All tests now pass (473/473) with zero errors.

## What Changed

### Infrastructure

- **pytest-asyncio**: Updated from `>=0.24,<1` to `>=0.24,<2` (now using 1.4.0) — fixes Python 3.14 deprecation of `asyncio.get_event_loop_policy`  
- **`tests/unit/conftest.py`**: `in_memory_session` fixture uses `@pytest_asyncio.fixture(loop_scope="function")` instead of `@pytest.fixture`
- **`shared/testing.mk`**: `make test` runs in 2 batches with combined coverage to avoid event loop overload when collecting 60+ modules
- **`tests/conftest.py`**: Removed the `session` fixture (unused by unit tests, only added collection overhead)

### Test Fixes (39 failures → 0)

| File | Failures | Root Cause |
|------|----------|------------|
| `test_local_backend.py` | 3 | Callbacks didn't accept `**kwargs`; `train()` passes `tokens=n, grad_norm=None` |
| `test_mlflow_inputs.py` | 7 | DDD restructure (#012): flat `mlflow_inputs.py` → `tracking/mlflow_inputs.py` |
| `test_metrics_collectors.py` | 13 | DDD restructure: `mps_metrics_collector` → `tracking/mps_metrics_collector` |
| `test_tracking_service.py` | 4 | DDD restructure: `MlflowInputResolver` path update |
| `test_training_phases.py` | 8 | DDD restructure: `resolve_backend`/`get_backend` → `compute/resolve.py`, `compute/registry.py` |
| `test_system_metrics.py` | 2 | `_system_metrics_enabled` fixture imported `tracking` package (`__init__.py`) instead of `tracking.tracking` module |
| `test_engine_load.py` | 2 | Didn't handle vector params (`rms_*` flat lists) in state_dict iteration |

### Key Discoveries

1. **Python 3.14 + pytest-asyncio 0.26 event loop issue**: `@pytest.fixture async def ... yield` (async generator fixtures) cause event loop corruption when 50+ test modules are collected together. Fix: use `@pytest_asyncio.fixture(loop_scope="function")` + batch the test run by explicit file paths.
2. **DDD restructure test gaps**: The #012 restructure moved modules into domain sub-packages but didn't update test `patch()` paths. 34 of 39 failures were stale DDD paths.
3. **Mock.patch with `from X import Y`**: When a module does `from ..compute.resolve import resolve_backend`, the name is bound as a local reference. `patch("compute.resolve.resolve_backend")` replaces the source but the local reference in the importing module is unchanged. Must patch at the consuming module's namespace: `patch("training.training.resolve_backend")`.
4. **`make test` batching**: Running `tests/unit/` as a directory triggers conftest collection for all 60+ modules, causing event loop overload. Running explicit file paths in 2 batches eliminates the issue.

## Related Artifacts

- [[404 - pytest-asyncio Python 3.14 compatibility]] (discovery to create)
- [[012-ddd-services-restructure]] (reference)
