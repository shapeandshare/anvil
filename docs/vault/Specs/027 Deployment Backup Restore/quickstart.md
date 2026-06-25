---
title: 'Quickstart: Deployment Backup and Restore'
type: spec
tags:
  - type/spec
  - domain/operations
status: draft
created: '2026-06-21'
updated: '2026-06-21'
---
## For Developers

### Layered flow
```
Routes (anvil/api/v1/backup.py)  /  CLI (anvil/services/backup/cli.py)
        │
        ▼
AnvilWorkbench.backup  (shared process-lifetime BackupService on app.state)
        │
        ├── BackupOperationRepository (anvil/db/repositories/backup_operations.py)  → DB only
        ├── ArchiveWriter / ArchiveReader (tar.gz + manifest + sha256)
        ├── SnapshotPlanner (managed roots + exclusions + space/quota pre-flight)
        ├── RestoreEngine (extract → verify → journal → atomic swap → rollback)
        ├── RestoreJournal (crash-recovery marker; read at startup)
        ├── RetentionPolicy (auto-rotation: oldest non-safety, never safety snapshots)
        └── BackupLock (single-op asyncio guard)

Audit (FR-031): emitted at the ROUTE/CLI layer via session-bound `workbench.audit`,
NOT inside the process-lifetime BackupService. create_backup returns rotated ids so
the route can audit each rotation deletion.
```

### Key conventions to follow
- **Async-first**: service/repo/routes are `async`; wrap blocking `tarfile`/`hashlib`/`shutil`/`sqlite3.backup()` in `await asyncio.to_thread(...)`.
- **One class per file**; new domain types live in `anvil/services/backup/`.
- **Enums over strings** (`BackupStatus`, `BackupOperationType`, `SchemaCompatibility`); convert `str → Enum` only at boundaries.
- **Pydantic `BaseModel`** for all value/result types and API schemas (`extra="forbid"` for requests, `extra="ignore"` for manifest reads).
- **Relative imports only** inside `anvil/`.
- **Bare `__init__.py`** (docstring only) for `anvil/services/backup/`.

### Wiring checklist
1. `anvil/db/models/backup_operation.py` (ORM) → import in `anvil/_resources/migrations/env.py`.
2. Alembic revision `003_add_backup_operations.py` (`down_revision="002"`).
3. `anvil/db/repositories/backup_operations.py`.
4. Extend governance enums: add 4 members to `audit_action.py`, 1 to `audit_target_type.py`.
5. `anvil/services/backup/*` (service + helpers + types + retention + journal + cli).
6. `AnvilWorkbench`: add `_backup_repo` / use shared `app.state.backup_service`; add `backup_repo` and `backup` accessors (`audit` accessor already exists).
7. App lifespan (`anvil/api/app.py`): instantiate one `BackupService` on `app.state` (process lifetime, holds the lock) **and run restore-journal recovery (FR-030) at startup**.
8. `anvil/api/v1/backup.py` + include in `router.py`; routes emit audit via `workbench.audit`.
9. `pyproject.toml`: `anvil-backup = "anvil.services.backup.cli:main"`.
10. `anvil/config.py`: backup config keys (incl. retention).
11. UI: extend `operations.html` + add `static/js/backup.js`.

---

## Validation (TDD — write tests first)

### Unit (`tests/unit/services/backup/`, `tests/unit/db/`)
```bash
make test
```
- `test_archive_writer.py` — archive produced, manifest correct, atomic temp→final, unique names.
- `test_archive_reader.py` — verify detects tampering; rejects path-traversal; refuses higher `manifest_version`.
- `test_snapshot_planner.py` — collects all managed roots; **excludes `logs/` and `.env`**; space/quota pre-flight math.
- `test_restore_engine.py` — temp→verify→journal→swap; **rollback leaves original intact on injected failure** (SC-006); WAL DB round-trips.
- `test_restore_journal.py` — journal written before swap, cleared on success; **startup recovery rolls back from `.bak` / points to safety snapshot** (FR-030).
- `test_retention_policy.py` — auto-rotation selects oldest non-safety; **never returns a safety-snapshot id**; respects max count/age (FR-032).
- `test_backup_manifest.py` — schema compatibility OK/WARN/BLOCKED mapping.
- `test_backup_service.py` — single-op lock (409 path); pre-restore safety snapshot always created; safety snapshot not deletable; last-backup delete guard; `create_backup` returns `rotated_backup_ids`.
- `test_cli.py` — arg parsing + exit-code mapping; audit emitted in `_run()`.
- `test_backup_operations_repo.py` — CRUD mirrors repository conventions.

> Audit assertions (FR-031): e2e tests assert an `audit_event` row exists with the expected action/target/outcome after create/restore/delete; rotation tests assert one `backup_delete` audit per rotated id.

### e2e HTTP (`tests/e2e/test_backup_endpoints.py`)
Uses the `client` fixture (in-memory SQLite). Covers the full contract matrix in `contracts/api-v1-backup.md` — create/list/status/preview/restore/verify/delete + SSE progress.

### Manual smoke
```bash
make run
anvil-backup create
# add a dataset via UI, then:
anvil-backup restore <id>     # confirm the dataset change is reverted
```

### Merge gates (Constitution)
```bash
make lint && make typecheck && make test && make vault-audit
```
All must pass. Coverage may only ratchet up.

---

## Success Criteria Mapping
| SC | Validated by |
|---|---|
| SC-001 (≤2 clicks backup) | UI: Create Backup + confirm; e2e create 202 |
| SC-002 (<30s for 100MB+500MB) | perf assertion in service test / manual |
| SC-003 (≤5-click restore) | wizard step count; e2e restore flow |
| SC-004 (<1s list/status) | status/list query indexed on `backup_id`; e2e timing |
| SC-005 (100% restore fidelity) | restore_engine post-swap checksum equality test |
| SC-006 (failed restore = no data loss) | restore_engine injected-failure rollback test |
| SC-007 (UI + CLI parity) | both call `BackupService.create_backup`; CLI contract tests |
