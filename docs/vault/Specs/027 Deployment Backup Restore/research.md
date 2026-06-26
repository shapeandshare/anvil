---
title: 'Research: Deployment Backup and Restore'
type: spec
tags:
  - type/spec
  - domain/operations
status: draft
created: '2026-06-21'
updated: '2026-06-21'
---

Back to [[Specs/027 Deployment Backup Restore/spec]].

## R2 — Archive format & immutability

**Decision**: Each backup is a single **`.tar.gz`** file named `backup-<UTC-timestamp>-<shortid>.tar.gz` (e.g. `backup-20260621T143000Z-a1b2c3.tar.gz`), written atomically (temp file in `data/backups/.tmp/` → `os.replace` into place). Files are never modified after creation.

**Rationale**:
- `tarfile` (stdlib) handles arbitrary directory trees, preserves structure, and streams — no third-party dep (Article I).
- gzip compression keeps archives small; acceptable CPU cost given backups are infrequent and run in a thread.
- Timestamp-based unique names satisfy FR-022 (immutable, no overwrite). Two rapid "Create Backup" clicks produce two distinct files.
- Atomic write (temp-then-replace) means a crashed/partial backup never appears as a valid backup; the `.tmp/` dir is swept on startup and on failure (FR-013).

**Alternatives considered**:
- *`.zip`*: viable, but `tar.gz` is the more natural Unix deployment-archive format and streams better for large trees. Either satisfies the spec; tar.gz chosen.
- *Uncompressed tar*: larger archives, faster CPU. Rejected — storage quota (FR-027) makes compression worthwhile.
- *Directory-per-backup (no single file)*: harder to guarantee atomicity/immutability and to compute one archive checksum. Rejected.

---

## R3 — Manifest & integrity verification

**Decision**: Embed a `manifest.json` at the archive root. It records: schema version (this manifest format), backup id, UTC timestamp, anvil deployment version (`anvil.__version__`), DB schema/Alembic head revision, operation type (manual vs pre-restore-safety), total uncompressed size, and a list of `{path, sha256, size}` for every file in the archive. The manifest itself is covered by a top-level `manifest_sha256` stored in the `backup_operations` DB row and recomputable on demand.

**Rationale**:
- Per-file SHA-256 enables the on-demand **Verify** action (FR-025): re-extract/stream each entry, recompute, compare. Mismatch ⇒ mark `corrupted` (FR-026).
- Storing the deployment version + Alembic head enables the **schema compatibility check** (FR-023, see R4).
- `hashlib.sha256` is stdlib (Article I).

**Alternatives considered**:
- *Single archive-level checksum only*: cheaper but can't localize corruption or verify individual restored files during atomic swap. Rejected — per-file checksums are needed for FR-024's post-extract verification.
- *CRC32 (tar built-in)*: too weak for integrity guarantees. Rejected.

---

## R4 — Schema-version compatibility on restore

**Decision**: Compare the backup manifest's stored Alembic head revision and `anvil.__version__` against the running deployment. Map to a `SchemaCompatibility` enum: `OK` (same Alembic head), `WARN` (same head, different anvil patch/minor version → allowed with warning), `BLOCKED` (different Alembic head → restore blocked with upgrade guidance).

**Rationale**:
- Restoring a DB snapshot whose schema head differs from the running app's expected head risks ORM/migration mismatch. Blocking is the safe default (Pit of Success, Article IX).
- The Alembic head is the authoritative schema identity; anvil version is informational/secondary.
- anvil already exposes `MigrationService` and bundles migrations under `anvil/_resources/migrations/versions/`; the current head is readable at runtime.

**Alternatives considered**:
- *Always allow restore, warn only*: risks silent corruption. Rejected.
- *Attempt auto-migration of restored DB*: out of scope for v1 and risky; the manifest records enough to add this later. Deferred.

---

## R5 — Atomic restore (no partial overwrite)

**Decision**: Restore is **temp-then-swap**: (1) extract the archive into a sibling temp dir under `data/backups/.restore-tmp/`; (2) verify every extracted file's SHA-256 against the manifest; (3) for each managed root (`data/anvil-state.db*`, `data/models/`, `data/datasets/`, `data/storage/`, `data/content/`, `mlruns/`), move the current live version aside to a `.bak` suffix, then `os.replace`/move the restored version into place; (4) on full success delete the `.bak` sides; (5) on ANY failure during the swap, roll back by restoring the `.bak` sides. Non-essential services (MLflow sidecar) are paused for the swap window.

