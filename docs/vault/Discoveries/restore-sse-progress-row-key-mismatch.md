---
title: Restore SSE Progress Row Key Mismatch — safety_snapshot_id vs backup_id
type: discovery
tags:
  - type/discovery
  - domain/operations
  - domain/ui
created: '2026-06-28'
updated: '2026-06-28'
status: draft
source: agent
aliases:
  - restore-sse-progress-row-key-mismatch
code-refs:
  - anvil/api/templates/operations.html
  - anvil/services/backup/backup_service.py
  - anvil/services/backup/progress_event.py
---

# Restore SSE Progress Row Key Mismatch

**Discovered**: 2026-06-28
**Context**: Restore SSE event flow between `backup_service.py`, `operations.html`
**Severity**: P3 (cosmetic — row badge fails to update before table refresh)

## The problem

When a restore operation runs, the backend emits SSE events keyed to the `safety_snapshot_id` (the pre-restore safety snapshot's backup_id). The frontend correctly connects SSE using `safety_snapshot_id`. However, the SSE event handlers in `_startSSE()` attempted to find the corresponding table row using `data.backup_id`, which for restore operations is the *original* backup being restored FROM — not the safety snapshot. The safety snapshot row lookup failed silently, so the inline badge update before `loadAll()` refreshed the table was a no-op.

## The fix

Three changes were needed:

1. **Backend**: The `_progress` closure in `BackupService.restore()` omitted `safety_snapshot_id` from restore progress `ProgressEvent`s. Added it so the frontend can resolve the correct row key. (`backup_service.py:475`)

2. **Frontend — complete/error handlers**: Changed row lookup from `data.backup_id` to `data.safety_snapshot_id || data.backup_id` so restore operations resolve the safety snapshot's row and backup operations still use their native backup_id. (`operations.html:759, 784`)

3. **Frontend — progress handler**: Removed the `data.operation_type !== 'restore'` guard that prevented restore progress from updating any table row at all. Changed lookup to `data.safety_snapshot_id || data.backup_id`. (`operations.html:744`)

## Notification history

All backup/restore events already push to `window._toastHistory` via the `toast()` function, which feeds the notification history modal. No changes needed there.

## References

- `anvil/api/templates/operations.html`
- `anvil/services/backup/backup_service.py`
- `anvil/services/backup/progress_event.py`