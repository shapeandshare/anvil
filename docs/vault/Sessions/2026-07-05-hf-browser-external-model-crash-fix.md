---
title: 'Fix HF Browser 500: ExternalModel table dropped by migration 013'
type: session-log
tags:
  - type/session-log
  - domain/database
  - domain/architecture
created: '2026-07-05'
updated: '2026-07-05'
---
# Fix HF Browser 500: ExternalModel table dropped by migration 013

**Root cause**: Migration `013_drop_external_models.py` intentionally removed the `external_models` table as part of the SC-006/FR-007 migration to `catalog_identities`. However, two route handlers still called `workbench.external_model_repo.find_by_source_identifier()`, which queries the deleted table, producing `sqlite3.OperationalError: no such table: external_models` → HTTP 500.

**Affected endpoints**:
- `GET /v1/hf-browser` (page handler in `pages.py`)
- `GET /v1/models/import/jobs` (JSON API in `models.py`)

**Fix**:
1. Added `find_latest_by_source_identifier()` to `CatalogIdentityRepository` (`catalog_identities.py`) — looks up by `source_type + source_identifier` without requiring `revision_sha`, returns latest match.
2. Replaced `external_model_repo.find_by_source_identifier()` calls in both route handlers with `catalog_identity_repo.find_latest_by_source_identifier()`.
3. Updated test mock in `test_models.py`.

**Verification**: 199/200 tests pass (1 pre-existing eval test failure). The `external_model_repo` remains as a legacy stub but is no longer called at runtime.

**Files changed**:
- `anvil/db/repositories/catalog_identities.py` — new method
- `anvil/api/v1/pages.py` — updated lookup
- `anvil/api/v1/models.py` — updated lookup
- `tests/unit/api/v1/test_models.py` — updated mock
