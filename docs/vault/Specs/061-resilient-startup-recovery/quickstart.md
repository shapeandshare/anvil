# Quickstart: Resilient Startup Recovery

> Operator guide for what happens when the database is bad and how to recover.

## What Changed

Before this feature: a corrupt or schema-desynced DB → `sys.exit(1)` → process exits → no UI → operator instinct: `rm data/anvil-state.db` (data loss).

After this feature: the server enters **maintenance mode**, binds the port, and serves a recovery page at `/v1/recovery/page`. No data is lost automatically.

## First: Don't Panic

If `make run` or the container starts but the web UI shows a recovery page (or `GET /v1/ready` returns 503):

1. **Your data is safe.** The suspect database was snapshotted to `data/backups/quarantine/<timestamp>/` before any action.
2. **The server is alive** (`GET /v1/health` → 200). The Docker healthcheck won't crash-loop it.
3. **Open `/v1/recovery/page`** in your browser to see what's wrong and what you can do.

## Recovery Options (from the UI)

Once at the recovery page, you can choose:

| Action | What it does | Data loss? |
|--------|-------------|------------|
| **Restore from backup** | Restores the latest compatible backup via the 027 restore engine | Loses data committed after the backup timestamp |
| **Quarantine + reset** | Moves the suspect DB to quarantine, starts fresh | Original data preserved in quarantine but not logically restored |
| **Retry migrations** | Re-attempts Alembic migrations (may fix a partial migration) | No data loss |

Each action requires:
1. **`ANVIL_RECOVERY_KEY`** — set this env var before starting the server
2. **Explicit confirmation** — type "CONFIRM" or click the confirmation button

## Setting Up the Recovery Key

```bash
export ANVIL_RECOVERY_KEY="your-secret-token"
make run
```

If unset, read-only recovery info is available but destructive actions are rejected with a clear message.

## Testing Recovery Scenarios

```bash
# Simulate a desynced DB (revision stamped, tables dropped)
python -c "
import sqlite3
conn = sqlite3.connect('data/anvil-state.db')
conn.executescript('''
  PRAGMA user_version = 1;
  CREATE TABLE IF NOT EXISTS alembic_version (version_num VARCHAR(32));
  DELETE FROM alembic_version;
  INSERT INTO alembic_version VALUES ('007');
  DROP TABLE IF EXISTS datasets;
  DROP TABLE IF EXISTS corpora;
  DROP TABLE IF EXISTS license_catalog;
''')
conn.commit()
conn.close()
"

# Start the server — it should enter maintenance mode
make run

# Verify
curl http://localhost:8080/v1/ready    # 503
curl http://localhost:8080/v1/health   # 200
curl http://localhost:8080/v1/recovery # maintenance mode state
```

## Healthcheck Configuration (Docker)

In your `compose.yaml`, point the healthcheck at **liveness** (`/v1/health`), not readiness:

```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8080/v1/health"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 40s
```

This keeps the container alive during maintenance mode so you can recover via the UI.

## Known Failure Modes

| Symptom | Likely cause | Action |
|---------|-------------|--------|
| Recovery page says "desynced" | App tables missing vs. Alembic revision | Try "retry migrations" first, then "restore from backup" |
| Recovery page says "corrupt" | SQLite file is physically damaged | "Restore from backup" is the best option |
| Recovery page says "restore_in_progress" | A previous restore was interrupted | System auto-recovers via RestoreJournal — wait |

## File Locations

| What | Where |
|------|-------|
| Suspect DB snapshot | `data/backups/quarantine/<timestamp>/` |
| Backup archives | `data/backups/backup-<id>.tar.gz` |
| Restore journal | `data/backups/.restore-journal.json` |
| App DB | `data/anvil-state.db` |