**Rationale**:
- Guarantees FR-014/FR-024/SC-006: the live deployment is never left half-overwritten. Verification happens *before* any live file is touched.
- The mandatory pre-restore safety snapshot (FR-018) is the outer safety net: even if the swap-level rollback fails catastrophically, the operator has a complete pre-restore backup whose id is surfaced in the UI/CLI.
- `os.replace` is atomic within a filesystem; directory swaps use move-aside + move-in.

**Alternatives considered**:
- *In-place extraction over live files*: a crash mid-extract corrupts the deployment. Rejected outright.
- *Symlink-swap of whole `data/` root*: cleaner atomicity but anvil's running process holds open file handles (SQLite); requires full process restart. The per-root move approach plus a "restart recommended" prompt (US2 scenario 5) is the pragmatic choice; full restart is recommended after restore anyway.

---

## R6 — Async discipline for blocking I/O

**Decision**: All archive/hash/copy/extract operations are synchronous stdlib calls wrapped in `await asyncio.to_thread(...)`. The `BackupService` methods are `async` and `await` these thread offloads. Progress is reported by passing a callback into the worker that pushes `ProgressEvent`s onto an `asyncio.Queue` (thread-safe handoff via `loop.call_soon_threadsafe`).

**Rationale**:
- Constitution Article V mandates async-first for service/web/DB layers; long blocking I/O on the event loop would freeze SSE heartbeats and the whole server.
- Mirrors how anvil's training already streams progress over a queue-backed SSE endpoint (`anvil/api/v1/training.py`).

**Alternatives considered**:
- *Run backup in a subprocess*: heavier, complicates progress reporting and the in-process single-operation lock. Rejected for v1.
- *Pure-async file I/O (`aiofiles`) for archiving*: `tarfile`/`hashlib` are CPU+IO bound and not async-native; thread offload is the correct tool. Rejected.

---

## R7 — Single-operation concurrency control

**Decision**: An in-process `BackupLock` (an `asyncio.Lock` plus a "current operation" descriptor) guards backup and restore. Acquiring is non-blocking from the API perspective: if busy, the route returns HTTP 409 with the in-flight operation's id/type. The lock lives on the long-lived `BackupService` instance (process-scoped), not per-request session.

**Rationale**:
- FR-012 requires only one backup/restore at a time. A single-host, single-process deployment makes an in-process lock sufficient.
- Returning 409 (rather than queueing) keeps the UX honest — the operator sees "a backup is already running."

**Alternatives considered**:
- *DB-row advisory lock*: overkill for single-process; adds DB round-trips. Rejected.
- *OS file lock*: needed only for multi-process; out of scope (single-host assumption). Deferred.

**Note on service lifetime**: most `AnvilWorkbench` services are session-scoped (created per request). The `BackupService` needs *process* lifetime for the lock and the in-flight progress queue. Decision: instantiate one `BackupService` on `app.state` at startup (lifespan) and have the `AnvilWorkbench.backup` accessor return that shared instance, passing a per-request `BackupOperationRepository` for DB writes. This matches how `app.state.mlflow` (the MLflow sidecar manager) is already a process-lifetime object on `app.state`.

---

## R8 — Storage quota enforcement & pre-flight space check

**Decision**: Config key `backup_quota_bytes` (default 10 GiB, env `ANVIL_BACKUP_QUOTA_BYTES`). Before creating a backup: (a) estimate required space (sum of source sizes, conservatively un-compressed, for the temp write) and check `shutil.disk_usage()` free space; (b) check that existing-backups total + estimated new size ≤ quota. Block with a clear, actionable message if either fails (FR-015, FR-027). For restore, the pre-flight verifies room for BOTH the pre-restore safety snapshot AND the extracted data.

**Rationale**:
- Pit of Success (Article IX): never crash with a disk-full error mid-backup; refuse up front with guidance.
- `shutil.disk_usage` is stdlib.

**Alternatives considered**:
- *Compress-then-check*: can't know compressed size in advance; conservative uncompressed estimate is the safe bound. Accepted.

---

## R9 — Pre-restore safety snapshot semantics

