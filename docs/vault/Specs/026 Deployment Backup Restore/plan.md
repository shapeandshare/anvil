# Implementation Plan: Deployment Backup & Restore

**Branch**: `026-deployment-backup-restore` | **Date**: 2026-06-21 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/docs/vault/Specs/026 Deployment Backup Restore/spec.md`

## Summary

Add full-deployment backup & restore to anvil: a consistent point-in-time snapshot of the SQLite app database **and** all persistent on-disk state (models, datasets, storage, content, MLflow DB + artifacts), packaged as a single immutable compressed archive with a checksummed manifest. The snapshot deliberately **excludes** `logs/` and `.env`/environment config. Operators trigger backups one-click from the Operations page (or `anvil-backup` CLI) and restore through a guided multi-step wizard that *always* auto-creates a pre-restore safety snapshot, requires a typed `RESTORE` confirmation, validates schema compatibility, and applies the restore **atomically** (temp → verify → journal → swap, with crash-safe rollback on next startup). Storage is bounded by a configurable quota with **auto-rotation** of the oldest non-safety backups. Every create/restore/delete/cleanup emits an **audit-log entry** via the existing `audit_event` infrastructure. Progress streams live over SSE. The feature plugs into the existing layered architecture (Repository → Service → `AnvilWorkbench` god class → Routes/CLI) and reuses existing design-system components, wizard CSS, and SSE client.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: FastAPI, async SQLAlchemy + aiosqlite, Jinja2, MLflow (sidecar). Backup archiving uses **stdlib only** (`tarfile`, `hashlib`, `shutil`, `tempfile`, `sqlite3`) — no new third-party deps.
**Storage**: SQLite (app DB at `data/anvil-state.db` in WAL mode; MLflow DB at `mlruns/mlflow.db`). Persistent state under `data/` and `mlruns/`. Backup archives at `data/backups/` (new, configurable via `ANVIL_BACKUP_DIR`).
**Testing**: pytest (unit in `tests/unit/`, e2e HTTP in `tests/e2e/` via the `client` fixture).
**Target Platform**: macOS / Linux single-host deployment.
**Project Type**: Web application (FastAPI server + Jinja2/SSE UI) with a CLI.
**Performance Goals**: Full backup of 100MB DB + 500MB files < 30s on local storage (SC-002). Backup list/status loads < 1s regardless of count (SC-004).
**Constraints**: Backups immutable & write-once; restore atomic with crash-safe recovery (FR-030); failed restore never loses data (SC-006); single backup/restore at a time (in-process lock); archives unencrypted at rest (filesystem-protected, FR per clarification Q1).
**Scale/Scope**: Single-host deployments; archive sizes up to multiple GB; default 10GB backup-storage quota with auto-rotation.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Article | Compliance |
|---|---|
| **I — Zero-Dependency Core** | ✅ No changes to `anvil/core/`. Backup is an opt-in layer using stdlib archiving only — zero new third-party deps. |
| **IV — TDD Mandatory** | ✅ Tests written first. Unit tests for service/manifest/checksum/atomic-swap/rotation/journal-recovery; e2e HTTP tests for all routes. Coverage ratchet honored. |
| **V — Async-First** | ✅ Service, repository, routes are `async`. Blocking archive I/O (`tarfile`, `hashlib`, `sqlite3.backup()`) runs via `asyncio.to_thread`. |
| **VI — `__init__.py` Ownership** | ✅ New `anvil/services/backup/` domain sub-package gets a bare docstring-only `__init__.py`. No re-exports. Relative imports only. |
| **VII — Layered Architecture** | ✅ `BackupOperationRepository` (DB only) → `BackupService` (logic) → `AnvilWorkbench` (accessor) → Routes/CLI. Audit emission happens at the session-bound route/CLI layer via `workbench.audit` (see research R11). |
| **VIII — iOS-Grade Polish** | ✅ Reuses existing design tokens, `section-card`, `wizard-steps`, `modal-dialog`, `meter`, `badge`, `toast`. UX rules (S4/S3) apply. |
| **IX — Pit of Success** | ✅ Auto pre-restore snapshot, typed confirmation, atomic swap + crash-safe journal recovery, integrity verification, quota auto-rotation (never deletes safety snapshots), last-backup deletion warning. |
| **X — Domain-Driven Decomposition** | ✅ Backup is one bounded context → `anvil/services/backup/`. Status/type/compat enums + result/value types co-locate there. New audit enum members extend the existing `governance` domain. Max 2 nesting levels. |
| **Additional — Migrations** | ✅ New `backup_operations` table via reversible Alembic revision `003`. |
| **Additional — mypy strict** | ✅ Full type annotations, no suppressions. |
| **Additional — Pydantic over dataclass** | ✅ All new structured/value types and API schemas use `BaseModel`. |
| **Additional — One class per file** | ✅ Each service/repo/model/enum/value type in its own file. |

**Result**: PASS. No violations. Complexity Tracking empty.

## Project Structure

### Documentation (this feature)

```text
docs/vault/Specs/026 Deployment Backup Restore/
├── plan.md              # This file
├── research.md          # Phase 0 output (R1–R13)
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (api-v1-backup.md, cli-backup.md, backup-archive.md)
├── checklists/requirements.md
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (repository root)

