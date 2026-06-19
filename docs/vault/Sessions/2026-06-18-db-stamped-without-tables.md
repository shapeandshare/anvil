---
aliases:
  - DB Stamped at HEAD Without Migration Execution Session
created: '2026-06-18'
tags:
  - type/session-log
  - domain/database
title: DB Stamped at HEAD Without Tables
type: session-log
updated: '2026-06-18'
source: agent
---
# DB Stamped at HEAD Without Tables

**Date**: 2026-06-18

## Summary

Fixed HTTP 500 on `/v1/datasets` and `/v1/corpora` — the database was at Alembic revision 013 in `alembic_version` but had never executed the migration SQL. All 8 application tables were missing. Fixed by dropping the stale `alembic_version` + `run_id_seq` tables and re-running all 14 migrations from scratch.

## What Was Done

### Diagnosis

- Confirmed both endpoints returned "Internal Server Error" via curl
- Traced the call chain: route handler → `Depends(get_service)` → `DatasetService.list_datasets()` / `CorpusService.list()` → `repo.get_all()` → `session.execute(select(...))`
- Isolated the error by querying the DB directly using the venv Python: `sqlite3.OperationalError: no such table: datasets`
- Inspected SQLite schema: only `alembic_version` (at version 013) and `run_id_seq` existed
- `MigrationService.upgrade()` reported `Before: 013, After: 013` — a no-op because Alembic believed the schema was current

### Fix

1. Backed up: `data/anvil-state.db` → `data/anvil-state.db.backup`
2. Dropped both stale tables
3. Re-ran upgrade — all 14 migrations applied:
   - `001_initial` → creates `datasets`, `training_configs`, `experiments`
   - `002_add_corpus_tables` → creates `corpora`, `corpus_files`
   - `003` through `013` → modifies/extends schema, drops experiments
4. Verified 8 tables: `alembic_version`, `corpora`, `corpus_files`, `curation_operations`, `datasets`, `import_sources`, `run_id_seq`, `samples`, `training_configs`
5. Both endpoints return 200 with empty results

## Vault Enrichment

- [[Discoveries/db-stamped-at-head-without-migration-execution|Discovery: DB Stamped at HEAD Without Migration Execution]]
- This session log
