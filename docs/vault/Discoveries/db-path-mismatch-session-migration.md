---
aliases:
  - DB Path Mismatch Between session.py and MigrationService
code-refs:
  - anvil/db/session.py
  - anvil/db/migration.py
  - anvil/config.py
created: '2026-06-18'
related:
  - '[[Sessions/2026-06-18-db-path-mismatch]]'
session: 2026-06-18-db-path-mismatch
source: agent
summary: >-
  session.py used ANVIL_DB_PATH defaulting to data/anvil.db while
  MigrationService used ANVIL_STATE_DB_PATH defaulting to data/anvil-state.db —
  causing all DB queries to fail with 'no such table' after the env var rename
  was applied inconsistently.
tags:
  - type/discovery
  - domain/database
  - status/draft
title: DB Path Mismatch Between session.py and MigrationService
type: discovery
updated: '2026-06-18'
---
`session.py` and `MigrationService` disagreed on which SQLite file to connect to. The runtime engine in `anvil/db/session.py` read from the legacy `ANVIL_DB_PATH` env var (default: `data/anvil.db`), while `MigrationService` read from the canonical `ANVIL_STATE_DB_PATH` in `config.py` (default: `data/anvil-state.db`). The two files diverged — migrations were applied only to `anvil-state.db`, so `anvil.db` had zero tables and every query returned "no such table" → HTTP 500.

## Root Cause

The `ANVIL_DB_PATH → ANVIL_STATE_DB_PATH` rename was completed in `config.py` and `migration.py` but missed in `session.py`. Because `get_config()` uses `@lru_cache` and `session.py` imported it at module level with its own fallback to `os.getenv("ANVIL_DB_PATH", "data/anvil.db")`, the code silently used a different database file than where migrations were applied. No startup error was raised because both files existed — the stale `data/anvil.db` was created by an earlier version of the code before the env var rename.

## Fix

Replaced the direct `os.getenv` + fallback in `session.py` with `cfg["state_db_path"]` from `config.py`, which handles the deprecation path (`ANVIL_DB_PATH → ANVIL_STATE_DB_PATH`) centrally:

```
# Before (broken):
DB_PATH = os.getenv("ANVIL_DB_PATH", str(Path("data/anvil.db").resolve()))

# After (fixed):
cfg = get_config()
DB_PATH = cfg["state_db_path"]
```

All three components now agree on the same path: `session.py`, `config.py`, and `migration.py` all resolve to `cfg["state_db_path"]` → `data/anvil-state.db`.

## Implications

- The stale `data/anvil.db` file remains on disk. It contains no tables and is no longer referenced by any code.
- Any environment that set `ANVIL_DB_PATH` but not `ANVIL_STATE_DB_PATH` still works — `config.py`'s deprecation path maps `ANVIL_DB_PATH` into `state_db_path`. But since `session.py` now uses `cfg["state_db_path"]` instead of reading the env var directly, both variables work correctly.
- The `config.py` deprecation warning remains the single source of truth for migration guidance.

## References
- [[Discoveries/Discoveries|Discoveries]]

- `anvil/db/session.py` — the file where the stale default lived
- `anvil/db/migration.py` — `MigrationService.__init__` already used `cfg["state_db_path"]`
- `anvil/config.py` — `get_config()` at lines 70-80 handles the deprecation path
