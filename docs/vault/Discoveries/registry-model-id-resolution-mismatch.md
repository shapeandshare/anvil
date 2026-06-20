---
title: Registry Model ID Resolution Mismatch
type: discovery
status: draft
source: agent
session: 2026-06-20-registry-model-detail-display-fixes
related:
  - '[[Sessions/2026-06-20-registry-model-detail-display-fixes]]'
code-refs:
  - anvil/api/v1/registry.py
created: '2026-06-20'
updated: '2026-06-20'
summary: >-
  Registry endpoints resolve integer model_id via dataset-{id}/corpus-{id}
  convention, but the models page passes experiment_id as the ID. This means
  demo models and models not named dataset-X/corpus-X can't be looked up from
  the detail page.
tags:
  - type/discovery
  - domain/registry
  - status/draft
aliases:
  - Registry Model ID Resolution Mismatch
---
# Registry Model ID Resolution Mismatch

The model detail page (`/v1/model-detail/{id}`) wasn't loading for demo models on a fresh system. The root cause: an ID scheme mismatch between how the models page labels models and how the registry API resolves them.

## The Two ID Schemes

**Listing side** (`TrackingService.list_registered_models()`):

- Returns `id: experiment_id` — read from the MLflow run tag `anvil.experiment_id`
- The models page (`models.html`) uses this `m.id` as the View link: `/v1/model-detail/{experiment_id}`

**Detail side** (`GET /v1/registry/models/{model_id}`):

- Attempts to resolve integer `model_id` by searching for MLflow models named `dataset-{id}` or `corpus-{id}`
- This convention-based naming is used when models are registered from an explicit dataset/corpus
- Demo models are registered under arbitrary names (e.g., `"demo"`) — they do not follow the `dataset-X` / `corpus-X` pattern

## Impact

- Model ID 1 (the demo model) would fail to load its detail page on a fresh system
- The page rendered but showed an API error, since the JS fetched `/v1/registry/models/1` which 404'd
- Same issue affected `get_version`, `delete_version`, and `delete_model` endpoints (all shared the same resolution logic)

## Three Display Issues Found

1. **`experiment_id` hardcoded to `None`**: The `get_model` endpoint collected `run_data.params` and `run_data.metrics` from each MLflow run but never read `run.data.tags` — so the `anvil.experiment_id` tag was lost. Template rendered `#null`.

2. **`dataset_name` as raw param**: Set to `run_data["params"].get("dataset_id")` — a numeric string, not a resolved name. For runs without a `dataset_id` param, it was `None`.

3. **Timestamps as epoch ms**: `str(v.creation_timestamp)` — MLflow returns epoch milliseconds as integers, and they were cast to string directly, rendering as `"1718901234567"`.

## Fix

1. **Model ID resolution**: Added experiment_id fallback to all four endpoints. If `dataset-{id}` / `corpus-{id}` lookup fails, iterate `list_registered_models()` and match on `m["id"] == int(model_id)`.

2. **experiment_id**: Read `run.data.tags.get("anvil.experiment_id")` — consistent with `TrackingService.list_registered_models()`.

3. **dataset_name**: Query `DatasetRepository` / `CorpusRepository` from the run's `dataset_id` / `corpus_id` params.

4. **created_at**: New `_fmt_ts()` helper at module level converting epoch ms → `"YYYY-MM-DD HH:MM UTC"`.

## Pre-existing pattern in `list_registered_models`

The model listing endpoint (`tracking.py`) already correctly reads the `anvil.experiment_id` tag. The `get_model` endpoint simply missed this — likely because it was implemented separately without reusing the same run-data-extraction pattern.

## Files affected

- `anvil/api/v1/registry.py` — `_fmt_ts()` helper, all four model ID resolution blocks, version dict construction in `get_model` and `get_version`
