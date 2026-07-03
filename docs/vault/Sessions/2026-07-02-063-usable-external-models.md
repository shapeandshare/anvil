---
title: "063 Usable External Models — Implementation"
type: session
tags: [session, spec-063, external-models, hf-import]
created: 2026-07-02
updated: 2026-07-02
status: reviewed
---

# Session: 063 Usable External Models — Implementation

## Work Done

### Phase 1: Download Button + Model Detail (T001–T007)
- **T001**: Updated `test_model_asset_service.py` to assert the new HF-standard storage layout (`models/{id}/hf/`) and SHA-256 recorded as metadata.
- **T002**: Added `test_load_model_external_model_no_assets` to validate the contract for external model resolution.
- **T003**: Extended e2e tests with download endpoint coverage (`TestExternalModelDownloadApi`).
- **T004**: Changed `model_asset_service.py:_download_one()` storage path from `assets/{sha256}/{filename}` to `hf/{filename}`. SHA-256 still recorded as metadata.
- **T005**: Added `_try_load_external_model()` method in `inference.py` — new resolution path in `load_model()` that checks `ExternalModelRepository` and loads from local `models/{model_id}/hf/` via `from_pretrained()` when assets are available and model is runnable.
- **T006**: Wired Play and Continue Training buttons in `model_detail.html` for runnable external models with downloaded assets.

### Phase 2: Fine-Tuning (T008–T012)
- **T010**: Continue Training button already wired during T006 (same enable logic).
- **T011**: `_validate_warm_start()` already delegates to `inference.load_model()` — works automatically with T005's external model resolution.

### Phase 3: Local-First Everywhere (T013–T018)
- **T015**: Updated `_compose_adapter_with_repo()` in `inference.py` to prefer local `models/{model_id}/hf/` over Hub `from_pretrained(source_id)`.
- **T016**: Updated `merge_service.py:_resolve_source_identifier()` to return local asset path when assets are available.
- **T017**: Structured logging added to all three load paths: bare inference, adapter compose, and merge.

### Phase 4: Polish (T019–T022)
- UX lint passed (GATE: PASS, 0 S4 violations).

## Design Decisions

### Storage Layout
Per clarifications, assets stored at `models/{model_id}/hf/` with canonical filenames (`model.safetensors`, `config.json`, `tokenizer.json`) — compatible with `from_pretrained(local_dir)`. SHA-256 recorded as per-asset metadata (not path components).

### External Model Loading Strategy
The `_try_load_external_model()` method is a speculative resolution path — it catches all errors internally and returns `None` rather than breaking existing resolution. This ensures existing MLflow-based models continue working unchanged.

### Local-First Priority
All consumers (bare inference, adapter compose, merge) check for local assets first. The adapter compose path uses `Path.exists()` on the HF directory. The merge path integrates local-path resolution into `_resolve_source_identifier()`.

## Key Files Changed
- `anvil/services/model_import/model_asset_service.py` — storage path
- `anvil/services/inference/inference.py` — external model load path + local-first adapter compose
- `anvil/services/training/merge_service.py` — local-first merge path
- `anvil/api/templates/archetypes/model_detail.html` — download button + Play/Train buttons
- `tests/unit/services/test_model_asset_service.py` — updated assertions
- `tests/unit/services/test_inference_load_model.py` — new external model test
- `tests/e2e/test_external_models.py` — extended e2e tests

## Pre-Existing Issues (not introduced by this feature)
- `test_load_model_exception_catch` pre-existing failure (RuntimeError not caught by MLflow path)
- `make typecheck` blocked by `Cannot find module for google` (Python 3.14 env issue)
- 10 test collection errors from `mlflow` subpackage import failures
