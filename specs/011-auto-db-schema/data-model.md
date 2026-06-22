# Data Model: Auto Database Schema Management

**Phase**: 1 — Design & Contracts
**Date**: 2026-06-18
**Feature**: [spec.md](../spec.md)

## Overview

This feature introduces no new persistent business entities. Its "data" is the Alembic migration infrastructure and the application database file itself. The models below describe the operational entities, not business-domain objects.

---

## Entity 1: Alembic Migration (Version)

| Attribute | Type | Description |
|-----------|------|-------------|
| `revision` | string (hash) | Unique identifier for this migration (e.g., `abc123def456`) |
| `down_revision` | string (hash) \| `None` | Parent revision; `None` for the initial migration |
| `branch_labels` | string \| `None` | Branch labels (anvil uses linear chain, no branches) |
| `depends_on` | string \| `None` | Explicit dependency reference (unused in anvil) |

**Persistence**: Stored in `alembic_version` table (single row with `version_num` column). Managed entirely by Alembic.

**Relationships**:
- Forms a singly-linked list via `down_revision → revision` chain
- `revision == HEAD` means all migrations applied
- Each version corresponds to a file in `migrations/versions/<rev>_<name>.py`

**Validation**:
- Chain must be linear and complete (no gaps)
- `down_revision` of each migration must exist in the chain
- Cycle detection is implicit in Alembic's DAG resolution

---

## Entity 2: Application Database (`anvil-state.db`)

| Attribute | Type | Description |
|-----------|------|-------------|
| `path` | string | Filesystem path, resolved from `ANVIL_STATE_DB_PATH` env var |
| `exists` | bool | Whether the SQLite file exists on disk |
| `current_revision` | string \| `None` | Current Alembic revision hash (from `alembic_version` table) |

**State transitions**:
```
DOES_NOT_EXIST → [create file] → EXISTS_EMPTY → [alembic upgrade heads] → MIGRATED
EXISTS_MIGRATED → [startup, no pending] → READY
EXISTS_MIGRATED → [startup, pending] → [auto-migrate or strict-verify] → READY or ERROR
EXISTS_AHEAD → [startup] → ERROR (refuse to start)
```

**Error states**:
- `ERROR_MIGRATION_FAILED`: Migration raised exception, server won't start
- `ERROR_SCHEMA_AHEAD`: DB revision > code revision, server won't start (prevent data loss)

---

## Entity 3: MigrationResult (Value Object)

| Attribute | Type | Description |
|-----------|------|-------------|
| `before_revision` | string \| `None` | Revision before migration ran |
| `after_revision` | string \| `None` | Revision after migration completed |
| `applied_count` | int | Number of migrations applied this run |
| `success` | bool | Whether migration completed without error |
| `error` | string \| `None` | Error message if failed |

**Usage**: Returned by `MigrationService.upgrade()`. Used for logging and status reporting.

---

## Business Entities (Unchanged)

All existing ORM models remain untouched:
- `Corpus`, `CorpusFile` — training data sources
- `Dataset`, `ImportSource`, `Sample` — curated datasets
- `TrainingConfig` — training hyperparameter configs
- `CurationOperation` — dataset curation operations

These models are registered with `Base.metadata` in `anvil/db/models/__init__.py`, which Alembic uses for autogenerate detection via `migrations/env.py`'s `target_metadata = Base.metadata`.

---

## Non-Entity: ANVIL_DB_AUTO_MIGRATE Config

| Attribute | Value |
|-----------|-------|
| Env var | `ANVIL_DB_AUTO_MIGRATE` |
| Type | `bool` (parsed from string) |
| Default | `true` (auto-migrate on startup) |
| Effects | Controls startup behavior (see research.md Decision 2) |
| Scope | Config key in `anvil/config.py` `get_config()` dictionary |