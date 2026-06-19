# Quickstart: Auto Database Schema Management

**Phase**: 1 — Design & Contracts
**Date**: 2026-06-18
**Feature**: [spec.md](spec.md)

## Developer Setup (What Changes)

Previously, running the app required two steps:
```bash
make setup      # creates venv, installs deps, RUNS DB MIGRATIONS
make run        # starts the server
```

Now, `make setup` still handles venv + deps, but the migration step has moved into app startup:

```bash
make setup      # creates venv, installs deps only (no more migration here!)
make run        # starts server → auto-migrates DB → ready
```

## What Stays the Same

- **Existing `make` targets still work**: `make db-upgrade`, `make db-downgrade`, etc. remain as wrappers around the new CLI
- **Existing `ANVIL_STATE_DB_PATH` env var**: Controls DB location as before
- **Existing Alembic migrations**: All 14 existing migration files unchanged
- **Existing `migrations/env.py`**: Unchanged — the async Alembic env config is correct

## What You Get

### Automatic Migration on Startup

```bash
# Remove DB to test first-run flow
rm -f data/anvil-state.db

# Start server — it creates DB + runs all migrations automatically
make run
```

### CLI Commands for Manual Management

```bash
# Upgrade to latest schema
anvil db upgrade

# Check current revision
anvil db current

# View migration history
anvil db history

# Roll back one migration
anvil db downgrade

# Roll back to specific revision
anvil db downgrade abc123def

# Generate new migration from model changes
anvil db revision -m "add user preferences table"

# Stamp DB at specific revision (bootstrapping)
anvil db stamp abc123def
```

### Disable Auto-Migration (Production/Staging)

```bash
export ANVIL_DB_AUTO_MIGRATE=false
make run
# Server refuses to start if schema is out of date
# → Run: anvil db upgrade
# → Then restart
```

## Migration Path

1. Update `anvil/db/session.py`: `init_engine()` stays the same (WAL + foreign keys)
2. Add `anvil/db/migration.py`: New `MigrationService` class wrapping Alembic commands
3. Modify `anvil/api/app.py` lifespan: Replace `create_all` with `MigrationService.ensure_migrated()`
4. Modify `anvil/config.py`: Add `ANVIL_DB_AUTO_MIGRATE` config key
5. Modify `anvil/cli.py`: Add `db_main()` function with argparse subcommands
6. Modify `pyproject.toml`: Add `anvil-db` entry point
7. Modify `shared/database.mk`: Update Make targets to use new CLI
8. Write tests: `tests/unit/db/test_migration.py`, `tests/e2e/test_db_migration.py`

## Testing

```bash
make test
# Covers:
# - MigrationService.upgrade() on fresh DB
# - MigrationService.upgrade() on up-to-date DB (no-op)
# - MigrationService.verify_schema() (strict mode)
# - verify_schema() when DB is ahead (error)
# - verify_schema() when DB is behind (error)
# - Each CLI subcommand (upgrade, downgrade, current, history, revision, stamp)
# - Startup integration: lifespan handler correctly calls migration
```