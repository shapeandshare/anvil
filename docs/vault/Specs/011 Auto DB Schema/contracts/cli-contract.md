# CLI Contract: `anvil db` Subcommand Group

**Phase**: 1 — Design & Contracts
**Date**: 2026-06-18
**Feature**: [spec.md](../spec.md)

## Overview

The `anvil db` CLI subcommand group exposes Alembic migration management commands. All commands delegate to `MigrationService` methods.

## Entry Point

```toml
# pyproject.toml — already has [project.scripts]
anvil-db = "anvil.cli:db_main"
```

## Subcommand Reference

### `anvil db upgrade`

Apply all pending migrations to HEAD.

```
anvil db upgrade
```

**Exit codes**:
- `0`: Success, all migrations applied (or none pending)
- `1`: Migration failed (error logged to stderr)

**Output**:
```
All migrations applied. Database at revision: abc123def456 (HEAD)
```
or (if already at HEAD):
```
Database already at latest revision: abc123def456 (HEAD)
```

---

### `anvil db downgrade`

Roll back one or more migrations.

```
anvil db downgrade              # Roll back 1 migration (default: -1)
anvil db downgrade -n 3         # Roll back 3 migrations
anvil db downgrade abc123def    # Roll back to specific revision
```

**Exit codes**:
- `0`: Success, migration(s) rolled back
- `1`: Specified revision not found in history
- `1`: Already at base revision (nothing to downgrade)

**Output**:
```
Downgraded to revision: abc123def456
```

---

### `anvil db current`

Show the current Alembic revision.

```
anvil db current
```

**Exit codes**:
- `0`: Information displayed

**Output**:
```
abc123def456 (HEAD)
```
or (if no revisions applied):
```
<base>
```

---

### `anvil db history`

Show the full migration history chain.

```
anvil db history
```

**Exit codes**:
- `0`: History displayed

**Output**:
```
abc123def456 -> def789abc012 (HEAD) Add experiment tracking
789012abc345 -> abc123def456 Add model registry
<base> -> 789012abc345 Initial schema
```

---

### `anvil db revision`

Auto-generate a new migration from ORM model changes.

```
anvil db revision -m "add user preferences table"
```

**Required args**: `-m` / `--message` — migration description

**Exit codes**:
- `0`: Migration file created
- `1`: `-m` flag not provided

**Output**:
```
Generated migration: /path/to/migrations/versions/abc123def456_add_user_preferences_table.py
```

---

### `anvil db stamp`

Stamp the database at a specific revision without running migrations (used for bootstrapping).

```
anvil db stamp abc123def456
```

**Exit codes**:
- `0`: Database stamped
- `1`: Revision string required

**Output**:
```
Stamped database at revision: abc123def456
```

---

## Error Handling

All subcommands output errors to stderr (not stdout). Migrations that raise exceptions are fatal:
- Upgrade failure: roll back, log full traceback, exit 1
- Downgrade failure: log full traceback, exit 1
- Revision not found: print error, exit 1

## Makefile Wrappers (unchanged, but internally redirect)

The existing Make targets in `shared/database.mk` will remain as convenience wrappers:

```makefile
db-upgrade: ## Apply all pending migrations
    $(PYTHON) -c "from anvil.cli import db_main; db_main(['upgrade'])"

db-downgrade: ## Rollback
    $(PYTHON) -c "from anvil.cli import db_main; db_main(['downgrade'])"

db-current: ## Show current revision
    $(PYTHON) -c "from anvil.cli import db_main; db_main(['current'])"

db-history: ## Show history
    $(PYTHON) -c "from anvil.cli import db_main; db_main(['history'])"

db-revision: ## Create migration (usage: MESSAGE="desc")
    $(PYTHON) -c "from anvil.cli import db_main; db_main(['revision', '-m', '$(MESSAGE)'])"

db-stamp: ## Stamp at revision (usage: REVISION=<hash>)
    $(PYTHON) -c "from anvil.cli import db_main; db_main(['stamp', '$(REVISION)'])"
```