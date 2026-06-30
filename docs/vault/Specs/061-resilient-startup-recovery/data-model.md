# Data Model: Resilient Startup Recovery

> Entities, states, and relationships for the startup classification, snapshot, and recovery infrastructure.

## 1. DbState (Enum)

**File**: `anvil/db/db_state.py` (NEW)
**Extends**: `StrEnum` (Python 3.11+ stdlib)

| Member | Value | Meaning |
|--------|-------|---------|
| `FRESH` | `"fresh"` | DB file did not exist before this startup; no `-wal`/`-shm` sidecars. Safe to initialize. |
| `HEALTHY` | `"healthy"` | DB readable, integrity passes, all expected tables present, Alembic revision consistent. |
| `DESYNCED` | `"desynced"` | Integrity passes but expected tables missing or revision inconsistent with schema. |
| `CORRUPT` | `"corrupt"` | SQLite cannot open DB, or `PRAGMA quick_check`/`integrity_check` fails. |
| `RESTORE_IN_PROGRESS` | `"restore_in_progress"` | `RestoreJournal` marker present on disk — a previous restore was interrupted. |

**Validation rules**:
- `FRESH` must be determined by **filesystem provenance only** — DB file absence AND no sidecars.
- A zero-byte DB file is NOT `FRESH` — it is treated as existing user state.
- Never infer `FRESH` from a read error.

**State transitions**:
```
[RESTORE_IN_PROGRESS] → journal.recover() → [reclassify as FRESH/HEALTHY/DESYNCED/CORRUPT]
[FRESH]               → init + migrate → [HEALTHY]
[HEALTHY]             → migrate/verify → [HEALTHY] (or DESYNCED if migration fails)
[DESYNCED]            → operator action → [HEALTHY] (restore/reset/retry-migrate)
[CORRUPT]             → operator action → [HEALTHY] (restore/reset)
```

## 2. StartupClassifier (Read-Only Component)

**File**: `anvil/db/db_state.py` (NEW)

A class (not a service — no session/repository dependencies) that performs read-only DB classification.

```python
class StartupClassifier:
    @staticmethod
    async def classify(db_url: str, db_path: Path) -> DbState
    @staticmethod
    async def check_provenance(db_path: Path) -> bool       # True if fresh
    @staticmethod
    async def check_integrity(db_url: str) -> IntegrityResult
    @staticmethod
    async def check_schema(db_url: str) -> SchemaResult
```

**Methods**:

| Method | Input | Output | Description |
|--------|-------|--------|-------------|
| `classify()` | `db_url: str, db_path: Path` | `DbState` | Orchestrates all checks in order: provenance → restore-journal → integrity → schema |
| `check_provenance()` | `db_path: Path` | `bool` | Returns True if DB file does not exist AND `-wal`/`-shm` absent |
| `check_integrity()` | `db_url: str` | `IntegrityResult` | Runs `PRAGMA quick_check`, escalates to `integrity_check` on failure |
| `check_schema()` | `db_url: str` | `SchemaResult` | Reads `PRAGMA user_version`, Alembic revision, runs `verify_table_integrity()` |

**Return types**:

```python
class IntegrityResult(BaseModel):
    passed: bool
    detail: str  # empty if passed, error message if failed

class SchemaResult(BaseModel):
    user_version: int | None       # None = read error
    alembic_revision: str | None   # None = no stamp
    expected_tables: frozenset[str]
    missing_tables: list[str]      # empty = all present
    consistent: bool               # True if all checks pass
```

## 3. MaintenanceMode (Runtime State)

**Location**: `app.state.maintenance_mode` (optional, set in lifespan)
**File**: `anvil/services/recovery/recovery_service.py` (NEW)

```python
class MaintenanceMode(BaseModel):
    active: bool
    db_state: DbState
    cause: str                     # human-readable explanation
    detected_at: datetime
    preserved_path: Path | None    # quarantine/snapshot location
    available_actions: list[RecoveryAction]
```

**Access pattern**: Routes check `request.app.state.maintenance_mode` — if present and `active=True`, normal routes short-circuit with a "recovery mode" response.

