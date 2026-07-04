---
title: 042 Model Asset Storage - Quickstart
type: spec
tags:
  - type/spec
created: 
updated: 2026-07-03
---

# Quickstart: Model Asset Storage (042)

**Date**: 2026-06-28 | **Branch**: `042-model-asset-storage`

## Goal

After this spec is implemented, a learner can download the weights, tokenizer, and config for an imported model — making it usable for fine-tuning and inference.

## What You'll Be Able to Do

1. **Import a model** (spec 040) → metadata-only entry with `METADATA_ONLY` status
2. **Download its assets** → trigger an async job that downloads safetensors weights + tokenizer + config
3. **Track progress** → poll the job status endpoint; see per-file progress (bytes downloaded, SHA-256 verified)
4. **Use the model** → status flips to `ASSETS_AVAILABLE`; model ready for fine-tuning

## Implementation Order

### Round 1 — Infrastructure (Foundation)
1. `anvil/services/_shared/encryption.py` — AES-256-GCM encrypt/decrypt
2. `anvil/db/models/user_secret.py` — UserSecret ORM model
3. `anvil/db/repositories/user_secret_repository.py` — CRUD
4. `anvil/db/models/model_asset.py` — ModelAsset ORM model (with `ModelAssetType`, `ModelAssetStatus` enums)
5. `anvil/db/models/asset_download_job.py` — AssetDownloadJob ORM model
6. `anvil/services/_shared/asset_download_job_status.py` — StrEnum for job status

### Round 2 — Repositories
7. `anvil/db/repositories/model_asset_repository.py`
8. `anvil/db/repositories/asset_download_job_repository.py`

### Round 3 — Service Layer
9. `anvil/services/_shared/encryption.py` — wire up the `EncryptionService` implementation
10. `anvil/services/model_import/model_asset_service.py` — `AssetDownloadService` implementation
    - `submit_download()` — create job + pre-create ModelAsset rows
    - `run_download()` — resolve file list, download each file, store, checksum
    - `get_job_status()` — return aggregate + per-asset progress
11. Extend `hf_source.py` — add `list_repo_files()`, `download_file()`, format detection

### Round 4 — API Layer
12. Add route to `anvil/api/v1/models.py` — `POST /v1/models/{id}/download` (HTTP 202)
13. Add route — `GET /v1/models/{id}/download/{job_id}/status`
14. Add route — `GET /v1/models/{id}/assets`
15. Add route — `POST /v1/user/secrets` (set HF token)
16. Wire `_fire_background_download()` matching the import pattern

### Round 5 — SDK + Workbench
17. Expose `ModelAssetService` via `AnvilWorkbench`
18. Add SDK client commands in `anvil/client/models/`

### Round 6 — Alembic Migration
19. `make db-revision` → auto-generate migration for new tables
20. Verify migration is reversible

### Round 7 — Tests
21. Unit tests for `encryption.py`
22. Unit tests for `ModelAssetRepository`
23. Unit tests for `UserSecretRepository`
24. Unit tests for `ModelAssetService`
25. E2E tests for download endpoints
26. E2E test: gated model + no token → actionable error

## Key Files to Create

```
NEW:
  anvil/db/models/model_asset.py
  anvil/db/models/asset_download_job.py
  anvil/db/models/user_secret.py
  anvil/db/repositories/model_asset_repository.py
  anvil/db/repositories/asset_download_job_repository.py
  anvil/db/repositories/user_secret_repository.py
  anvil/services/_shared/asset_download_job_status.py
  anvil/services/_shared/encryption.py
  anvil/services/model_import/model_asset_service.py
  anvil/services/model_import/download_worker.py        # streaming + checksum logic
  anvil/services/model_import/format_detector.py         # FR-033 format verification
  tests/unit/db/repositories/test_model_asset_repository.py
  tests/unit/db/repositories/test_user_secret_repository.py
  tests/unit/services/test_model_asset_service.py
  tests/unit/services/test_encryption.py
  tests/e2e/test_model_assets.py

MODIFY:
  anvil/db/models/external_model.py                     # add relationship to ModelAsset
  anvil/services/model_import/hf_source.py              # add download methods
  anvil/api/v1/models.py                                # add download routes
  anvil/workbench.py                                    # expose ModelAssetService
  anvil/client/models/                                  # add SDK commands
```

## Acceptance Checklist

- [ ] `SC-001`: Learner downloads assets → tracked, checksummed, marked available
- [ ] `SC-002`: SaaS mode assets stored in LakeFS, org-scoped (future — verify seam)
- [ ] `SC-003`: Interrupted download resumes cleanly
- [ ] `SC-004`: Unsupported format (GGUF) refused before download
- [ ] `SC-005 (NMRG)`: Pre-existing tests pass; local mode uses FileStore with no cloud deps