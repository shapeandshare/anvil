---
title: 'Session: Live backup progress in table rows with animated status chip'
type: session-log
tags:
  - type/session-log
  - domain/ui
  - domain/operations
created: '2026-06-27'
updated: '2026-06-27'
status: draft
source: agent
aliases:
  - backup-live-progress-row-chips
---

# Session: Live backup progress in table rows with animated status chip

**Date**: 2026-06-27
**Trigger**: User request — backup creation needs live feedback populated in the table rows with a moving update chip.

## What was done

### Problem

The Operations page already had a separate progress panel (spinner + bar) that showed during backup/restore, but the backup table rows themselves showed no live feedback. A row only appeared after the operation completed via `loadAll()`. Users had to look at a separate area above the table to see progress.

### Solution — in-row live progress chips via SSE

Three new JS helper methods were added to the `backup` object in `operations.html`, plus CSS for an animated pulsing dot indicator:

1. **`_getRowByBackupId(backupId)`** — Finds a table row by `data-key` attribute (matches `dom.syncTableBody` keying convention).

2. **`_findOrCreateRow(backupId)`** — Creates a live row immediately after POST `/v1/backup` returns, before SSE data arrives. The row shows a pulsing yellow "creating" badge in the status column.

3. **`_updateProgressRow(backupId, percent, step)`** — On each SSE `progress` event, updates the row's status chip to show `"45% — Archiving files"` with a pulsing dot.

4. **`_startSSE` modified** — Progress events now also update the table row. Complete events flip the badge to green "completed". Error events flip to red "failed". The existing progress panel still updates too for visibility.

5. **CSS `.badge__pulse` animation** — A 6px dot with `animation: badge-pulse 1.2s ease-in-out infinite` that scales between full size (opacity 1) and 70% (opacity 0.35), giving a gentle breathing pulse effect.

### Files changed

- `anvil/api/static/css/components.css` — Added `.badge__pulse` class and `@keyframes badge-pulse` animation.
- `anvil/api/templates/operations.html` — Added 3 helpers, modified `create()` to insert row, modified `_startSSE()` to update row on progress/complete/error.

### Design decisions

- The existing progress panel is preserved (visible at top for when the table is scrolled or empty).
- The `_updateProgressRow` updates use `innerHTML` comparison diffing (`statusCell.innerHTML !== statusHtml`) to avoid unnecessary DOM churn on every SSE event (matches `dom.setHtml` pattern).
- The row is inserted with `data-key` matching the backup_id so that `dom.syncTableBody` reconciliation in `loadAll()` can find and update it seamlessly when fresh server data arrives.
- Backup progress only (not restore) — restore operations use a different operation_id (the safety_snapshot_id) and the row may not exist.

## Related

- [[2026-06-27-backup-restore-ui-fixes-and-async-debt]]
- [[2026-06-27-backup-ui-csp-fixes]]
- [[ADR-040-deployment-backup-restore]]
