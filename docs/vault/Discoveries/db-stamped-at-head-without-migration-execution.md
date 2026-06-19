---
aliases:
  - DB Stamped at HEAD Without Migration Execution
code-refs:
  - anvil/db/migration.py
  - anvil/db/session.py
  - migrations/versions/
created: '2026-06-18'
related:
  - '[[Sessions/2026-06-18-db-stamped-without-tables]]'
session: 2026-06-18-db-stamped-without-tables
source: agent
summary: >-
  The application database was at Alembic revision 013 (stamped in
  alembic_version) but had never executed migration SQL — only 2 tables existed
  (alembic_version, run_id_seq). All application tables (datasets, corpora,
  etc.) were missing, causing HTTP 500 on every endpoint.
tags:
  - type/discovery
  - domain/database
  - status/draft
title: DB Stamped at HEAD Without Migration Execution
type: discovery
updated: '2026-06-18'
---
The SQLite database at `data/anvil-state.db` reported Alembic revision `013` via its `alembic_version` table but had only 2 tables — `alembic_version` and `run_id_seq` — out of the 8 expected. All migration bodies from `001_initial.py` through `013_drop_experiment_registry_tables_add_run_id_seq.py` were skipped despite Alembic believing the schema was up-to-date.

## Symptoms

- Every endpoint hitting the DB returned HTTP 500 with `sqlite3.OperationalError: no such table: datasets`
- Appeared identical to missing table errors, not connection errors
- Both `datasets` endpoints AND `corpora` endpoints failed identically (shared root cause)
- The `MigrationService.upgrade()` reported `Before: 013, After: 013` — a no-op

## Root Cause

The database was in a state where `alembic_version` was stamped at revision `013` but the actual schema objects (tables, indexes) created by migrations `001` through `013` were absent. Only `run_id_seq` existed because it was created by migration `013` itself. This mismatch between Alembic's version table and the physical schema caused `ensure_migrated()` to silently skip all pending work — Alembic saw `013 == heads` and returned immediately without running any migrations.

How this state arose is unclear, but the likely causes (in order):
1. **Stamp without execution**: A previous run of `alembic stamp 013` (or equivalent through `MigrationService.stamp()`) was invoked, which creates/populates `alembic_version` without running migration SQL
2. **Partial upgrade + crash**: An earlier upgrade crashed after writing the revision stamp but before committing DDL — though SQLite's transactional DDL should prevent this
3. **DB file replacement**: The `alembic_version` table was somehow copied from another database without the schema objects

## Fix

1. Backed up the stale DB: `data/anvil-state.db → data/anvil-state.db.backup`
2. Dropped both stale tables: `alembic_version` and `run_id_seq`
3. Re-ran `MigrationService.upgrade()` which applied all 14 migrations in order:

```
None → 001 → 002 → 003 → 004 → 005 → 006 → 002b → 
12a4027155f0 (merge) → 007 → 008 → 009 → 010 → 011 → 013
```

4. Verified all 8 application tables were created (`datasets`, `corpora`, `corpus_files`, `samples`, `curation_operations`, `import_sources`, `training_configs`, `run_id_seq`)
5. Confirmed both `/v1/datasets` and `/v1/corpora` return 200

## Implications

- `run_id_seq` was dropped and recreated — any previous run ID sequence state was lost
- No other data was present in the database (empty tables), so no data loss occurred
- The stale backup file `data/anvil-state.db.backup` can be deleted after confirmation
- This scenario should be detectable by health/audit tooling: a warning when `alembic_version` exists but expected tables are missing

## References

- `anvil/db/migration.py` — `MigrationService.ensure_migrated()` / `upgrade()` entry points
- `anvil/db/session.py` — DB session factory that connects to the same path
- `migrations/versions/` — all 14 migration scripts (`001` through `013` + merge)
- `data/anvil-state.db.backup` — stale DB backup on disk
