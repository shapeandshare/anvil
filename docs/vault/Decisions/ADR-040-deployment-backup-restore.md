---
title: 'ADR-040: Full-Deployment Backup & Restore'
type: decision
tags:
  - type/decision
  - domain/operations
  - domain/architecture
created: '2026-06-21'
updated: '2026-06-21'
source: agent
code-refs:
  - anvil/services/backup/
  - anvil/db/models/backup_operation.py
  - anvil/db/repositories/backup_operations.py
  - anvil/api/v1/backup.py
  - anvil/config.py
aliases: 'ADR-040: Full-Deployment Backup & Restore'
---
# ADR-040: Full-Deployment Backup & Restore

## Status

Accepted

## Context

anvil lacked any mechanism to create point-in-time snapshots of the
full deployment state — SQLite app database (`data/anvil-state.db`),
MLflow tracking data (`mlruns/`), and filesystem state (`data/models/`,
`data/datasets/`, `data/storage/`, `data/content/`). Operators had no
way to safely recover from data corruption, failed upgrades, or
environment migration. The feature needed to be zero-dependency (stdlib
only), operate on a single-host deployment, and provide strong safety
guarantees (Pit of Success, Constitution Article IX).

Key design constraints:
- **Zero new third-party deps** (Article I) — archiving via `tarfile`,
  checksums via `hashlib`, DB snapshot via `sqlite3.Connection.backup()`.
- **Async-first** (Article V) — blocking I/O via `asyncio.to_thread`.
- **Layered architecture** (Article VII) — Repository → Service → God
  Class (AnvilWorkbench) → Routes/CLI.
- **Session-scoped audit** (FR-031) — audit events emitted at the route
  layer, not inside the process-lifetime `BackupService` (research R11).
- **Pit of Success** (Article IX) — safety snapshot before restore,
  typed `RESTORE` confirmation, atomic swap, crash-safe journal,
  auto-rotation that never deletes safety snapshots.

## Decision

Implement a new `BackupService` (process-lifetime, on `app.state`) that
orchestrates the backup and restore pipeline:

### Architecture

```
API Routes (anvil/api/v1/backup.py) ── emit audit via session-bound wb.audit
  │
  ▼  (calls process-lifetime BackupService on app.state)
BackupService ───────── holds BackupLock, progress queues
  │
  ├── SnapshotPlanner ── 6 managed roots (data/ + mlruns/), excludes logs/.env
  ├── ArchiveWriter ──── tar.gz, WAL-safe sqlite3.backup(), per-file sha256
  ├── ArchiveReader ──── verify checksums, safe extract, path-traversal guard
  ├── RetentionPolicy ── quota/count/age rotation, never returns safety snapshots
  ├── RestoreEngine ──── extract→verify→journal→swap→rollback
  ├── RestoreJournal ─── crash-safe marker before swap, startup recovery
  └── BackupOperationRepository ── session-bound DB access
```

### Key Decisions (from research R1–R14)

| # | Topic | Decision |
|---|-------|----------|
| R1 | Consistent DB snapshot | `sqlite3.Connection.backup()` in a thread (WAL-safe) |
| R2 | Archive format | Atomic immutable `.tar.gz`, timestamped unique names |
| R3 | Integrity | `manifest.json` with per-file SHA-256; on-demand Verify |
| R4 | Schema compat | Compare Alembic head + version → OK/WARN/BLOCKED |
| R5 | Atomic restore | Extract→verify→journal→move-aside→swap, rollback on failure |
| R6 | Async | Blocking I/O via `asyncio.to_thread`; queue-backed SSE progress |
| R7 | Concurrency | Process-scoped `BackupLock` on `app.state`; 409 if busy |
| R8 | Quota/space | `backup_quota_bytes` (10 GiB default) + `disk_usage` pre-flight |
| R9 | Safety snapshot | Auto pre-restore snapshot, flagged, undeletable via normal flow |
| R10 | UI/SSE | Extend Operations page; `BackupSession` client mirrors `SSESession` |
| R11 | Audit logging | `AuditService.record()` at route/CLI layer (session-bound), not in service |
| R12 | Auto-rotation | `RetentionPolicy` deletes oldest non-safety; safety snapshots exempt |
| R13 | Crash-safe restore | `RestoreJournal` marker before swap; startup rollback recovery |
| R14 | Snapshot scope | Include data + `mlruns/`; exclude `logs/` and `.env` |

## Consequences

### Positive
- Operators can create consistent, immutable, verifiable full-deployment
  snapshots with a single click or CLI command.
- Restore is safe by default: auto safety snapshot, typed confirmation,
  atomic swap, crash journal, rollback on failure.
- Storage is self-maintaining via configurable auto-rotation.
- All operations are audited via the existing hash-chained audit trail.
- Zero new third-party Python dependencies.

### Negative
- The process-lifetime `BackupService` means the single-operation lock
  does not protect against concurrent CLI + web-server backup/restore
  on a multi-process deployment (documented limitation; single-host
  assumption).
- Archives are not encrypted at rest (filesystem permissions only);
  encryption is deferred to a future version per Q1 of the clarification
  session.

### Neutral
- Requires Alembic revision `003` for the new `backup_operations` table.
- `logs/` and `.env` are permanently excluded from backups (design
  decision, not configurable).

## See Also

- [[Decisions/README|Decisions]]
