# Startup Contract: Auto-Schema Migration on Application Start

**Phase**: 1 — Design & Contracts
**Date**: 2026-06-18
**Feature**: [spec.md](../spec.md)

## Overview

On application startup (FastAPI lifespan), the app replaces the current `Base.metadata.create_all` call with an Alembic migration pipeline. This contract defines the exact startup behavior, config, and error handling.

## Config

| Env Variable | Type | Default | Description |
|-------------|------|---------|-------------|
| `ANVIL_DB_AUTO_MIGRATE` | bool (parsed) | `true` | Auto-migrate on startup (`true`) or strict verify (`false`) |
| `ANVIL_STATE_DB_PATH` | string | `data/anvil-state.db` | SQLite database file path |

## Startup Sequence

```
app startup (FastAPI lifespan)
    │
    ├── 1. init_engine()
    │       → PRAGMA journal_mode=WAL
    │       → PRAGMA foreign_keys=ON
    │
    ├── 2. Read ANVIL_DB_AUTO_MIGRATE from config
    │
    ├── 3. [ANVIL_DB_AUTO_MIGRATE=true] (default)
    │       → MigrationService.upgrade()
    │       ├── DB file exists?
    │       │   ├── YES → alembic upgrade heads
    │       │   └── NO  → create file + dirs → alembic upgrade heads
    │       ├── Success? → log before/after revision → proceed
    │       └── Failure? → log error → exit(1) (server refuses to start)
    │
    └── 4. [ANVIL_DB_AUTO_MIGRATE=false]
            → MigrationService.verify_schema()
            ├── Schema matches HEAD? → proceed
            ├── Schema AHEAD of HEAD? → log warning → exit(1) (prevent data loss)
            └── Schema BEHIND HEAD?
                    → log mismatch
                    → print "Run: anvil db upgrade"
                    → exit(1)

After migration → start MLflow subprocess → start web server
```

## Module: `MigrationService` (`anvil/db/migration.py`)

```python
class MigrationService:
    """Wraps Alembic programmatic API for application startup and CLI usage."""

    def __init__(
        self,
        db_url: str | None = None,
        alembic_ini_path: str | None = None,
    ):
        """
        Args:
            db_url: SQLAlchemy database URL. Defaults to env ANVIL_STATE_DB_PATH.
            alembic_ini_path: Path to alembic.ini. Defaults to project root.
        """
        ...

    async def upgrade(self) -> tuple[str | None, str | None]:
        """
        Apply all pending migrations.
        Returns (before_revision, after_revision).
        Creates DB file + parent dirs if they don't exist.
        """

    async def verify_schema(self) -> None:
        """
        Verify DB schema matches expected HEAD revision.
        Raises MigrationError if:
        - DB is ahead (schema AHEAD of code)
        - DB is behind (pending migrations, auto-migrate disabled)
        """

    async def current(self) -> str | None:
        """Return current DB revision hash, or None if no revision stamped."""

    async def history(self) -> list[dict]:
        """Return list of {revision, down_revision, message} dicts."""

    async def downgrade(self, revision: str = "-1") -> str | None:
        """Roll back to given revision. Returns final revision."""

    async def stamp(self, revision: str) -> None:
        """Stamp DB at revision without running migrations."""

    async def create_revision(self, message: str) -> str:
        """Autogenerate a new migration. Returns revision hash path."""
```

## Changes to Existing Files

### `anvil/api/app.py` (lines 22-25)

**Before**:
```python
await init_engine()
async with async_engine.begin() as conn:
    await conn.run_sync(Base.metadata.create_all)
```

**After**:
```python
await init_engine()
from anvil.db.migration import MigrationService
from anvil.config import get_config

cfg = get_config()
svc = MigrationService()
if cfg["db_auto_migrate"]:
    before, after = await svc.upgrade()
    if before != after:
        logger.info("Auto-migrated DB: %s → %s", before, after)
else:
    await svc.verify_schema()
```

### `anvil/config.py`

**Add**:
```python
"db_auto_migrate": os.getenv("ANVIL_DB_AUTO_MIGRATE", "true").lower()
    in ("true", "1", "yes"),
```

## Error Handling

| Scenario | Behavior | Exit |
|----------|----------|------|
| Migration fails (constraint, syntax) | Log full traceback, roll back | `exit(1)` |
| DB schema ahead of code | Log warning, refuse to start | `exit(1)` |
| DB schema behind (strict mode) | Print `anvil db upgrade` command | `exit(1)` |
| DB file doesn't exist | Create file + parent dirs, run all migrations | `exit(0)` after success |
| Migration race condition (2 instances) | SQLite WAL, one fails with retryable error | Log + `exit(1)` |

## Logging

All migration activity uses the `anvil.db.migration` logger at INFO level:

```log
INFO  [anvil.db.migration] Database does not exist at /path/to/anvil-state.db — creating...
INFO  [anvil.db.migration] Auto-migrating DB: <base> → abc123def456
INFO  [anvil.db.migration] Applied 1 migration(s). Current HEAD: abc123def456
INFO  [anvil.db.migration] Database already at HEAD: abc123def456 — no action needed
ERROR [anvil.db.migration] Migration failed: <traceback>
ERROR [anvil.db.migration] Schema mismatch: DB at def789abc012, code expects abc123def456 (HEAD).
      Run: anvil db upgrade
```

## Guard: SQLite File Management

When the DB file doesn't exist:
1. Check parent directory exists; create it if needed (`pathlib.Path.mkdir(parents=True, exist_ok=True)`)
2. The async engine creation + first connection will create the SQLite file
3. Then run `alembic upgrade heads` to build full schema
4. This replaces the current pattern where `make setup` first runs `mkdir -p data` then `alembic upgrade heads`