# Contract: Backup HTTP API (`/v1/backup`)

**Feature**: 026-deployment-backup-restore | **Phase**: 1
**Module**: `anvil/api/v1/backup.py` (new `router = APIRouter()`, included in `anvil/api/v1/router.py`)

All routes are `async`. They call the `AnvilWorkbench` god class (`request.app.state` provides the shared process-lifetime `BackupService`; a per-request `BackupOperationRepository` is wired through the workbench). Request/response bodies are Pydantic `BaseModel` with `ConfigDict(extra="forbid")`, matching `anvil/api/v1/schemas.py` conventions. Errors use `HTTPException` with the status codes below.

> **Auth/versioning**: inherits the existing `/v1` router's API-key + header-versioning middleware (feature 023/024). No backup-specific auth model.
>
> **Audit (FR-031, R11)**: `POST /v1/backup` (create), `POST /v1/backup/{id}/restore`, `DELETE /v1/backup/{id}`, and safety-snapshot cleanup each emit an `audit_event` via the **session-bound** `workbench.audit.record(...)` **at the route layer** (the process-lifetime `BackupService` does not hold a session). Actions: `backup_create` / `backup_restore` / `backup_delete` / `safety_snapshot_cleanup`; target type `backup`; outcome `success`/`error`. Audit-write failure propagates (rolls back the route's transaction).

---

## Endpoints

### `POST /v1/backup` — Create a backup
Initiates a full deployment backup. Returns immediately (202) with the new `backup_id`; progress is observed via the stream endpoint.

**Request body**: none.

**Behavior**: Before creating, the service runs **auto-rotation** (FR-027/FR-032): if the new backup would exceed the quota, it deletes the oldest non-safety backups (per the retention policy) to make room. The route emits a `backup_create` audit entry on success, plus one `backup_delete` audit entry per rotated backup (FR-031, R11).

**Responses**:
- `202 Accepted`
  ```json
  { "backup_id": "20260621T143000Z-a1b2c3", "status": "creating", "rotated_backup_ids": [] }
  ```
- `409 Conflict` — a backup or restore is already running:
  ```json
  { "detail": "A backup operation is already in progress", "operation_type": "backup", "backup_id": "..." }
  ```
- `507 Insufficient Storage` — pre-flight space/quota check failed **even after rotating all eligible non-safety backups**:
  ```json
  { "detail": "Insufficient space after rotation: need 620 MB, 410 MB free", "required_bytes": 650117120, "available_bytes": 429916160 }
  ```

---

### `GET /v1/backup` — List backups
**Query**: `?include_safety=true|false` (default `true`).

**Response** `200 OK` — array of `BackupSummary`:
```json
[
  {
    "backup_id": "20260621T143000Z-a1b2c3",
    "operation_type": "backup",
    "status": "completed",
    "created_at": "2026-06-21T14:30:00Z",
    "archive_size_bytes": 534773760,
    "deployment_version": "1.7.0",
    "schema_revision": "002",
    "age_seconds": 3600,
    "is_safety_snapshot": false,
    "deletable": true
  }
]
```

---

### `GET /v1/backup/status` — Storage status card
**Response** `200 OK` — `BackupStorageStatus`:
```json
{
  "backup_count": 4,
  "total_bytes": 2147483648,
  "quota_bytes": 10737418240,
  "quota_used_fraction": 0.2,
  "over_threshold": false,
  "latest_backup_at": "2026-06-21T14:30:00Z",
  "oldest_backup_at": "2026-06-18T09:00:00Z"
}
```

---

### `GET /v1/backup/{backup_id}` — Get one backup
**Response** `200 OK` — `BackupSummary`. `404` if unknown.

---

### `GET /v1/backup/{backup_id}/preview` — Restore preview
Drives wizard step 1: reads the manifest, computes schema compatibility and space pre-flight.

**Response** `200 OK` — `RestorePreview`:
```json
{
  "backup_id": "20260621T143000Z-a1b2c3",
  "created_at": "2026-06-21T14:30:00Z",
  "archive_size_bytes": 534773760,
  "total_uncompressed_bytes": 901234567,
  "entry_count": 1284,
  "deployment_version": "1.7.0",
  "schema_revision": "002",
  "compatibility": "ok",
  "compatibility_detail": "Schema head matches the running deployment.",
  "required_free_bytes": 1802469134,
  "sufficient_space": true
}
```
- `404` if unknown backup.

---

### `GET /v1/backup/stream/{backup_id}` — SSE progress
Server-Sent Events for an in-flight backup or restore. Mirrors the training SSE contract (`anvil/api/v1/training.py`): `StreamingResponse`, `media_type="text/event-stream"`, headers `Cache-Control: no-cache`, `X-Accel-Buffering: no`.

**Events** (`event:` / `data:` = JSON `ProgressEvent`):
- `progress` — `{ "percent": 42.0, "current_step": "Snapshotting database", "operation_type": "backup", "backup_id": "..." }`
- `complete` — `{ "percent": 100, "backup_id": "...", "safety_snapshot_id": "..."|null }`
- `error` — `{ "message": "…" }`
- `heartbeat` — `{}` every 30s of inactivity.

Stream closes after `complete` or `error`. If the operation already finished/never existed, emits a single `error` event then closes (training-endpoint precedent).

---

### `POST /v1/backup/{backup_id}/restore` — Restore from a backup
Starts a restore. **Always** auto-creates a pre-restore safety snapshot first (FR-018). Returns 202; progress via stream.

**Request body**:
```json
{ "confirm": "RESTORE" }
```
- `confirm` MUST equal the literal string `"RESTORE"` (FR-021).

**Responses**:
- `202 Accepted` — `{ "restore_operation_id": "...", "safety_snapshot_id": "...", "status": "creating" }`
- `400 Bad Request` — confirmation token missing/incorrect: `{ "detail": "Confirmation token must be 'RESTORE'" }`
- `409 Conflict` — operation already running (same shape as create).
- `409 Conflict` — schema incompatible (`BLOCKED`): `{ "detail": "Backup schema (head 001) is incompatible with the running deployment (head 002). Restore blocked.", "compatibility": "blocked" }`
- `507 Insufficient Storage` — no room for safety snapshot + extract.

---

### `POST /v1/backup/{backup_id}/verify` — Verify integrity
Recomputes per-file checksums against the manifest (FR-025). May take time for large archives; runs server-side and returns the result (not streamed for v1).

**Response** `200 OK` — `VerifyResult`:
```json
{ "backup_id": "...", "valid": true, "checked_count": 1284, "mismatched": [] }
```
A failed verify also transitions the backup's stored `status` to `corrupted` (FR-026). `404` if unknown.

---

### `DELETE /v1/backup/{backup_id}` — Delete a backup
**Query**: `?confirm_last=true` — required only when deleting the last restorable backup (FR-028).

**Responses**:
- `200 OK` — `{ "deleted": "20260621T143000Z-a1b2c3" }`
- `400 Bad Request` — attempting to delete the last restorable backup without `confirm_last=true`:
  ```json
  { "detail": "This is the only remaining backup. Deleting it leaves no recovery option.", "is_last": true }
  ```
- `403 Forbidden` — attempting to delete a pre-restore safety snapshot via this route (FR-020):
  ```json
  { "detail": "Safety snapshots cannot be deleted here. Use the safety-snapshot cleanup action." }
  ```
- `404` if unknown.

---

## Contract Test Matrix (e2e — `tests/e2e/test_backup_endpoints.py`)

| Test | Asserts |
|---|---|
| create returns 202 + id, archive appears | FR-002, US1/1 |
| second create while running returns 409 | FR-012 |
| list shows created backup with status `completed` | FR-010, US1/2 |
| status returns counts/quota/ages | FR-011, FR-029 |
| preview returns compatibility + space | FR-023, US2/1 |
| restore without `confirm=="RESTORE"` → 400 | FR-021 |
| restore happy path → 202, safety_snapshot_id present | FR-018, US2 |
| restore of schema-incompatible backup → 409 blocked | FR-023 |
| verify valid backup → `valid:true` | FR-025 |
| verify tampered archive → `valid:false`, status→corrupted | FR-025, FR-026 |
| delete last backup without confirm_last → 400 | FR-028 |
| delete safety snapshot → 403 | FR-020 |
| SSE stream emits progress then complete | SSE contract |
| create over quota auto-rotates oldest non-safety; `rotated_backup_ids` populated | FR-027, FR-032 |
| rotation never deletes a safety snapshot | FR-032 |
| create/restore/delete each emit an audit_event (action/target/outcome) | FR-031 |
| restore writes a journal before swap; cleared on success | FR-030 |

> **Note — not an HTTP endpoint**: interrupted-restore recovery (FR-030) runs at **application startup** (lifespan), not via a route. Its tests live in `tests/unit/services/backup/test_restore_journal.py` and a startup-recovery unit test, not in the e2e route suite.
