---
title: Restore SSE progress badge fix — safety_snapshot_id row key mismatch
type: session-log
tags:
  - type/session-log
  - domain/operations
  - domain/ui
created: '2026-06-28'
updated: '2026-06-28'
aliases: Restore SSE progress badge fix
source: agent
---

# Session: Restore SSE progress badge fix

**Updated**: 2026-06-28
**Tags**: `type/session-log`, `domain/operations`, `domain/ui`

## Summary

Fixed a bug where restore operation progress/complete/error events failed to update the inline table row badge because the frontend looked up rows by `data.backup_id` (the source backup) instead of `data.safety_snapshot_id` (the pre-restore safety snapshot's ID).

## Work Done

1. **Investigation**: Traced the full restore SSE flow from backend (`BackupService.restore()`) through SSE streaming endpoint (`GET /v1/backup/stream/{operation_id}`) to frontend (`_startSSE()` in `operations.html`).

2. **Root cause found**: Three interrelated issues:
   - Backend progress events omitted `safety_snapshot_id` → frontend couldn't resolve the correct row key
   - Complete/error handlers used `data.backup_id` (source backup) instead of `safety_snapshot_id`
   - Progress handler explicitly skipped restore operations with `data.operation_type !== 'restore'` guard

3. **Fixes applied**:
   - `backup_service.py`: Added `safety_snapshot_id` to restore progress ProgressEvents
   - `operations.html`: All three SSE event handlers now use `safety_snapshot_id || backup_id` for row resolution; progress guard removed

4. **Verification**: Ran backup-specific test suite (44/44 passed, 10 pre-existing e2e infra errors). Diagnostics show no new errors introduced.

## Vault Enrichment

- [[restore-sse-progress-row-key-mismatch]] — discovery note documenting the bug and fix
- [[Discoveries/restore-sse-progress-row-key-mismatch]]

## References

- `anvil/api/templates/operations.html`
- `anvil/services/backup/backup_service.py`