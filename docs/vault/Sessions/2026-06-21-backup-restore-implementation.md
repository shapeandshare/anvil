---
title: Deployment Backup & Restore — Full Implementation
type: session-log
tags:
  - type/session-log
  - domain/operations
created: '2026-06-21'
updated: '2026-06-21'
status: draft
aliases: Deployment Backup & Restore — Full Implementation
source: agent
---
# Deployment Backup & Restore — Full Implementation

**Session**: Implemented the complete backup & restore feature for the
anvil deployment (feature 026-deployment-backup-restore). See
[[Decisions/ADR-040-deployment-backup-restore|ADR-040]] for the full
architecture decision record.

## What was done

### Phase 1-2: Foundation (T001-T026)
- Added 5 backup config keys to `anvil/config.py`
- Created `anvil/services/backup/` domain sub-package (18 files)
- Implemented 3 domain enums (`BackupStatus`, `BackupOperationType`,
  `SchemaCompatibility`)
- Extended `AuditAction` (+4 members) and `AuditTargetType` (+1 member)
  for backup audit events
- Created 8 Pydantic value types (`BackupManifest`, `ManifestEntry`,
  `BackupSummary`, `BackupStorageStatus`, `RestorePreview`,
  `VerifyResult`, `ProgressEvent`, `CreateBackupResult`)
- Created `BackupOperation` ORM model + Alembic revision `003`
- Implemented `BackupOperationRepository` with session-bound CRUD
- Built `BackupLock` (process-scoped single-op guard)
- Wired `BackupService` into `app.state` at startup + workbench accessor

### Phase 3: One-Click Backup — US1 (T027-T039)
- `SnapshotPlanner` — 6 managed roots, excludes `logs/`/`.env`
- `RetentionPolicy` — quota/count/age auto-rotation, safety-snapshot exempt
- `ArchiveWriter` — WAL-safe DB via `sqlite3.Connection.backup()`, tar.gz,
  per-file SHA-256 manifest, atomic write
- `BackupService.create_backup` — lock→plan→rotate→archive→complete
- API routes: `POST /v1/backup`, `GET /v1/backup`, `GET /v1/backup/{id}`
  with route-layer audit emission
- `anvil-backup` CLI with create/list/show/status subcommands

### Phase 4-7: Restore, Verify, Delete — US2/US4/US6 (T040-T072)
- `ArchiveReader` — checksum verification, safe extract, path-traversal guard
- `RestoreJournal` — crash-safe marker file before swap, startup recovery
- `RestoreEngine` — extract→verify→journal→swap→rollback
- `check_schema_compatibility` — OK/WARN/BLOCKED mapping
- `BackupService.restore` — typed `RESTORE` confirm, auto safety snapshot,
  engine pipeline
- `BackupService.verify` — full checksum verification, marks corrupted
- `BackupService.delete_backup` — last-backup guard, safety-snapshot refusal
- `BackupService.storage_status` — aggregate stats for Operations page
- API routes: `POST /v1/backup/{id}/verify`, `POST /v1/backup/{id}/restore`,
  `DELETE /v1/backup/{id}`, `GET /v1/backup/status`
- SSE stream: `GET /v1/backup/stream/{id}`

### Tests (35 passing)
- `test_snapshot_planner.py` — 4 tests (roots, exclusions, plan structure)
- `test_retention_policy.py` — 8 tests (quota, count, age, safety exemption)
- `test_archive_writer.py` — 4 tests (manifest, entries, atomicity, uniqueness)
- `test_backup_service.py` — 5 tests (create, lock, failure, list, rotation)
- `test_backup_operations_repo.py` — 5 tests (CRUD, restorable filter)
- `test_cli.py` — 9 tests (parser structure, exit codes)

## Key files

- **Services**: `anvil/services/backup/` (18 files)
- **Model**: `anvil/db/models/backup_operation.py`
- **Repository**: `anvil/db/repositories/backup_operations.py`
- **Migration**: `anvil/_resources/migrations/versions/003_add_backup_operations.py`
- **Routes**: `anvil/api/v1/backup.py`
- **CLI**: `anvil/services/backup/cli.py`
- **Tests**: `tests/unit/services/backup/` (5 files),
  `tests/unit/db/test_backup_operations_repo.py`
- **Wiring edits**: `anvil/config.py`, `anvil/workbench.py`,
  `anvil/api/app.py`, `anvil/api/v1/router.py`,
  `anvil/_resources/migrations/env.py`, `pyproject.toml`