---
aliases:
  - 'Session: Schema Version Gate and DB Verify'
created: '2026-06-23'
source: agent
status: draft
tags:
  - type/session-log
  - domain/database
  - domain/tooling
  - domain/infrastructure
  - domain/ui
title: >-
  Session: Schema Version Gate, DB Verify, CI Migration Gate, Health Endpoint
  Enrichment
type: session-log
updated: '2026-06-23'
---
# Session: Schema Version Gate, DB Verify, CI Migration Gate, Health Endpoint Enrichment

**Date**: 2026-06-23
**Trigger**: About and data pages returning 500 errors due to missing `license_catalog` table (migration squash issue recurring for the 3rd+ time). User requested a systematic fix instead of another migration.

## What was done

### 1. Diagnosis

- Reproduced the 500 errors on `/v1/about` and `/v1/datasets-page`
- Identified root cause as `sqlite3.OperationalError: no such table: license_catalog` — migration 001 was squashed after databases were at version 003, so Alembic never created the new tables
- Confirmed the database had only 2 tables (`alembic_version`, `run_id_seq`) vs the expected 22

### 2. Implemented Schema Version Gate

Created `anvil/db/schema_version.py` with `SCHEMA_VERSION = 1`. After a successful migration, `PRAGMA user_version` is set to match. At startup, the lifespan handler calls `ensure_schema_version()` — if the PRAGMA value is non-zero and doesn't match, the server prints a clear error and exits.

### 3. Implemented `anvil db verify` CLI

Created `anvil/db/registry.py` — a shared source of truth for ORM table names, replacing 15 duplicate model imports in `env.py`. Added `verify` subcommand to `cli.py` that compares expected tables against `sqlite_master`. Added `make db-verify` target to Makefile.

### 4. Implemented CI Migration Gate

Created `scripts/ci/check_migration_integrity.py` — detects when migration files change without a corresponding `SCHEMA_VERSION` bump. Fails with clear error listing changed files.

### 5. Fixed Makefile db targets

All `db-*` targets in `shared/database.mk` were using `$(PYTHON) -m anvil.cli db_main <command>` which was dead code — `cli.py` has no `if __name__ == "__main__"` guard. Fixed to use the `anvil-db` console script.

### 6. Enriched Health Endpoint and Ops UI

Updated `/v1/health/detailed` to return:
- `database`: status, schema_version, expected_schema_version, migration_revision
- `mlflow`: status (socket health check), error
- `docs`: swagger (`/docs`) and redoc (`/redoc`) URLs

Updated ops UI template to display an "Infrastructure" card showing DB health badge, schema version, migration revision, MLflow status, and API docs links.

### 7. Fixed Swagger UI and ReDoc Access

Two issues:
- Auth middleware blocked `/docs`, `/redoc`, `/openapi.json` — added to exempt routes
- CSP blocked CDN assets — applied conditional CSP (relaxed for docs, strict for app). Discovered CSP Level 3 ignores `unsafe-inline` when `nonce` is also present.

### 8. Fixed CI failures

Fixed `db_migration` type error in `health_ops.py` (`svc.current()` returns `str | None`). Removed unused imports caught by pre-commit hooks.

## Architecture decisions

- **PRAGMA user_version over custom table** for schema version storage — no table needed, survives database recreation, works on any SQLite DB
- **Conditional CSP** for docs vs app routes — keeps strict nonce-based CSP for app while allowing Swagger/ReDoc CDN assets
- **Shared registry** over individual model imports — single source of truth eliminates duplicate import lists

## Files changed

### New
- `anvil/db/schema_version.py` — SCHEMA_VERSION constant
- `anvil/db/registry.py` — shared ORM table registry
- `scripts/ci/check_migration_integrity.py` — CI migration gate
- `Discoveries/schema-version-gate-db-verify.md` — discovery note
- `Discoveries/csp-blocks-swagger-redoc.md` — discovery note

### Modified
- `anvil/db/migration.py` — added schema version and table integrity methods
- `anvil/api/app.py` — schema version gate in lifespan, conditional CSP
- `anvil/api/v1/health_ops.py` — enriched health endpoint
- `anvil/api/templates/operations.html` — infrastructure card in ops UI
- `anvil/cli.py` — `verify` subcommand
- `anvil/_resources/migrations/env.py` — use registry
- `shared/database.mk` — `db-verify` target, fixed console script usage
- `anvil/api/auth.py` — exempt `/docs`, `/redoc`, `/openapi.json`

## References

- `anvil/db/schema_version.py`
- `anvil/db/registry.py`
- `anvil/db/migration.py`
- `scripts/ci/check_migration_integrity.py`
- PR #168: https://github.com/shapeandshare/anvil/pull/168

## Related

- [[Discoveries/schema-version-gate-db-verify|Schema Version Gate, DB Verify CLI, and Migration Integrity CI Gate]] — discovery note from this session
- [[Discoveries/csp-blocks-swagger-redoc|CSP Blocks Swagger UI and ReDoc CDN Assets]] — discovery note from this session
- [[Decisions/ADR-024-auto-db-migration|ADR-024: Auto DB Schema]] — related database migration decision
- [[Reference/ArchitectureOverview|Architecture]] — database migration and schema context
