---
title: 'Session: Backup UI Fixes, Async Debt, Notification History'
type: session-log
tags:
  - type/session-log
  - domain/operations
  - domain/ui
  - domain/architecture
created: '2026-06-27'
updated: '2026-06-27'
status: draft
source: agent
aliases:
  - backup-ui-fixes-async-debt-notification-history
---
# Session: Backup UI Fixes, Async Debt, Notification History

**Date**: 2026-06-27
**Trigger**: Server crash on `make run`, then inability to restore/corrupted-delete from Ops UI, plus disappearing error toasts.

## What was done

### 1. Stale port 8080 — server fails to start
- `make run` errored with `Error 1` — uvicorn's `loop.create_server()` raised `OSError` (address in use) → `sys.exit(1)`.
- Root cause: a previous server process (PID 56179) still held port 8080 but was defunct (not serving).
- Killed the stale PID. Note: `make stop` handles this automatically, but a crashed server leaves the port occupied.

### 2. `Queue.put` never awaited in backup_service.py
- `RuntimeWarning: coroutine 'Queue.put' was never awaited` emitted twice from `backup_service.py:186` during operations.
- **Root cause**: Two `_progress` closures in `create_backup()` and `restore()` used `asyncio.get_event_loop()` to submit coroutines via `run_coroutine_threadsafe`. In Python 3.14, `get_event_loop()` can return a different/non-running loop when called from synchronous callbacks not in the main thread → coroutine never scheduled → garbage-collected with warning.
- **Fix**: Stored `asyncio.get_running_loop()` at `BackupService.__init__` time (called from async lifespan context) as `self._loop`. Both closures now use `self._loop`.
- This was one of 24+ `get_event_loop()` occurrences flagged by the thread model review (TMR, 2026-06-21). The majority remain.

### 3. Blocking `process.wait()` in async endpoints
- `MLflowService.stop()` calls `subprocess.Popen.wait(timeout=10)` synchronously. Called from `restart_all_services`, `restart_service`, and `stop_service` async route handlers → blocks the event loop for up to 10s, freezing the server.
- **Fix**: Added `async_stop()` method wrapping the `wait()` in `asyncio.to_thread()`. Updated all 3 endpoints to `await mlflow.async_stop()`.

### 4. Backup action buttons not rendering
- `_updateBackupRow()` in `operations.html` built the `actionsHtml` string (verify/restore/delete buttons) but **never assigned it to the DOM** — `tr.cells[5].innerHTML = actionsHtml` was missing.
- Pre-existing bug — buttons were computed on every syncTableBody update but silently discarded.
- **Fix**: Added the missing assignment.

### 5. Delete button unavailable for corrupted/failed backups
- Delete button was gated behind `if (b.status === 'completed')`. Corrupted and failed backups had no action buttons at all.
- **Fix**: Restructured button logic: verify only on `completed`, restore only on `completed` + non-safety, delete on `completed/corrupted/failed` + non-safety.

### 6. Notification history system
- **Problem**: Error toasts (and all toasts) disappeared after 3 seconds (`TOAST_DURATION = 3000`). Users couldn't read error details before they vanished. No mechanism to review past notifications.
- **Fix**: Two-part system:
  - **Persistence**: Both `content.js` and `operations.html` toast functions now push to `window._toastHistory[]` with timestamp, type, and message.
  - **Error duration**: Error toasts now last 10s (up from 3s). Info/success stay at 3s.
  - **History viewer**: Bell button (🔔) added to the backup actions bar. Opens a modal showing all notifications in reverse-chronological order with type badge, message, and relative time. Dismiss via Close/Escape/click-outside.
- Note: `toast()` functions are independently defined per page (each template has its own IIFE), so there are effectively two separate toast implementations — `content.js` (used by data/curation pages) and `operations.html` (used by the operations page). Both were updated.

### 7. Restart All toast shows per-service status
- `restartAll()` unconditionally showed "All services restarted" even though the API returns `"web": "cannot_manage"` (a web server can't restart itself from within).
- **Fix**: Toast now reflects the actual API response (e.g. "MLflow restarted. Web: cannot_manage").

## Key files changed

| File | Changes |
|------|---------|
| `anvil/services/backup/backup_service.py` | `self._loop` stored at init; both `_progress` closures use `self._loop` instead of `asyncio.get_event_loop()` |
| `anvil/supervisor/services.py` | Added `async_stop()` with `await asyncio.to_thread(self.process.wait, timeout=10)` |
| `anvil/api/v1/health_ops.py` | 3 endpoints use `await mlflow.async_stop()` |
| `anvil/api/templates/operations.html` | Backup buttons rendering, corrupted/failed delete, error toast 10s, notification history modal + bell, restartAll toast accuracy |
| `anvil/api/static/js/content.js` | Error toast 10s, `window._toastHistory[]` recording |

## Discovery notes

- [[Discoveries/asyncio-get-event-loop-deprecated-in-sync-callbacks|`asyncio.get_event_loop()` returns wrong loop in sync callbacks]] — new
- [[Discoveries/backup-row-actions-not-rendered|Backup row actions silently discarded in `_updateBackupRow`]] — new

## Related

- [[Sessions/2026-06-21-thread-model-review|Thread Model Review]] — flagged the `get_event_loop` pattern (24+ occurrences)
- [[Sessions/2026-06-27-backup-ui-csp-fixes|Backup UI CSP Fixes]] — prior session that added the `_updateBackupRow` function
- [[Sessions/2026-06-27-innerhtml-targeted-dom-updates|innerHTML to targeted DOM updates]] — prior session that introduced `dom.syncTableBody` and the `_updateBackupRow` pattern
- BackupService — system note (not yet created)
