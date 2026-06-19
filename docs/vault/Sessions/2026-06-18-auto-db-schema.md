---
title: Auto Database Schema Management Session
type: session-log
tags:
  - type/session-log
  - domain/infrastructure
created: '2026-06-18T00:00:00.000Z'
updated: '2026-06-18T00:00:00.000Z'
---
# Auto Database Schema Management Session

**Date**: 2026-06-18

## Summary

Replaced the `Base.metadata.create_all` approach in the FastAPI lifespan with a proper Alembic migration pipeline. Added `anvil db` CLI subcommand group for explicit migration management. This eliminates the need for `make setup` to initialize the database — the app creates + migrates its schema on first startup.

## What Was Done

### Discovery & Research

- Explored MLflow's approach to database management: `mlflow/store/db/utils.py` uses strict schema verification (`_verify_schema`) on the main tracking store (refuses to start if out of date), while the auth store (`mlflow/server/auth/db/utils.py`) auto-migrates via `migrate_if_needed`. Documented the tension between convenience and safety.
- Researched `alembic.command` programmatic API — confirmed `command.upgrade()`, `.downgrade()`, `.current()`, `.stamp()`, `.revision()`, and `ScriptDirectory.from_config()` for history enumeration.
- Audited the existing codebase: 14 Alembic migration versions, async engine in `anvil/db/session.py`, async env in `migrations/env.py`, `Base.metadata.create_all` in `anvil/api/app.py` lifespan handler.

### Design Decisions

- **Option C (hybrid)**: `ANVIL_DB_AUTO_MIGRATE=true` (default, auto-migrate). `ANVIL_DB_AUTO_MIGRATE=false` switches to strict verification (MLflow tracking store model). Formalized as ADR-016.
- **MigrationService**: Wraps `alembic.command.*` calls via `run_in_executor` for async compatibility with FastAPI's event loop.
- **CLI**: Single `db_main()` function with argparse subparsers (matching existing `corpus_main()` pattern), registered as `anvil-db` console script in `pyproject.toml`.

### Implementation

| Layer | Files |
|-------|-------|
| **Service** | `anvil/db/migration.py` — `MigrationService` class (116 lines) |
| **Config** | `anvil/config.py` — added `db_auto_migrate` key |
| **Startup** | `anvil/api/app.py` — replaced `create_all` with `ensure_migrated()` |
| **CLI** | `anvil/cli.py` — added `db_main()` with 6 subcommands |
| **Entry point** | `pyproject.toml` — added `anvil-db` script |
| **Makefile** | `shared/database.mk` — delegated to new CLI |
| **Doc/Config** | `.env.example`, `README.md`, `.dockerignore` |

### Tests (38 total, all pass)

| Suite | Count | Scope |
|-------|-------|-------|
| Unit — MigrationService | 19 | Construction, upgrade, verify_schema, current, history, downgrade, stamp, revision, ensure_migrated |
| Unit — CLI | 9 | Argument parsing, delegation, error handling |
| End-to-end | 10 | Fresh DB auto-create, idempotency, strict verify, downgrade roundtrip, history, stamp |

### Key Files Changed

| File | Change |
|------|--------|
| `anvil/db/migration.py` | NEW — MigrationService wrapping Alembic commands |
| `anvil/api/app.py` | Replace `Base.metadata.create_all` with `MigrationService.ensure_migrated()` |
| `anvil/config.py` | Add `ANVIL_DB_AUTO_MIGRATE` config key |
| `anvil/cli.py` | Add `db_main()` with 6 argparse subcommands |
| `pyproject.toml` | Add `anvil-db` console script entry point |
| `shared/database.mk` | Delegate all targets to `anvil-db` CLI |

## What Was Learned

- `get_config()` uses `@lru_cache` which causes stale config across test runs — test environments must call `get_config.cache_clear()` before setting env vars.
- Alembic's `ScriptDirectory` is imported inside methods (not at module level), which affects where `unittest.mock.patch` targets need to point.
- The `alembic_version` table stores a single `version_num` row; reading it directly via SQL is more reliable than parsing `alembic.command.current()` stdout.
- SQLAlchemy's sync `create_engine` (without `+aiosqlite`) is needed for simple metadata queries in `run_in_executor` callbacks.

## Vault Enrichment

- [[Decisions/ADR-016-auto-db-migration|ADR-016: Auto Database Schema Migration]]
- This session log