**Decision**: Before any restore, `BackupService` creates a normal backup tagged `operation_type = PRE_RESTORE_SAFETY`. It appears in listings but is flagged distinctly (FR-019) and is excluded from the standard delete flow (FR-020) — it has a separate, explicitly-labeled cleanup action. Its id is returned to the operator on restore completion (US2 scenario 5) so they can undo.

**Rationale**: Directly implements the core Pit-of-Success addition from the spec review — the wrong action (irreversible overwrite) becomes reversible by default.

---

## R10 — UI integration & SSE client

**Decision**: Extend `operations.html` with a new `.section-card` (status card with `meter` quota gauge + grouped-list of backups + actions bar) and a restore wizard built from the existing `wizard-steps`/`wizard-panel` archetype inside a `modal-dialog`. Add `anvil/api/static/js/backup.js` with a `BackupSession` SSE client modeled on the existing `SSESession` (`anvil/api/static/js/sse.js`), pointed at `GET /v1/backup/stream/{id}`.

**Rationale**: Reuses the design system and SSE client verbatim (Constitution Article VIII, UX rules). No new components, no new raw style values.

**Alternatives considered**:
- *Separate `/v1/backup-page`*: the spec explicitly says add to the existing Operations page. Rejected.

---

## R11 — Audit logging integration (FR-031, clarification Q3)

**Decision**: Emit audit entries for backup create, restore, delete, and safety-snapshot cleanup using the **existing** `AuditService.record()` (the hash-chained `audit_event` infrastructure from the governance domain). Add new enum members — `BACKUP_CREATE`, `BACKUP_RESTORE`, `BACKUP_DELETE`, `SAFETY_SNAPSHOT_CLEANUP` to `AuditAction`, and `BACKUP` to `AuditTargetType`. **Audit emission happens at the route/CLI layer** (which holds a session-bound `workbench.audit`), NOT inside `BackupService`.

**Rationale**:
- `AuditService` is **session-scoped** and its writes participate in the caller's transaction; audit-write failure *propagates* (by design — governance FR-011). `BackupService`, however, is **process-lifetime** (research R7) and holds no request session. Emitting from inside `BackupService` would cross the session boundary incorrectly.
- The route handler / CLI command already has a per-request `AsyncSession` and `workbench.audit`. After `BackupService` reports success/failure, the route records the audit event within its own transaction — clean layering (Constitution Article VII).
- Reuses existing infra verbatim; no new audit subsystem (spec Assumption).
- Auto-rotation deletions (R12) are also audited — the rotation runs inside `create_backup`, so the service returns the list of rotated backup ids and the route emits one `BACKUP_DELETE` audit entry per rotated id.

**Alternatives considered**:
- *Inject `AuditService` into `BackupService`*: breaks the process-vs-session lifetime boundary; the audit service's session would be stale across operations. Rejected.
- *New backup-specific audit table*: duplicates governance infra; rejected per spec Assumption.

---

## R12 — Storage quota auto-rotation & retention (FR-027, FR-032, clarification Q4)

**Decision**: When a new backup would exceed `backup_quota_bytes`, `BackupService` auto-rotates: it deletes the **oldest non-safety** backups (ordered by `created_at`) until the projected total fits, governed by a `RetentionPolicy` (configurable `backup_retention_max_count` via `ANVIL_BACKUP_RETENTION_MAX_COUNT`, and `backup_retention_max_age_days` via `ANVIL_BACKUP_RETENTION_MAX_AGE_DAYS`; either may be unset). Pre-restore safety snapshots are **never** auto-deleted. If, after rotating all eligible non-safety backups, space is still insufficient, creation is blocked (507/exit 4). Each auto-deletion is audited (R11).

**Rationale**:
- Pit of Success: a full quota must not silently block the mandatory pre-restore safety snapshot at restore time. Rotation keeps the system self-maintaining.
- Safety-snapshot exemption preserves the undo guarantee even under storage pressure.
- Retention is a pure policy object (testable in isolation) consumed by `create_backup`.

**Alternatives considered**:
- *Hard block only (no rotation)*: simpler but pushes retention burden entirely onto the operator and risks blocking restores. Superseded by clarification Q4.
- *Rotate by age only / count only*: less flexible; combined count+age covers more operator policies.

---

## R13 — Crash-safe restore via journal (FR-030, clarification Q2)

