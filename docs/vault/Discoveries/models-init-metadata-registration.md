---
title: Models __init__ Metadata Registration
type: discovery
tags:
  - type/discovery
  - domain/database
status: reviewed
created: '2026-06-23'
updated: '2026-06-23'
aliases:
  - models-init-metadata-registration
source: agent
code-refs:
  - anvil/db/models/
---
# Models `__init__` Metadata Registration

**Type**: discovery
**Tags**: #discovery #testing #database #sqlalchemy
**Status**: reviewed
**Created**: 2026-06-21

## Summary

The `anvil/db/models/__init__.py` package was bare (docstring-only), causing all ORM models except `Dataset` and `CurationOperation` to be invisible to SQLAlchemy's `Base.metadata`. This caused `NoReferencedTableError` in every test using the `client` fixture when models with foreign-key references (e.g., `Sample.import_source_id → import_sources.id`) were created.

## Root Cause

Per the project's `__init__.py` Ownership Policy (Constitution Article VI), all domain sub-packages should have a bare, docstring-only `__init__.py` with no re-exports. However, SQLAlchemy ORM models must be imported somewhere to register their tables with `Base.metadata`. Previously only `Dataset` and `CurationOperation` were imported (by the datasets API router), leaving the other 17 model modules unregistered.

## Fix

Added `from . import <module>` side-effect imports for all 19 model modules in `models/__init__.py`. These imports trigger the ORM class registation without re-exporting symbols, which is consistent with Article VI's intent (no re-exports) while ensuring metadata completeness.

## Similar Issue: Unhandled IntegrityError Propagation

During testing, SQLAlchemy `IntegrityError` exceptions (e.g., from UNIQUE constraint violations) propagate as Python exceptions through FastAPI's ASGITransport rather than being caught and returned as HTTP 500 responses. Tests that expect an error response must wrap the call in a `try/except` to catch the propagated exception.

## Affected Files

- `anvil/db/models/__init__.py` — was bare, now imports all model modules
- All `tests/e2e/api/test_*.py` files using `client` fixture

## Related: InferenceService Demo Model Resolution

A second discovery during the same session involved the inference service's model resolution. The `InferenceService._resolve_default_id()` method has a documented resolution order ("MLflow Model Registry → filesystem") but the filesystem fallback only checked for a hardcoded `experiment_1.json` path. In practice, MLflow (running via Docker on port 5001 from `make run`) may register the "demo" model with a different experiment ID (e.g., 4). The `load_model()` MLflow download fallback also only searched for models named `dataset-{id}` or `corpus-{id}`, missing the "demo" model name.

### Fixes Applied

1. **`_resolve_default_id()`** (in `anvil/services/inference/inference.py`): Generalised filesystem fallback to scan for any `experiment_*.json` file, not just `experiment_1.json`. This handles the case where MLflow registers the demo model with a non-canonical experiment ID.

2. **`load_model()` MLflow fallback**: Added `"demo"` to the candidate model name set so the demo model is found when downloading from MLflow's Model Registry.

3. **`scripts/seed_demo_model.py`**: Updated to query MLflow for the registered demo model's experiment ID and save the seed artifact to the matching `experiment_{id}.json` path. Previously always saved to `experiment_1.json` regardless of MLflow state.

### Workflow

```bash
make test-e2e-seed    # trains demo model, saves to correct experiment_{id}.json
make test-e2e-full    # seed + run full API e2e suite
```

## See Also

- [[Sessions/2026-06-21-api-e2e-suite]]