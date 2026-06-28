---
title: Backup SSE Reconnection on Page Refresh
type: session-log
tags:
  - type/session-log
  - domain/ui
  - domain/operations
created: '2026-06-27'
updated: '2026-06-27'
status: draft
source: agent
aliases: Backup SSE Reconnection on Page Refresh
---

# Backup SSE Reconnection on Page Refresh

**Session**: Fixed a UX bug where refreshing the Operations page during a
running backup would lose all progress context — the SSE progress card
disappeared and the user had no way to see the operation still running.

## What was done

### Diagnosed the state-loss mechanism

Traced the full backup flow:
1. `POST /v1/backup` → `BackupService.create_backup()` → creates DB row with `status='creating'`
2. Frontend stores `backup._activeOperationId` and connects `EventSource` to `/v1/backup/stream/{id}`
3. On page refresh: JS state resets (`_activeOperationId`, `_eventSource` both null)
4. The DB still shows `status='creating'` but the UI never reconnects

### Added `checkForActiveOperation()` to ops page

Wired a new method on the `backup` JS object that runs on page load:
- Fetches `GET /v1/backup` (the backup list)
- Scans for any entry with `status === 'creating'`
- If found, reconnects the SSE stream to resume progress tracking

### Files modified

- `anvil/api/templates/operations.html` — 2 edits:
  - Added `checkForActiveOperation()` method (lines 785-806)
  - Added `setTimeout` call on page load (line 919)

## Discoveries

- [[Discoveries/backup-sse-state-lost-on-page-refresh|Backup SSE State Lost on Page Refresh]]
