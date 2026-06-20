---
title: 'Session: Demo model moved into user-space loading path'
type: session-log
source: agent
tags:
  - type/session-log
  - domain/inference
  - domain/registry
created: '2026-06-20T00:00:00.000Z'
updated: '2026-06-20T00:00:00.000Z'
aliases:
  - 'Session: Demo model user-space refactor'
  - Demo model refactor
---
# Session: Demo model moved into user-space loading path

**Date**: 2026-06-20
**Branch**: `ui-layout-overhaul`

## Problem

The demo model had two identities — loaded via `_demo_provider` (when `model_id=None`) but listed in the UI via MLflow registration. The playground sent the string `"demo"` as `model_id`, which hit an `isinstance(str)` branch that never resolved to a real file or artifact.

## Changes

### `anvil/services/tracking/tracking.py`
- `list_registered_models()` now reads the `anvil.experiment_id` tag from the MLflow run and returns it as `id` instead of hardcoded `None`.

### `anvil/api/templates/archetypes/playground.html`
- Generate button sends `model.id` (numeric) instead of the string select key as `model_id`.

### `anvil/services/inference/inference.py`
- Removed `_demo_provider` import, attribute, and fallback from `InferenceService`.
- Removed `isinstance(model_id, str)` MLflow-by-name branch from `load_model()`.
- Added `_resolve_default_id()` — three-tier resolution: MLflow (prefer "demo"), then MLflow (any model), then filesystem (`experiment_1.json`).

### `anvil/services/inference/demo_model_provider.py`
- Inline fallback (when system pipeline warmup fails) now saves to `data/models/experiment_1.json` so the filesystem path resolves.

### `tests/unit/services/test_inference.py`
- Replaced `test_inference_service_load_demo` (tested removed `_demo_provider` path) with `test_inference_service_load_by_id` (loads from filesystem by numeric ID).

## Key discoveries

- **`_demo_provider` was a band-aid for the cold-start race**. The warmup runs in a background thread during server startup; the provider was needed because widgets could fire before warmup completed. With `_resolve_default_id()`, both MLflow and filesystem are checked — if neither has a model, the empty state shows cleanly.
- **`list_registered_models()` returned `id: null` for every model** — the `anvil.experiment_id` tag was set on runs but never read during listing. This forced the UI to use model names as identifiers, which didn't match any loading path.
- **The inline fallback was orphaned** — it saved to `data/models/demo/model.json` but `load_model()` only checks `experiment_{id}.json`. This made the fallback invisible to the inference layer.
- **`experiment_1.json` is the well-known path** for the demo model. The demo warmup is always the first experiment allocation at startup, so ID 1 is deterministic.

## Files changed

```
anvil/api/templates/archetypes/playground.html  |  7 +-
anvil/services/inference/demo_model_provider.py |  6 ++
anvil/services/inference/inference.py           | 94 +++++++++++-------
anvil/services/tracking/tracking.py             | 14 +--
tests/unit/services/test_inference.py           | 28 +++++--
```
