---
title: 011 Auto DB Schema - research
type: research
tags:
  - type/spec
spec-refs:
  - docs/vault/Specs/011 Auto DB Schema/
related:
  - '[[011 Auto DB Schema]]'
created: ~
updated: ~
---
# Research: Auto Database Schema Management

**Phase**: 0 — Outline & Research
**Date**: 2026-06-18
**Feature**: [spec.md](spec.md)

## Overview

Research decisions for replacing the current `Base.metadata.create_all` startup pattern with a proper Alembic migration pipeline, adding CLI commands, and cross-referencing MLflow's approach.

---

## Decision 1: Programmatic Alembic Integration

**Decision**: Use `alembic.command` programmatic API via a `MigrationService` wrapper class. The service reads the Alembic config at runtime (overriding `sqlalchemy.url` with the app's resolved DB path), then delegates to `alembic.command.upgrade()`, `.downgrade()`, `.current()`, `.history()`, `.revision()`, `.stamp()`.

**Rationale**:
- The existing `migrations/env.py` already handles async engines correctly via `async_engine_from_config`
- Using `alembic.command` from Python code (not subprocess) is the documented Alembic approach
- The `alembic.ini` `sqlalchemy.url` can be overridden at runtime via `config.set_main_option("sqlalchemy.url", url)`, which is exactly how MLflow does it in `_get_alembic_config()`
- This preserves all existing migration files and env config — zero changes needed there

**Alternatives considered**:
- **Subprocess call**: `subprocess.run(["alembic", "upgrade", "head"])` — fragile, loses error context, harder to test
- **Shelling out via Make**: `make db-upgrade` — requires make installed, not suitable for pip-installable CLI
- **`Base.metadata.create_all` (current)**: Doesn't run migrations, only creates from ORM metadata. Misses schema changes that aren't reflected in models (e.g., raw SQL in migrations)

**Key pattern (from MLflow's `mlflow/store/db/utils.py`)**:
```python
def _upgrade_db(engine):
    from alembic import command
    db_url = str(engine.url)
    config = _get_alembic_config(db_url)
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "heads")
```

---

## Decision 2: Auto-Migrate vs. Strict Verification

**Decision**: Option C — Hybrid approach (user-selected).
- `ANVIL_DB_AUTO_MIGRATE=true` (default): auto-migrate on startup — `alembic upgrade head` before server accepts requests
- `ANVIL_DB_AUTO_MIGRATE=false`: strict verification — check revision matches HEAD, refuse to start if out of date, print `anvil db upgrade` command

**Rationale**:
- Auto-migrate by default matches the "Pit of Success" constitutional principle
- Strict verification via env var covers production/staging where explicit control is required
- MLflow uses BOTH approaches (auth store auto-migrates, tracking store verifies) — anvil gets the best of both

**Edge case handling**:
- **DB doesn't exist**: Create file + parent dirs, then run all migrations from scratch
- **DB is ahead of code**: Refuse to start, log warning (preventing data loss)
- **Migration fails**: Roll back, log error, exit non-zero
- **Race condition**: SQLite WAL mode handles concurrent access gracefully

---

## Decision 3: CLI Subcommand Structure

**Decision**: Single `anvil-db` console script entry point with argparse subparsers. The `db_main()` function uses a parent parser with subcommands matching the existing `corpus_main()` pattern in `anvil/cli.py`.

**Rationale**:
- Matches existing CLI pattern (`corpus_main()` with subcommands `create`, `ingest`, `list`, etc.)
- Single pyproject.toml entry point (`anvil-db = "anvil.cli:db_main"`) vs. 6 separate entry points
- Consistent UX: `anvil db upgrade`, `anvil db current`, etc.
- Makefile targets can be thin wrappers: `make db-upgrade` → `$(PYTHON) -m anvil.cli db_main`

**CLI commands (spec FR-006)**:

| Command | Args | Delegates to |
|---------|------|-------------|
| `anvil db upgrade` | (none) | `alembic.command.upgrade(config, "heads")` |
| `anvil db downgrade` | `[-n N\|REVISION]` | `alembic.command.downgrade(config, revision)` |
| `anvil db current` | (none) | `alembic.command.current(config)` |
| `anvil db history` | (none) | `alembic.command.history(config)` |
| `anvil db revision` | `-m "message"` | `alembic.command.revision(config, autogenerate=True, message=msg)` |
| `anvil db stamp` | `<revision>` | `alembic.command.stamp(config, revision)` |

---

## Decision 4: MigrationService API Design

**Decision**: Encapsulate all Alembic operations in `anvil/db/migration.py` as a `MigrationService` class with async-compatible methods.

**API surface**:
```python
class MigrationService:
    def __init__(self, db_url: str | None = None, alembic_ini_path: str | None = None):
        # Resolve config at init time
        ...

    async def upgrade(self) -> tuple[str, str]:
        """Apply all pending migrations. Returns (before_rev, after_rev)."""

    async def downgrade(self, revision: str = "-1") -> str:
        """Roll back to given revision. Returns final revision."""

    async def current(self) -> str | None:
        """Get current DB revision hash."""

    async def history(self) -> list[dict]:
        """Get migration history as structured list."""

    async def stamp(self, revision: str) -> None:
        """Stamp DB at revision without running migrations."""

    async def create_revision(self, message: str) -> str:
        """Auto-generate a new migration. Returns revision hash."""

    async def verify_schema(self) -> bool:
        """Check if DB schema matches HEAD. Returns True if match."""

    async def ensure_migrated(self) -> None:
        """Run upgrade or strict-verify based on ANVIL_DB_AUTO_MIGRATE."""
```

**Async pattern**: Alembic is sync, so wrap with `asyncio.get_event_loop().run_in_executor(None, lambda: sync_call)` — matching the project's existing pattern in `anvil/cli.py` (e.g., safetensors export).

---

## Decision 5: Config Changes

**Decision**: Add `ANVIL_DB_AUTO_MIGRATE` to `anvil/config.py` `get_config()` return value. Rename existing `ANVIL_DB_PATH` reference to `ANVIL_STATE_DB_PATH` (already handled as a deprecation path).

**New config key**:
```python
"db_auto_migrate": os.getenv("ANVIL_DB_AUTO_MIGRATE", "true").lower() in ("true", "1", "yes"),
```

---

## Decision 6: Startup Flow

**Decision**: Replace the existing `Base.metadata.create_all` in the FastAPI lifespan with a call to `MigrationService.ensure_migrated()`.

**Current flow** (app.py lifespan, lines 22-25):
```python
await init_engine()
async with async_engine.begin() as conn:
    await conn.run_sync(Base.metadata.create_all)
```

**New flow**:
```python
await init_engine()
cfg = get_config()
svc = MigrationService(db_url=SQLALCHEMY_DATABASE_URL)
if cfg["db_auto_migrate"]:
    before, after = await svc.upgrade()
    if before != after:
        logger.info("Migrated DB from %s to %s", before, after)
else:
    await svc.verify_schema()  # Raises if out of date
```

---

## References

1. Alembic Programmatic API: https://alembic.sqlalchemy.org/en/latest/api/commands.html
2. MLflow `_upgrade_db` + `_verify_schema`: `mlflow/store/db/utils.py`
3. MLflow auth `migrate_if_needed`: `mlflow/server/auth/db/utils.py`
4. MLflow CLI `db upgrade`: `mlflow/db.py`
5. Existing anvil `migrations/env.py` — async engine config
6. Existing anvil `corpus_main()` — argparse subcommand pattern in `anvil/cli.py`