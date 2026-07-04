---
aliases:
  - Import queued and download button fix
created: '2026-07-04T00:00:00.000Z'
source: agent
status: draft
tags:
  - type/session-log
  - status/draft
title: >-
  Session: Fix import stuck queued and missing download button for imported
  models
type: session
updated: '2026-07-04T00:00:00.000Z'
---
# Session: Fix import job stuck in "queued" and missing download button for imported models

## Summary

Two bugs in the model import UI:

1. **Import jobs stuck in "queued"** — `_fire_background_import()` caught exceptions in the background worker but never updated the job status to `FAILED`. When the worker crashed (HF API transient error, MLflow blip), the transaction rolled back and the job stayed `QUEUED` permanently — invisible error, no retry possible.

2. **Download button never appears for imported models** — The model detail page used `?source=external` query param (set by the models page links) to detect imported models. Commit `af3fb60` removed this param from links (since the unified catalog now serves all model types). Without it, `loadModelDetail()` fell through to the old registry endpoint — which found the model in MLflow and rendered the trained-model template (no download button, no asset section).

## Changes

### `anvil/api/v1/models.py`

- Added `ModelImportJobStatus` and `datetime.UTC` imports.
- `_fire_background_import()` now catches worker exceptions and opens a fresh session to mark the job as `FAILED` with error code `background_worker_error`, instead of silently reverting to `QUEUED`.

### `anvil/api/templates/archetypes/model_detail.html`

- `loadModelDetail()` now calls the unified catalog `GET /v1/models/{name}` endpoint first to detect the model's `kind` field.
- If `kind === 'external'`, routes to `loadExternalModelDetail()` (shows download button, asset status, etc.).
- Otherwise falls through to the registry-based detail (`loadRegistryModelDetail()`, extracted from the old `loadModelDetail()`).
- `deleteModel()` uses the detected `_modelKind` instead of the stale `urlParams.get('source') === 'external'` check.
- Added `_modelKind` tracking variable.

## Discoveries

- The `ExternalModel` table is no longer populated by the import flow — `register_external_model()` registers directly in the MLflow catalog. The download routes (`POST /v1/models/{model_id}/download`) still expect an integer `ExternalModel` PK and will need a separate fix to work with the unified catalog.
- Background worker pattern (`_fire_background_import`) has a fragility: when `run_import()` fails to commit its transaction-level status updates, the job reverts to its previous DB state. The fix adds a second-chance session to persist the failure state.

## Test Results

`make test`: 305 passed. Models API tests: 18 passed.

## Files Changed

| File | Change |
|------|--------|
| `anvil/api/v1/models.py` | Worker marks jobs as FAILED on exception |
| `anvil/api/templates/archetypes/model_detail.html` | Catalog-based model kind detection |
| `.gitignore` | Added `anvil-state.db` to ignore list |
