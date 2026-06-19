---
aliases:
  - DB Path Mismatch Session
created: '2026-06-18'
tags:
  - type/session-log
  - domain/database
title: DB Path Mismatch Session
type: session-log
updated: '2026-06-18'
source: agent
---
# DB Path Mismatch Session

**Date**: 2026-06-18

## Summary

Fixed HTTP 500 errors on `/v1/datasets` and `/v1/corpora` endpoints caused by a DB path mismatch between `session.py` (connected to `data/anvil.db`) and `MigrationService` (applied to `data/anvil-state.db`). All subsequent DB queries failed with "no such table" because the runtime engine was querying an empty database.

## What Was Done

### Discovery & Diagnosis

- Traced the full call chain from UI error display (`loadCombinedData` in `datasets.html`) through API routes (`/v1/datasets`, `/v1/corpora`), service layer (`DatasetService.list_datasets`, `CorpusService.list`), and repository layer (`DatasetRepository.get_all`, `CorpusRepository.get_all`).
- Identified that both endpoints returning 500 simultaneously suggested a shared root cause — DB session or initialization.
- Verified that two SQLite files existed: `data/anvil.db` (zero tables) and `data/anvil-state.db` (all 8 tables: `alembic_version`, `corpora`, `corpus_files`, `datasets`, `samples`, `curation_operations`, `import_sources`, `training_configs`).
- Confirmed that `config.py` migrated from `ANVIL_DB_PATH` to `ANVIL_STATE_DB_PATH` with a deprecation shim, and `MigrationService` already used `cfg["state_db_path"]` — but `session.py` still read `ANVIL_DB_PATH` directly with its own fallback.

### Fix

- **`anvil/db/session.py`**: Replaced `os.getenv("ANVIL_DB_PATH", "data/anvil.db")` with `cfg["state_db_path"]` from `config.py`, which respects the deprecation path and defaults to `data/anvil-state.db`. Removed unused `os` and `Path` imports.
- Verified: `lsp_diagnostics` clean, both endpoints return 200 with full data.

### Files Changed

| File | Change |
|------|--------|
| `anvil/db/session.py` | Use `cfg["state_db_path"]` instead of `os.getenv("ANVIL_DB_PATH", ...)` |

## Vault Enrichment

- [[Discoveries/db-path-mismatch-session-migration|Discovery: DB Path Mismatch]]
- This session log