```text
anvil/
├── config.py                                  # + backup_dir, backup_quota_bytes, retention keys (edit)
├── workbench.py                               # + backup_repo / backup accessors (edit)
├── _resources/migrations/                      # (top-level package resources, NOT under db/)
│   ├── env.py                                  # + import backup_operation model (edit)
│   └── versions/
│       └── 003_add_backup_operations.py        # NEW — Alembic revision (down_revision="002")
├── db/
│   ├── models/
│   │   └── backup_operation.py                # NEW — BackupOperation ORM model
│   └── repositories/
│       └── backup_operations.py               # NEW — BackupOperationRepository
├── services/
│   ├── governance/                             # EXISTING audit domain — extend enums
│   │   ├── audit_action.py                     # + BACKUP_CREATE/RESTORE/DELETE/SAFETY_SNAPSHOT_CLEANUP (edit)
│   │   └── audit_target_type.py                # + BACKUP (edit)
│   └── backup/                                 # NEW domain sub-package
│       ├── __init__.py                         # bare docstring
│       ├── backup_service.py                   # BackupService (orchestration, process-lifetime, lock)
│       ├── archive_writer.py                   # ArchiveWriter (tar + manifest + checksums)
│       ├── archive_reader.py                   # ArchiveReader (verify + safe extract)
│       ├── snapshot_planner.py                 # SnapshotPlanner (managed roots, exclusions, pre-flight)
│       ├── restore_engine.py                   # RestoreEngine (temp→verify→journal→swap, rollback)
│       ├── restore_journal.py                  # RestoreJournal (write/read/clear crash-recovery marker)
│       ├── retention_policy.py                 # RetentionPolicy (auto-rotation: max count/age)
│       ├── backup_manifest.py                  # BackupManifest (Pydantic, extra="ignore")
│       ├── manifest_entry.py                   # ManifestEntry (Pydantic)
│       ├── backup_summary.py                   # BackupSummary (Pydantic)
│       ├── backup_storage_status.py            # BackupStorageStatus (Pydantic)
│       ├── restore_preview.py                  # RestorePreview (Pydantic)
│       ├── verify_result.py                    # VerifyResult (Pydantic)
│       ├── progress_event.py                   # ProgressEvent (Pydantic, SSE payload)
│       ├── create_backup_result.py             # CreateBackupResult (Pydantic — backup_id + rotated ids)
│       ├── backup_status.py                    # BackupStatus (StrEnum)
│       ├── backup_operation_type.py            # BackupOperationType (StrEnum)
│       ├── schema_compatibility.py             # SchemaCompatibility (StrEnum)
│       ├── backup_lock.py                       # BackupLock (process-scoped single-op guard)
│       └── cli.py                              # anvil-backup CLI entry
├── api/
│   ├── v1/
│   │   ├── backup.py                           # NEW — routes (emit audit via workbench.audit)
│   │   └── router.py                           # + include backup_router (edit)
│   ├── app.py                                  # + app.state.backup_service + startup journal recovery (edit)
│   └── templates/operations.html               # + backup section-card + restore wizard + help (edit)
├── api/static/js/backup.js                     # NEW — backup ops + wizard + BackupSession (SSE)

pyproject.toml                                  # + anvil-backup script entry (edit)

tests/
├── unit/services/backup/                       # writer, reader, restore_engine, journal, planner,
│   └── ... (test_*.py)                          #   retention, manifest, backup_service, cli
├── unit/db/test_backup_operations_repo.py
└── e2e/test_backup_endpoints.py
```

**Structure Decision**: Single-project layered architecture (the established anvil pattern). Backup is a new bounded context (`anvil/services/backup/`) wired through `AnvilWorkbench` to a new `anvil/api/v1/backup.py` and an `anvil-backup` CLI. Audit emission reuses the existing `governance` domain's `AuditService` at the session-bound route/CLI layer. UI extends `operations.html`. No structural deviation from the constitution.

## Complexity Tracking

> No constitution violations — section intentionally empty.