**Decision**: `RestoreEngine` writes a `RestoreJournal` marker file (e.g. `data/backups/.restore-journal.json`) **before** the file-swap phase, recording: the restore operation id, the source backup id, the pre-restore safety snapshot id, and the list of managed roots about to be swapped (with their `.bak` move-aside paths). The swap proceeds per-root (move live → `.bak`, move restored → live). On clean, fully-verified completion the journal and `.bak` sides are removed. On any in-process failure, the engine rolls back from `.bak`. **On application startup** (`app.py` lifespan), if a journal exists, the system detects an interrupted restore and: (a) rolls back from the `.bak` copies if present, or (b) if `.bak` copies are missing/incomplete, surfaces a clear recovery state referencing the safety-snapshot id and leaves the journal for operator action.

**Rationale**:
- Closes the power-loss/`kill -9` gap that plain try/except rollback cannot cover (the process is gone).
- The journal + safety snapshot together guarantee SC-006 ("failed restore never loses data") even across a hard crash.
- Startup recovery is a small, deterministic step in the existing lifespan handler (where DB init + Alembic migrate already run).

**Alternatives considered**:
- *Best-effort `.tmp` sweep only*: cannot detect a half-applied swap → silent corruption risk. Rejected (clarification Q2 chose the journal).
- *Single whole-tree directory rename*: strongest atomicity but requires full process stop + open-SQLite-handle juggling; deferred (research R5 alternatives).

---

## R14 — Snapshot scope: inclusions & exclusions (FR-001, clarification Q5)

**Decision**: A backup includes exactly: `data/anvil-state.db`, `data/models/`, `data/datasets/`, `data/storage/`, `data/content/`, and `mlruns/` (incl. `mlruns/mlflow.db`). It **excludes** `logs/` (diagnostic, not reconstruction state) and `.env`/environment config (environment-specific settings + secrets that must not cross environments on restore). `SnapshotPlanner` hard-codes this managed-root set and exclusion list.

**Rationale**:
- Restoring `.env` could overwrite the target host's ports/paths and leak secrets across environments; logs bloat archives without aiding state reconstruction.
- Matches the existing data-model archive layout (logs/`.env` were never listed) — this decision makes the exclusion explicit and testable.

**Alternatives considered**:
- *Include `logs/`*: forensic completeness vs. archive bloat + overwrite of target logs. Rejected (Q5=A).
- *Include `.env`*: full reproducibility vs. cross-environment secret/config hazard. Rejected (Q5=A).

---

## Summary of Decisions

| # | Topic | Decision |
|---|---|---|
| R1 | Consistent DB snapshot | `sqlite3.Connection.backup()` in a thread (WAL-safe) |
| R2 | Archive format | Atomic immutable `.tar.gz`, timestamped unique names |
| R3 | Integrity | `manifest.json` with per-file SHA-256; on-demand Verify |
| R4 | Schema compat | Compare Alembic head + version → OK/WARN/BLOCKED |
| R5 | Atomic restore | Extract→verify→move-aside→swap, rollback on failure |
| R6 | Async | Blocking I/O via `asyncio.to_thread`; queue-backed progress |
| R7 | Concurrency | Process-scoped `BackupLock` on `app.state`; 409 if busy |
| R8 | Quota/space | `backup_quota_bytes` (10 GiB default) + `disk_usage` pre-flight |
| R9 | Safety snapshot | Auto pre-restore snapshot, flagged, undeletable via normal flow |
| R10 | UI/SSE | Extend Operations page; `BackupSession` client mirrors `SSESession` |
| R11 | Audit logging | Reuse `AuditService.record()`; emit at route/CLI layer (session-bound), not in process-lifetime service; add 4 `AuditAction` + 1 `AuditTargetType` members |
| R12 | Quota auto-rotation | `RetentionPolicy` (max count/age) deletes oldest non-safety backups; safety snapshots exempt; block only if still over after rotation |
| R13 | Crash-safe restore | `RestoreJournal` marker before swap; startup detects interrupted restore → roll back from `.bak` or point to safety snapshot |
| R14 | Snapshot scope | Include data + `mlruns/`; exclude `logs/` and `.env` |

**All decisions use stdlib only — zero new third-party dependencies.** No ADR-worthy dependency additions; an ADR documenting the backup architecture decision will be recorded during implementation per Constitution governance.
