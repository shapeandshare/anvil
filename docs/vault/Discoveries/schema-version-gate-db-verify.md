---
aliases:
  - Schema Version Gate and DB Verify
code-refs:
  - anvil/db/schema_version.py
  - anvil/db/registry.py
  - anvil/db/migration.py
  - anvil/cli.py
  - shared/database.mk
created: '2026-06-23'
source: agent
status: draft
tags:
  - type/discovery
  - domain/database
  - domain/tooling
title: 'Schema Version Gate, DB Verify CLI, and Migration Integrity CI Gate'
type: discovery
updated: '2026-06-23'
---
# Discovery: Schema Version Gate, DB Verify CLI, and Migration Integrity CI Gate

## What was found

The codebase had a recurring failure mode: every time Alembic migration 001 was squashed/rewritten to add new tables, databases created before the squash would be missing those tables. Alembic correctly skipped re-running the squashed migration (revision was already at 003), but the application would crash with an opaque `sqlite3.OperationalError: no such table: license_catalog` → HTTP 500 on pages that depended on governance data (`/v1/about`, `/v1/datasets-page`).

This had been encountered at least three separate times. The error provided no useful diagnostic — just "Internal Server Error" with no server-side traceback logged.

## Three-part solution

### 1. Schema Version Constant (hard enforcement)

File: `anvil/db/schema_version.py`

- `SCHEMA_VERSION = 1` — bumped in the same commit that rewrites/squashes migrations
- Stored via SQLite `PRAGMA user_version` (an integer in the DB file header, no table needed, survives migration rewrites)
- `MigrationService.upgrade()` auto-stamps the version after a successful migration
- `MigrationService.ensure_schema_version()` checks at server startup: if `user_version` is non-zero and doesn't match `SCHEMA_VERSION`, prints a clear error and calls `sys.exit(1)`

### 2. `anvil db verify` CLI (diagnosis)

File: `anvil/db/registry.py`, `anvil/cli.py`

- Shared ORM table registry (`anvil/db/registry.py`) provides `get_expected_tables()` — a single source of truth for the canonical table set
- Replaced 15 individual model imports in `env.py` with a single import from the registry
- `anvil db verify` compares expected tables against `sqlite_master`, reports missing tables with an actionable fix message
- Added `make db-verify` target

### 3. CI Migration Integrity Gate (prevention)

File: `scripts/ci/check_migration_integrity.py`

- Detects when migration files change without a corresponding `SCHEMA_VERSION` bump
- Usage: `python3 scripts/ci/check_migration_integrity.py --base-ref origin/main --head-ref HEAD`
- Exit 0 = ok, exit 1 = migrations changed without version bump (prints clear error with list of changed files)

## Makefile fix

All `db-*` Makefile targets were using `$(PYTHON) -m anvil.cli db_main <command>` which was dead code — `cli.py` has no `if __name__ == "__main__"` guard. Fixed to use the `anvil-db` console script (declared in `pyproject.toml`).

## References
- [[Discoveries/Discoveries|Discoveries]]

- `anvil/db/schema_version.py` — `SCHEMA_VERSION` constant
- `anvil/db/registry.py` — `get_expected_tables()` shared registry
- `anvil/db/migration.py` — `get_schema_version()`, `set_schema_version()`, `ensure_schema_version()`, `verify_table_integrity()`
- `anvil/api/app.py` — lifespan handler calls `ensure_schema_version()` after migration
- `anvil/cli.py` — `verify` subcommand in `db_main`
- `shared/database.mk` — `db-verify` target, fixed all db targets
- `scripts/ci/check_migration_integrity.py` — CI gate script
- `anvil/_resources/migrations/env.py` — replaced duplicate model imports with registry
