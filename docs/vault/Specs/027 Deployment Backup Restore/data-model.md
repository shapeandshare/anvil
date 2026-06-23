# Data Model: Deployment Backup & Restore

**Feature**: 026-deployment-backup-restore | **Date**: 2026-06-21 | **Phase**: 1

Derives the persisted entities, value types, and enums from the spec's Key Entities (spec §Key Entities) and Functional Requirements. Follows anvil conventions: ORM models inherit `Base, TimestampMixin`; value/result types are Pydantic `BaseModel`; fixed value sets are `StrEnum`; one class per file; types co-located in `anvil/services/backup/`.

---

## 1. Persisted Entity (DB)

### `BackupOperation` — ORM model

**File**: `anvil/db/models/backup_operation.py`
**Table**: `backup_operations`
**Maps spec entity**: *BackupOperation* (and the persisted index of *BackupArchive*).

| Column | Type | Constraints / Default | Notes |
|---|---|---|---|
| `id` | `int` | PK, autoincrement | |
| `backup_id` | `str` | `String(64)`, unique, indexed | Public id, e.g. `20260621T143000Z-a1b2c3` |
| `operation_type` | `str` | `String(20)`, default `BACKUP` | `BackupOperationType` value (`backup` / `restore` / `pre_restore_safety`) |
| `status` | `str` | `String(20)`, default `CREATING` | `BackupStatus` value |
| `archive_filename` | `str \| None` | `String(255)`, nullable | Filename within backup dir; null until archive written |
| `archive_size_bytes` | `int` | `Integer`, default `0` | Compressed archive size |
| `total_uncompressed_bytes` | `int` | `Integer`, default `0` | Sum of source file sizes |
| `manifest_sha256` | `str \| None` | `String(64)`, nullable | Top-level manifest checksum |
| `deployment_version` | `str \| None` | `String(50)`, nullable | `anvil.__version__` at creation |
| `schema_revision` | `str \| None` | `String(64)`, nullable | Alembic head at creation |
| `started_at` | `datetime \| None` | `DateTime`, nullable | Operation start |
| `completed_at` | `datetime \| None` | `DateTime`, nullable | Operation end (success or fail) |
| `error_message` | `str \| None` | `String(1000)`, nullable | Populated on failure |
| `restored_from_backup_id` | `str \| None` | `String(64)`, nullable | For `restore` rows: which backup was restored |
| `safety_snapshot_id` | `str \| None` | `String(64)`, nullable | For `restore` rows: the auto pre-restore snapshot's `backup_id` |
| `created_at` | `datetime` | from `TimestampMixin` | |
| `updated_at` | `datetime` | from `TimestampMixin` | |

**Relationships**: none (flat operations log). The archive file on disk is the source of truth for contents; this table is the queryable index + operation history.

**Validation rules** (enforced in service layer, not DB):
- `backup_id` is generated, never client-supplied.
- A row with `operation_type=pre_restore_safety` MUST NOT be deletable via the standard delete path (FR-020).
- `status` transitions are constrained (see state machine below).

---

## 2. State Machine — `BackupStatus`

```
                 ┌─────────────┐
   create  ───▶  │  CREATING   │
                 └──────┬──────┘
              success   │   failure
            ┌───────────┴───────────┐
            ▼                       ▼
      ┌───────────┐          ┌───────────┐
      │ COMPLETED │          │  FAILED   │
      └─────┬─────┘          └───────────┘
            │ verify finds mismatch
            ▼
      ┌───────────┐
      │ CORRUPTED │
      └───────────┘

   Restore operation rows use the same enum:
   CREATING (= in progress) ─▶ COMPLETED | FAILED
```

| From | Event | To |
|---|---|---|
| (none) | create initiated | `CREATING` |
| `CREATING` | archive written + manifest verified | `COMPLETED` |
| `CREATING` | any error / disk full / aborted | `FAILED` |
| `COMPLETED` | on-demand Verify finds checksum mismatch | `CORRUPTED` |
| `COMPLETED`/`CORRUPTED` | (terminal otherwise) | — |

`FAILED` rows have their partial archive cleaned up (FR-013). `CORRUPTED` archives are retained but flagged (FR-026); restore from them is allowed only with extra warnings (spec edge case).

---

## 3. Value & Result Types (Pydantic `BaseModel`)

### `BackupManifest`
**File**: `anvil/services/backup/backup_manifest.py` — serialized as `manifest.json` inside each archive.

| Field | Type | Notes |
|---|---|---|
| `manifest_version` | `int` | Manifest format version (start at `1`) |
| `backup_id` | `str` | |
| `created_at` | `datetime` | UTC |
| `operation_type` | `BackupOperationType` | |
| `deployment_version` | `str` | `anvil.__version__` |
| `schema_revision` | `str` | Alembic head |
| `total_uncompressed_bytes` | `int` | |
| `entries` | `list[ManifestEntry]` | Per-file checksums |

### `ManifestEntry`
**File**: `anvil/services/backup/manifest_entry.py`

