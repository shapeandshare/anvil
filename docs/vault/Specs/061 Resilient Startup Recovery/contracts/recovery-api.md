# Recovery API Contracts

> HTTP API contracts for the maintenance/recovery surface. All recovery endpoints are auth-exempt (read-only views) or require `Authorization: Bearer <ANVIL_RECOVERY_KEY>` (state-altering actions).

## Readiness: `GET /v1/ready`

Liveness stays at `GET /v1/health` (unchanged: returns `{"status":"healthy"}` auth-exempt, always 200).

### Response (Normal Mode — DB writable)

```json
{
  "status": "ready",
  "db_state": "healthy"
}
```

Status: **200 OK**

### Response (Maintenance Mode — DB desynced/corrupt)

```json
{
  "status": "not_ready",
  "db_state": "desynced",
  "cause": "Schema version mismatch: expected tables missing (datasets, corpora, license_catalog)"
}
```

Status: **503 Service Unavailable**

### Response (Maintenance Mode — DB corrupt)

```json
{
  "status": "not_ready",
  "db_state": "corrupt",
  "cause": "PRAGMA integrity_check: database disk image is malformed"
}
```

Status: **503 Service Unavailable**

---

## Recovery Status: `GET /v1/recovery`

Returns the current maintenance/recovery mode state. Only meaningful in maintenance mode; in normal mode returns `{"maintenance_mode": false}`.

### Response (Maintenance Mode)

```json
{
  "maintenance_mode": true,
  "db_state": "desynced",
  "cause": "Schema version mismatch: expected tables missing (datasets)",
  "detected_at": "2026-06-30T15:00:00Z",
  "preserved_artifact": "data/backups/quarantine/20260630T150000Z/",
  "available_actions": ["restore", "quarantine_reset", "retry_migrations"],
  "has_backups": true
}
```

Status: **200 OK** (auth-exempt)

### Response (Normal Mode)

```json
{
  "maintenance_mode": false
}
```

Status: **200 OK** (auth-exempt)

---

## List Available Backups: `GET /v1/recovery/backups`

Lists backups available for restore. Scans the filesystem (`data/backups/backup-*.tar.gz`) since the app DB is unavailable.

### Response

```json
{
  "backups": [
    {
      "backup_id": "20260629T120000Z-a1b2c3",
      "archive_filename": "backup-20260629T120000Z-a1b2c3.tar.gz",
      "size_bytes": 1048576,
      "created_at": "2026-06-29T12:00:00Z",
      "deployment_version": "0.18.0",
      "schema_revision": "007"
    }
  ]
}
```

Status: **200 OK** (auth-exempt)

---

## Get Recovery Action Confirmation Shape: `GET /v1/recovery/actions/{action}`

Returns what confirmation is required before the action can be executed.

### Response

```json
{
  "action": "restore",
  "label": "Restore from Backup",
  "description": "Restore the application database from a verified backup. This will roll back to the backup timestamp — data committed after the backup will be lost.",
  "requires_confirmation": true,
  "confirmation_token_name": "confirm",
  "confirmation_type": "string",
  "parameters": [
    {
      "name": "backup_id",
      "type": "string",
      "required": true,
      "description": "Backup ID from /v1/recovery/backups"
    }
  ]
}
```

Status: **200 OK** (auth-exempt)

---

## Execute Recovery Action: `POST /v1/recovery/actions/{action}`

Executes a state-altering recovery action. Requires `Authorization: Bearer <ANVIL_RECOVERY_KEY>` and `{"confirm": "<confirmation_string>"}` in the body.

### Request

```json
{
  "confirm": "CONFIRM",
  "backup_id": "20260629T120000Z-a1b2c3"
}
```

### Response (Accepted)

```json
{
  "status": "accepted",
  "message": "Safety snapshot taken. Restore from backup 20260629T120000Z-a1b2c3 initiated.",
  "snapshot_path": "data/backups/quarantine/20260630T150001Z/",
  "restart_required": true
}
```

Status: **202 Accepted**

### Response (Missing/Invalid Recovery Key)

```json
{
  "detail": "Recovery token required. Set ANVIL_RECOVERY_KEY or provide 'Authorization: Bearer <token>'."
}
```

Status: **403 Forbidden**

### Response (Missing Confirmation)

```json
{
  "detail": "Action 'restore' requires confirmation. Provide '{\"confirm\": \"CONFIRM\"}' in the request body."
}
```

Status: **400 Bad Request**

### Action-Specific Parameters

| Action | Body Fields | Description |
|--------|-------------|-------------|
| `restore` | `confirm`, `backup_id` | Restore from specified backup |
| `quarantine_reset` | `confirm` | Move suspect DB to quarantine, init fresh DB |
| `retry_migrations` | `confirm` | Re-attempt Alembic migrations on suspect DB |

---

## Recovery Page: `GET /v1/recovery/page`

Returns the rendered Jinja2 recovery page HTML. Shows DB status, cause, preserved artifact location, available backups, and gated recovery action buttons.

### Response

Status: **200 OK** (auth-exempt). Content-Type: `text/html`

Renders `templates/recovery.html` template with context:
```json
{
  "db_state": "desynced",
  "cause": "Schema version mismatch: expected tables missing (datasets)",
  "detected_at": "2026-06-30T15:00:00Z",
  "preserved_artifact": "data/backups/quarantine/20260630T150000Z/",
  "available_backups": [{"backup_id": "...", "created_at": "...", "size_bytes": 1048576}],
  "available_actions": ["restore", "quarantine_reset", "retry_migrations"],
  "has_recovery_key": true
}
```

---

## Error Responses (Common)

### 503 — Maintenance mode active (normal routes)

```json
{
  "detail": "Service is in maintenance mode. Database recovery is required before this endpoint is available.",
  "recovery_url": "/v1/recovery/page"
}
```

### 401 — Missing recovery key for action

```json
{
  "detail": "This action requires authentication via ANVIL_RECOVERY_KEY."
}
```