## 4. RecoveryAction (Enum)

**File**: `anvil/services/recovery/recovery_service.py` (NEW)
**Extends**: `StrEnum`

| Member | Value | Requires Confirmation | Requires `ANVIL_RECOVERY_KEY` |
|--------|-------|----------------------|-------------------------------|
| `RESTORE` | `"restore"` | Yes | Yes |
| `QUARANTINE_RESET` | `"quarantine_reset"` | Yes | Yes |
| `RETRY_MIGRATIONS` | `"retry_migrations"` | Yes | Yes |
| `SALVAGE` | `"salvage"` | Yes | Yes (advanced) |

## 5. DbSnapshot (Artifact)

**File**: `anvil/services/recovery/snapshot.py` (NEW)

A timestamped, preserved copy of the DB trio plus metadata. Written to `data/backups/quarantine/<timestamp>/`.

```python
class DbSnapshot(BaseModel):
    timestamp: datetime
    detected_state: DbState
    cause: str
    paths: SnapshotPaths
    manifest: SnapshotManifest

class SnapshotPaths(BaseModel):
    db: Path        # original DB path (source)
    wal: Path | None
    shm: Path | None
    dest_dir: Path  # data/backups/quarantine/<timestamp>/

class SnapshotManifest(BaseModel):
    size_bytes: int
    sha256: str
    timestamp: datetime
    detected_state: str
    cause: str
```

**Directory layout**:
```
data/backups/quarantine/20260630T150000Z/
├── anvil-state.db
├── anvil-state.db-wal          (present if WAL was non-empty at snapshot time)
├── anvil-state.db-shm          (present if WAL was non-empty)
└── manifest.json               (SnapshotManifest JSON)
```

## 6. Quarantine (Action)

**File**: `anvil/services/recovery/quarantine.py` (NEW)

Same structure as `DbSnapshot` but uses `shutil.move()` (or `os.rename()`) instead of copy. The source DB path is freed for a fresh init.

## 7. RecoveryService (Service Layer)

**File**: `anvil/services/recovery/recovery_service.py` (NEW)

Orchestrates recovery actions, gated by operator confirmation and recovery token.

```python
class RecoveryService:
    def __init__(self, backup_dir: Path, recovery_key: str | None)

    async def snapshot_suspect_db(self, db_path: Path, state: DbState, cause: str) -> DbSnapshot
    async def quarantine_and_reset(self, db_path: Path, state: DbState, cause: str, token: str) -> DbSnapshot
    async def restore_from_backup(self, backup_id: str, token: str) -> RestoreResult
    async def retry_migrations(self, db_url: str, token: str) -> MigrationResult
    async def list_available_backups(self) -> list[BackupSummary]
    def verify_recovery_token(self, token: str | None) -> bool
```

**Integration with existing services**:
- `restore_from_backup()` delegates to existing `BackupService.restore()` (FR-015)
- `list_available_backups()` scans `data/backups/backup-*.tar.gz` filesystem directly (DB is unavailable)
- Space estimation before destructive actions uses existing `SnapshotPlanner.plan()`

## 8. Integrated Data Flow

```
                        ┌─────────────────────────────┐
                        │   StartupClassifier           │
                        │   (read-only, no deps)        │
                        └──────────┬──────────────────┘
                                   │ DbState
                                   ▼
                        ┌─────────────────────────────┐
                        │   Lifespan Branch             │
                        │   - fresh/healthy → continue  │
                        │   - desynced/corrupt → Maint  │
                        └──────────┬──────────────────┘
                                   │
              ┌────────────────────┼────────────────────┐
              ▼                    ▼                    ▼
   ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
   │ Normal Startup    │  │ MaintenanceMode   │  │ RecoveryService   │
   │ (migrate, seed,   │  │ (app.state flag,  │  │ (snapshot,        │
   │  bootstrap, etc.) │  │  route gate,      │  │  quarantine,      │
   │                   │  │  recovery page)   │  │  restore, etc.)   │
   └──────────────────┘  └──────────────────┘  └──────────────────┘
```
