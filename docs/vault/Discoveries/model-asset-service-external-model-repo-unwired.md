---
aliases:
  - ModelAssetService ExternalModel dead wire
created: '2026-07-04T00:00:00.000Z'
source: agent
status: draft
tags:
  - type/discovery
  - status/draft
  - domain/registry
  - domain/architecture
title: >-
  ModelAssetService ExternalModel Repository Wired as None: Download Pipeline
  Dead
updated: '2026-07-04T00:00:00.000Z'
type: discovery
code-refs:
  - 'anvil/workbench.py:732-743'
  - 'anvil/services/model_import/model_asset_service.py:132-178'
  - anvil/db/repositories/external_models.py
---
# ModelAssetService ExternalModelRepository Wired as None — Download Pipeline Dead

## Discovery

`ModelAssetService` (powering `POST /v1/models/{model_id}/download`) was initialized with `None` for its `external_model_repo` parameter in `AnvilWorkbench.model_assets`. All download operations (`submit_download`, `run_download`, `get_assets_for_model`) call `self._model_repo.get()` and `self._model_repo.update_fields()` — both crash with `AttributeError: 'NoneType' object has no attribute 'get'` when the repo is `None`.

The same issue existed for `ModelImportService.model_imports` (also wired with `None`), though the import flow's `run_import()` had been refactored to use catalog identities and didn't call the deprecated repo — until we added ExternalModel creation for download support.

## Root Cause

The `ExternalModelRepository` was deprecated in favor of `CatalogIdentityRepository` + `ModelCatalogService`. The workbench wiring was set to `None` with a `# legacy` comment during the catalog migration. However, the download pipeline (`ModelAssetService`) was never refactored to use the catalog — it still depends on `ExternalModelRepository.get()` to resolve model identities for asset download.

## Impact

- All download button clicks would crash the background worker silently (caught by the generic `logger.exception` handler)
- The Import Jobs panel's "Download" button for completed imports was non-functional
- UI lacked download buttons entirely because `external_model_id` was never populated in template context

## Fix

1. Added `external_model_repo` lazy property to `AnvilWorkbench`
2. Wired it into both `model_imports` and `model_assets` service initializers
3. Added `find_by_source_identifier()` to `ExternalModelRepository` for looking up models by source type + identifier (not revision SHA, which was too strict)
4. Modified `ModelImportService.run_import()` to create `ExternalModel` rows after successful catalog registration, bridging the legacy download pipeline

## Code Locations

- `anvil/workbench.py:732-743` — model_assets property (was passing None)
- `anvil/services/model_import/model_asset_service.py:132-178` — submit_download uses `self._model_repo.get()`
- `anvil/services/model_import/model_asset_service.py:247-370` — run_download uses `self._model_repo.get()` and `self._model_repo.update_fields()`
- `anvil/db/repositories/external_models.py` — the legacy repo (still functional, still needed)

## See Also

- `anvil/db/models/external_model.py` — Deprecated ExternalModel ORM
- `anvil/db/repositories/catalog_identities.py` — The replacement CatalogIdentityRepository
- [[Sessions/2026-07-04-hf-browser-download-buttons|Session log]]
