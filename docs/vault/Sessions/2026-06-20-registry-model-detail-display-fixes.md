---
title: 'Session: Registry Model Detail Display Fixes'
type: session-log
tags:
  - type/session-log
  - domain/registry
created: '2026-06-20'
updated: '2026-06-20'
source: agent
aliases:
  - 'Session: Registry Model Detail Display Fixes'
---
# Session: Registry Model Detail Display Fixes

**Date**: 2026-06-20
**Status**: Completed

## Summary

Fixed three display bugs on the model detail page (`/v1/model-detail/{id}`): `experiment_id` was always `null`, dataset name was a raw numeric param, and timestamps were raw epoch milliseconds.

## Changes

### `anvil/api/v1/registry.py`

**Model ID resolution** (all four endpoints: `get_model`, `get_version`, `delete_version`, `delete_model`):

- Added experiment_id fallback: when `dataset-{id}` / `corpus-{id}` convention lookup fails, iterate `list_registered_models()` and match on `m["id"] == int(model_id)`. This fixes demo models (registered under names like `"demo"`) resolving as model ID 1 or 2.

**Version display data** (`get_model` and `get_version`):

1. **`experiment_id`**: Changed from hardcoded `None` to reading `run.data.tags.get("anvil.experiment_id")` — same pattern as `TrackingService.list_registered_models()`. Now renders as `#1`, `#2` instead of `#null`.

2. **`dataset_name`**: Added DB resolution. Reads `dataset_id` or `corpus_id` from run params, queries `DatasetRepository`/`CorpusRepository` for the human-readable name. Falls back to `"Dataset #{id}"` / `"Corpus #{id}"` if the entity was deleted.

3. **`created_at`**: Added `_fmt_ts()` helper (module-level) that converts epoch ms → `"YYYY-MM-DD HH:MM UTC"` format. Applied to both version-level and model-level timestamps.

## References

- [[Discoveries/registry-model-id-resolution-mismatch]]
