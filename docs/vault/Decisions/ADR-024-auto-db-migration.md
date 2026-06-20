---
title: ADR-016 — Auto Database Schema Migration
type: decision
tags:
  - type/decision
  - domain/infrastructure
created: '2026-06-18T00:00:00.000Z'
updated: '2026-06-18T00:00:00.000Z'
aliases:
  - ADR-016
  - Auto Database Schema Migration
source: agent
code-refs:
  - anvil/db/migration.py
  - anvil/api/app.py
  - anvil/config.py
---
# ADR-016: Auto Database Schema Migration

**Status**: Accepted

## Context

The app required `make setup` to initialize the database via Alembic migrations before the first `make run`. This created friction for developers who just wanted to clone and run. Meanwhile, the FastAPI lifespan handler used `Base.metadata.create_all` — which only creates tables from ORM model metadata but does NOT run Alembic migrations. This dual-path schema management was risky: `create_all` could diverge from the migration chain, and schema changes in migrations (column adds, raw SQL) were silently skipped on fresh startup.

MLflow's approach was studied as a reference: the main tracking store (`mlflow/store/tracking/sqlalchemy_store.py`) uses strict schema verification — refuses to start if the schema is out of date and requires explicit `mlflow db upgrade`. The auth store (`mlflow/server/auth/sqlalchemy_store.py`) auto-migrates on startup via `migrate_if_needed()`.

## Decision

**Option C — Hybrid**: Auto-migrate on startup by default, with a strict verification mode for production.

| Env Var | Default | Behavior |
|---------|---------|----------|
| `ANVIL_DB_AUTO_MIGRATE=true` | ✅ default | `alembic upgrade heads` runs in the FastAPI lifespan before the server accepts requests |
| `ANVIL_DB_AUTO_MIGRATE=false` | — | Strict verification: checks current revision matches HEAD, refuses to start if out of date, prints `anvil db upgrade` |

The auto-migration path creates the SQLite file + parent directories if they don't exist, then applies all pending migrations. If a migration fails, the error is logged and the server exits with a non-zero code.

### CLI Commands

Six subcommands are exposed under `anvil db`:

| Command | Delegates To |
|---------|-------------|
| `anvil db upgrade` | `alembic.command.upgrade(config, "heads")` |
| `anvil db downgrade [revision]` | `alembic.command.downgrade(config, revision)` |
| `anvil db current` | Direct `alembic_version` table read |
| `anvil db history` | `ScriptDirectory.walk_revisions()` |
| `anvil db revision -m "msg"` | `alembic.command.revision(config, autogenerate=True, message=msg)` |
| `anvil db stamp <revision>` | `alembic.command.stamp(config, revision)` |

## Consequences

**Positive**:
- Single command to go from clone to running app (`make setup && make run` → `make setup && make run` with migration now happening at `run` time instead)
- Safer startup: `alembic upgrade heads` replaces `create_all`, eliminating dual-path divergence
- Production safety valve via `ANVIL_DB_AUTO_MIGRATE=false`
- Existing Make targets (`db-upgrade`, etc.) continue to work, now delegated through the unified CLI
- All existing migrations and Alembic config untouched

**Negative**:
- Auto-migration on startup means the server may be slower to start on version upgrades (mitigated by SC-003: <2s for one pending migration)
- Race condition if two server instances start simultaneously (mitigated by SQLite WAL mode — one succeeds, the other gets `database is locked`)
- Operators who want strict control must remember to set `ANVIL_DB_AUTO_MIGRATE=false` in production environments

## Compliance

- `anvil/db/migration.py` wraps all Alembic interactions; the lifespan handler in `anvil/api/app.py` is the sole caller of `ensure_migrated()`
- The `ANVIL_DB_AUTO_MIGRATE` env var is read from `anvil/config.py` `get_config()` (cached via `@lru_cache`)
- Existing `make setup` still runs `alembic upgrade heads` via the CLI for backward compatibility
- All new code passes `mypy --strict`
