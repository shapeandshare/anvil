---
title: Backup SSE connection state lost on ops page refresh
type: discovery
tags:
  - type/discovery
  - domain/ui
  - domain/operations
created: '2026-06-27'
updated: '2026-06-27'
status: draft
source: agent
aliases:
  - backup-sse-state-lost-on-page-refresh
code-refs:
  - anvil/api/templates/operations.html
---

# Backup SSE Connection State Lost on Ops Page Refresh

**Discovered**: 2026-06-27
**Context**: `anvil/api/templates/operations.html` — `backup` JS object
**Severity**: P3 (UX regression — in-progress context lost on navigation)

## The problem

When a user clicks "Create Backup" on the Operations page, the backup is
initiated via `POST /v1/backup` and the frontend connects an `EventSource`
(SSE) to `/v1/backup/stream/{backup_id}` to show real-time progress.

The SSE connection and backup operation ID are stored as plain JS variables
on the `backup` object:

```javascript
backup._activeOperationId = data.backup_id;  // plain JS var
backup._startSSE(data.backup_id);             // EventSource in JS memory
```

If the user **refreshes the page** (or navigates away and back using the
SPA client-nav pattern that does `loadContent()`), all JS state is reset:

1. `backup._activeOperationId` → `null`
2. `backup._eventSource` → `null`
3. The progress card (`#backup-progress`) is hidden (default `display:none`)
4. No code reconnects the SSE stream

The database still correctly records the operation's `status = "creating"`,
but the UI never checks for it on initial load.

## Why it was missed

- The SSE connection was designed for the "happy path" — start a backup,
  watch it complete, done.
- Page refresh during a long-running background operation wasn't considered.
- The `_startSSE` method is only called from `backup.create()` (user-initiated)
  and `backup.previewRestore()` (restore flow).

## Fix

Added `backup.checkForActiveOperation()` to the ops page JS:

```javascript
checkForActiveOperation: function() {
  if (backup._eventSource) return; // already connected
  fetch('/v1/backup').then(function(resp) {
    if (!resp.ok) return;
    resp.json().then(function(backups) {
      var active = null;
      for (var i = 0; i < backups.length; i++) {
        if (backups[i].status === 'creating') {
          active = backups[i];
          break;
        }
      }
      if (active) {
        backup._activeOperationId = active.backup_id;
        backup._startSSE(active.backup_id);
      }
    });
  });
}
```

Called 1500ms after initial page load (allowing the backup list to render):

```javascript
setTimeout(function() { backup.checkForActiveOperation(); }, 1500);
```

## See also

- [[Sessions/2026-06-27-backup-sse-reconnection|Backup SSE Reconnection on Page Refresh]] — session log
