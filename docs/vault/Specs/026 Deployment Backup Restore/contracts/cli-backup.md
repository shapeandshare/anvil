# Contract: `anvil-backup` CLI

**Feature**: 026-deployment-backup-restore | **Phase**: 1
**Module**: `anvil/services/backup/cli.py` — `build_parser()` + `main(argv)` + `_cmd_*` functions
**Wiring**: `pyproject.toml` → `[project.scripts]` → `anvil-backup = "anvil.services.backup.cli:main"`

Mirrors the established anvil CLI pattern (`anvil/services/vault/cli.py`, `anvil/cli.py:corpus_main`): `argparse` with subcommands, an `async def _run()` body invoked via `asyncio.run()`, using `AsyncSessionLocal()` for DB access and a `BackupService` for the work. CLI parity with the UI is mandatory (FR-004/005/006, SC-007).

---

## Synopsis

```
anvil-backup create
anvil-backup list [--include-safety] [--json]
anvil-backup show <backup-id> [--json]
anvil-backup verify <backup-id> [--json]
anvil-backup restore <backup-id> [--force] [--yes]
anvil-backup delete <backup-id> [--confirm-last]
anvil-backup status [--json]
anvil-backup cleanup-safety [--yes]
```

---

## Subcommands

### `create`
Creates a full deployment backup. Streams progress to stderr; prints the new `backup_id` to stdout on success. Runs auto-rotation first (deletes oldest non-safety backups if over quota; never safety snapshots) and prints any rotated ids. Emits `backup_create` (+ `backup_delete` per rotated id) audit entries.
- **Exit 0** on success.
- **Exit 3** if another operation is in progress (maps to API 409).
- **Exit 4** if insufficient space/quota **after rotation** (maps to 507). Message states needed vs available.

```
$ anvil-backup create
Creating backup… [████████░░] 80%  Snapshotting MLflow
Backup created: 20260621T143000Z-a1b2c3  (510 MB)
```

### `list`
Lists backups (newest first). `--json` emits a JSON array of `BackupSummary`. Without `--include-safety`, pre-restore safety snapshots are hidden.

```
$ anvil-backup list
BACKUP ID                    TYPE     STATUS     SIZE     AGE        VER
20260621T143000Z-a1b2c3      backup   completed  510 MB   1h ago     1.7.0
20260620T090000Z-d4e5f6      backup   completed  498 MB   1d ago     1.7.0
```

### `show <backup-id>`
Prints one backup's detail (table or `--json`). **Exit 5** if not found.

### `verify <backup-id>`
Recomputes checksums vs manifest (FR-025). Prints `Valid` or `Corrupted (N mismatched)`.
- **Exit 0** valid; **Exit 6** corrupted (and marks status `corrupted`). **Exit 5** if not found.

### `restore <backup-id>`
Restores the deployment.
- **Two-step safety (FR-021):** the command (a) auto-creates a pre-restore safety snapshot, then (b) requires the operator to type `RESTORE` at an interactive prompt before applying. The typed confirmation is **always** required.
- `--force` skips only the *service-pause* interactive confirmation, **not** the typed `RESTORE` confirmation.
- `--yes` is rejected as a means to bypass the typed confirmation (documented: there is intentionally no flag that skips typing `RESTORE`).
- On success prints the restored state summary and the **safety snapshot id** for undo.

```
$ anvil-backup restore 20260620T090000Z-d4e5f6
Creating pre-restore safety snapshot… done (20260621T150000Z-z9y8x7)
Schema compatibility: OK
This will overwrite the current deployment state.
Type RESTORE to continue: RESTORE
Restoring… [██████████] 100%
Restore complete. Pre-restore safety snapshot: 20260621T150000Z-z9y8x7
Restart the application to load restored state.
```
- **Exit 0** success; **Exit 2** confirmation not given/incorrect; **Exit 3** busy; **Exit 4** insufficient space; **Exit 5** not found; **Exit 7** schema incompatible (BLOCKED).

### `delete <backup-id>`
Deletes a backup archive + its DB row.
- Prompts for confirmation showing details.
- If it is the last restorable backup, requires `--confirm-last` (FR-028); otherwise **Exit 8** with the warning message.
- Refuses to delete a safety snapshot (**Exit 9**); directs to `cleanup-safety` (FR-020).

### `status`
Prints the storage status (count, total, quota gauge, latest/oldest). `--json` → `BackupStorageStatus`.

### `cleanup-safety`
The separate, explicitly-labeled path to remove pre-restore safety snapshots (FR-020). Prompts unless `--yes`.

---

## Exit Code Table

| Code | Meaning | API analogue |
|---|---|---|
| 0 | Success | 2xx |
| 2 | Confirmation missing/incorrect | 400 |
| 3 | Operation already in progress | 409 |
| 4 | Insufficient space / quota exceeded | 507 |
| 5 | Backup not found | 404 |
| 6 | Verify found corruption | 200 (`valid:false`) |
| 7 | Schema incompatible (restore blocked) | 409 |
| 8 | Refused: would delete last restorable backup | 400 |
| 9 | Refused: cannot delete safety snapshot here | 403 |

---

## Behavioral Guarantees (shared with API)

- **Identical effect** to the UI one-click backup (FR-004 / US3 scenario 1): both call `BackupService.create_backup()`.
- **Audit (FR-031)**: every `create`/`restore`/`delete`/`cleanup-safety` invocation emits an `audit_event` via a session-bound `workbench.audit.record(...)` in the CLI's `async _run()` body (the CLI opens its own `AsyncSessionLocal()`), mirroring the route-layer pattern.
- **Auto-rotation (FR-027/FR-032)**: `create` self-maintains storage; safety snapshots are exempt.
- **Crash recovery (FR-030)**: an interrupted restore is recovered at next **application startup** (lifespan), not by the CLI; the CLI restore writes the same journal the server reads.
- **Single-operation lock** is process-scoped; a CLI `create`/`restore` while the web server runs one (or vice-versa) is **not** guaranteed mutually exclusive across processes in v1 (single-host assumption; documented limitation — see research R7). For correctness operators should avoid concurrent CLI + UI operations.

> *Cross-process locking is explicitly out of scope for v1 per the spec's single-host assumption; this is the one place where the in-process lock does not protect. Documented here so it is a known, accepted limitation rather than a silent gap.*