| Field | Type | Notes |
|---|---|---|
| `path` | `str` | Path **relative to archive root** (e.g. `data/anvil-state.db`) |
| `sha256` | `str` | Hex digest |
| `size` | `int` | Bytes |

### `BackupSummary`
**File**: `anvil/services/backup/backup_summary.py` — list/UI/CLI projection of a `BackupOperation` (+ derived fields).

| Field | Type | Notes |
|---|---|---|
| `backup_id` | `str` | |
| `operation_type` | `BackupOperationType` | |
| `status` | `BackupStatus` | |
| `created_at` | `datetime` | |
| `archive_size_bytes` | `int` | |
| `deployment_version` | `str \| None` | |
| `schema_revision` | `str \| None` | |
| `age_seconds` | `int` | Derived: now − created_at |
| `is_safety_snapshot` | `bool` | Derived: `operation_type == PRE_RESTORE_SAFETY` |
| `deletable` | `bool` | Derived: not a safety snapshot |

### `BackupStorageStatus`
**File**: `anvil/services/backup/backup_storage_status.py` — powers the Operations status card (FR-011, FR-029).

| Field | Type | Notes |
|---|---|---|
| `backup_count` | `int` | |
| `total_bytes` | `int` | Sum of archive sizes |
| `quota_bytes` | `int` | Configured quota |
| `quota_used_fraction` | `float` | `total_bytes / quota_bytes`, clamped 0–1 |
| `over_threshold` | `bool` | `quota_used_fraction ≥ warn threshold` |
| `latest_backup_at` | `datetime \| None` | |
| `oldest_backup_at` | `datetime \| None` | |

### `RestorePreview`
**File**: `anvil/services/backup/restore_preview.py` — drives wizard step 1 (US2 scenario 1).

| Field | Type | Notes |
|---|---|---|
| `backup_id` | `str` | |
| `created_at` | `datetime` | |
| `archive_size_bytes` | `int` | |
| `total_uncompressed_bytes` | `int` | |
| `entry_count` | `int` | Number of files |
| `deployment_version` | `str` | From manifest |
| `schema_revision` | `str` | From manifest |
| `compatibility` | `SchemaCompatibility` | OK / WARN / BLOCKED |
| `compatibility_detail` | `str` | Human-readable explanation |
| `required_free_bytes` | `int` | For pre-flight (safety snapshot + extract) |
| `sufficient_space` | `bool` | |

### `VerifyResult`
**File**: `anvil/services/backup/verify_result.py` — Verify action output (FR-025).

| Field | Type | Notes |
|---|---|---|
| `backup_id` | `str` | |
| `valid` | `bool` | |
| `checked_count` | `int` | Files verified |
| `mismatched` | `list[str]` | Paths whose checksum failed |

### `ProgressEvent`
**File**: `anvil/services/backup/progress_event.py` — SSE payload for backup/restore progress.

| Field | Type | Notes |
|---|---|---|
| `event` | `str` | `progress` / `complete` / `error` / `heartbeat` |
| `operation_type` | `BackupOperationType` | |
| `backup_id` | `str \| None` | |
| `percent` | `float` | 0–100 |
| `current_step` | `str` | e.g. "Snapshotting database", "Verifying", "Swapping files" |
| `message` | `str \| None` | Error or info detail |
| `safety_snapshot_id` | `str \| None` | Surfaced on restore complete |

### `RetentionPolicy` (FR-032, R12)
**File**: `anvil/services/backup/retention_policy.py` — governs auto-rotation.

| Field | Type | Notes |
|---|---|---|
| `quota_bytes` | `int` | Hard storage cap |
| `max_count` | `int \| None` | Max number of non-safety backups (None = unbounded) |
| `max_age_days` | `int \| None` | Max age for non-safety backups (None = unbounded) |

Behavior: given current backups + a projected new size, returns the ordered list of **non-safety** backup ids to delete (oldest first) so the result fits the quota/count/age limits. **Never** returns a safety-snapshot id. Pure/​deterministic — unit-testable in isolation.

### `RestoreJournal` (FR-030, R13)
**File**: `anvil/services/backup/restore_journal.py` — crash-recovery marker, serialized to `data/backups/.restore-journal.json`.

| Field | Type | Notes |
|---|---|---|
| `restore_operation_id` | `str` | The in-flight restore op |
| `source_backup_id` | `str` | Backup being restored |
| `safety_snapshot_id` | `str` | Pre-restore safety snapshot for recovery |
| `roots` | `list[str]` | Managed roots being swapped |
| `phase` | `str` | `swapping` (only written during the swap window) |
| `created_at` | `datetime` | |

Lifecycle: written **before** the swap; removed only after clean, fully-verified completion. Presence at startup ⇒ interrupted restore ⇒ recovery (R13).

### `CreateBackupResult` (internal, R11/R12)
**File**: `anvil/services/backup/create_backup_result.py` — what `BackupService.create_backup` returns to the route so it can emit audit entries.

| Field | Type | Notes |
|---|---|---|
| `backup_id` | `str` | The created backup |
| `rotated_backup_ids` | `list[str]` | Non-safety backups auto-deleted to make room (each audited as `BACKUP_DELETE`) |

---

## 4. Enums (`StrEnum`)

### `BackupStatus` — `anvil/services/backup/backup_status.py`
```python
CREATING = "creating"
COMPLETED = "completed"
FAILED = "failed"
CORRUPTED = "corrupted"
```

### `BackupOperationType` — `anvil/services/backup/backup_operation_type.py`
```python
BACKUP = "backup"                       # manual user-initiated backup
RESTORE = "restore"                     # a restore operation record
PRE_RESTORE_SAFETY = "pre_restore_safety"   # auto snapshot before restore
```

### `SchemaCompatibility` — `anvil/services/backup/schema_compatibility.py`
```python
OK = "ok"            # same Alembic head + same version → restore freely
WARN = "warn"        # same head, version drift → allowed with warning
BLOCKED = "blocked"  # different Alembic head → restore blocked
```

### Existing enums to EXTEND (governance domain — FR-031, R11)

These already exist; add the members below (do not create new enums).

`AuditAction` — `anvil/services/governance/audit_action.py` (add):
```python
BACKUP_CREATE = "backup_create"
BACKUP_RESTORE = "backup_restore"
BACKUP_DELETE = "backup_delete"
SAFETY_SNAPSHOT_CLEANUP = "safety_snapshot_cleanup"
```

`AuditTargetType` — `anvil/services/governance/audit_target_type.py` (add):
```python
BACKUP = "backup"
```

`AuditOutcome` is reused as-is (`SUCCESS`/`REJECTED`/`ERROR`). No `AuditEvent` model, repository, or `AuditService.record()` changes are needed.

**Boundary discipline** (Constitution Principle 11): repository/API boundaries accept `str | <Enum>` and convert via `Enum(value)`; internal methods are strictly typed with the enum.

---

## 5. Archive On-Disk Layout

A backup archive (`backup-<id>.tar.gz`) extracts to:

```text
manifest.json                      # BackupManifest (root)
data/
├── anvil-state.db                 # consistent SQLite snapshot (single file, WAL-merged)
├── models/...                     # trained model artifacts
├── datasets/...                   # uploaded dataset files
├── storage/...                    # general blob store
└── content/...                    # content repository blobs
mlruns/
├── mlflow.db                      # MLflow backend SQLite snapshot
└── ...                            # MLflow artifacts
```

> The live WAL sidecar files (`-wal`, `-shm`) are **not** archived — the Online Backup API produces a single merged `.db`. On restore, only `anvil-state.db` is written; SQLite recreates `-wal`/`-shm` on next open.

---

## 6. Configuration Additions

**File**: `anvil/config.py` (`get_config()` dict additions)

| Key | Env var | Default |
|---|---|---|
| `backup_dir` | `ANVIL_BACKUP_DIR` | `data/backups` |
| `backup_quota_bytes` | `ANVIL_BACKUP_QUOTA_BYTES` | `10 * 1024**3` (10 GiB) |
| `backup_quota_warn_fraction` | `ANVIL_BACKUP_QUOTA_WARN` | `0.8` |
| `backup_retention_max_count` | `ANVIL_BACKUP_RETENTION_MAX_COUNT` | `None` (unbounded — quota governs) |
| `backup_retention_max_age_days` | `ANVIL_BACKUP_RETENTION_MAX_AGE_DAYS` | `None` (unbounded) |

### Snapshot scope (FR-001, R14)

**Included** managed roots: `data/anvil-state.db`, `data/models/`, `data/datasets/`, `data/storage/`, `data/content/`, `mlruns/` (incl. `mlruns/mlflow.db`).
**Excluded**: `logs/` (diagnostic), `.env`/environment config (environment-specific + secrets). `SnapshotPlanner` hard-codes this set.

---

## 7. Requirement → Model Traceability

| FR | Model element |
|---|---|
| FR-001 | Archive layout §5 (DB + all filesystem roots) |
| FR-007 | `backup_dir` config §6 |
| FR-008 | `BackupManifest`, `ManifestEntry` §3 |
| FR-009, FR-025 | `VerifyResult`; `manifest_sha256` + per-file checksums |
| FR-010, FR-011 | `BackupSummary`, `BackupStorageStatus` §3 |
| FR-012 | (service `BackupLock`; no model) |
| FR-018, FR-019, FR-020 | `BackupOperationType.PRE_RESTORE_SAFETY`; `BackupSummary.deletable` |
| FR-022 | `backup_id` unique + immutable archive (no update path) |
| FR-023 | `SchemaCompatibility`; `RestorePreview.compatibility` |
| FR-026 | `BackupStatus.CORRUPTED` |
| FR-027, FR-029 | `BackupStorageStatus` quota fields |
| FR-028 | `BackupSummary.deletable` + service "is last restorable" check |
| FR-030 | `RestoreJournal` + startup recovery |
| FR-031 | `AuditAction`/`AuditTargetType` additions; `CreateBackupResult.rotated_backup_ids` (route-layer audit emit, R11) |
| FR-032 | `RetentionPolicy`; config retention keys §6 |
| FR-001 (scope) | Snapshot inclusions/exclusions §6 (R14) |
