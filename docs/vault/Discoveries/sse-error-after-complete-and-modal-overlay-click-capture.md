---
title: SSE error event fires after successful complete, and stale modal overlay captures clicks
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
  - sse-error-after-complete-and-modal-overlay-click-capture
code-refs:
  - anvil/api/templates/operations.html
  - anvil/api/static/css/components.css
---

# SSE Error-After-Complete and Stale Modal Overlay Click Capture

**Discovered**: 2026-06-27  
**Context**: `anvil/api/templates/operations.html` — `_startSSE` and `confirmModal`; `components.css` — `.modal-overlay--closing`  
**Severity**: P2 (functional — notification history button appears broken after backup)

## Bug 1: SSE `error` fires after successful `complete`

### The bug

When the backup server finishes successfully and closes the EventSource connection, the browser fires **both** the `complete` event and an `error` event. The browser treats any connection close from the server as a transport error, so the `error` handler runs even after a successful completion.

This causes two problems:

1. **Conflicting toasts**: `complete` handler calls `toast('Operation completed successfully', 'success')`, then the `error` handler calls `toast('Operation encountered an error', 'error')` — the error toast visually overrides the success toast.
2. **Unnecessary load**: `backup.loadAll()` is called twice, causing a redundant re-fetch and re-render of the backup table.

```javascript
// The sequence:
es.addEventListener('complete', function(e) {
    toast('Operation completed successfully', 'success');  // ✅ runs first
    backup.loadAll();
});

es.addEventListener('error', function(e) {
    toast('Operation encountered an error', 'error');      // ❌ also runs
    backup.loadAll();                                       // ❌ redundant
});
```

### Why it happened

- The `EventSource` specification requires the browser to fire an `error` event whenever the connection is terminated, regardless of the server's intent. A server-initiated close after a `complete` event is indistinguishable from a network error at the transport level.
- The original implementation didn't account for this dual-event sequence.

### Fix

Added a `backup._operationResolved` flag:

```javascript
_startSSE: function(operationId) {
    backup._operationResolved = false;       // reset for each operation
    // ...
    es.addEventListener('complete', function(e) {
        backup._operationResolved = true;    // mark resolved
        toast('Operation completed successfully', 'success');
        backup.loadAll();
    });

    es.addEventListener('error', function(e) {
        if (backup._operationResolved) return;  // skip if already completed
        // ... normal error handling ...
    });
}
```

## Bug 2: Stale confirm modal overlay intercepts clicks during 250ms close animation

### The bug

The `backup.confirmModal` function's `close()` adds a `.modal-overlay--closing` CSS class and schedules `overlay.remove()` via `setTimeout(250)`. During that 250ms window, the overlay remains in the DOM with `position: fixed; inset: 0; z-index: 10000;` — it intercepts **all clicks** even while visually fading out.

The notification history button (🔔) in the backup actions bar is particularly affected: users who click it immediately after confirming a backup action find the button "unresponsive" because the fading overlay catches the click instead.

### Why it happened

- The CSS animation (`modal-overlay-out`) fades the overlay to `opacity: 0` over 200ms, but the `animation-fill-mode: both` only affects visual rendering — the element still has full click-capture geometry.
- The 250ms `setTimeout` before DOM removal creates a window where the invisible overlay blocks interaction.

### Fix

Added `pointer-events: none` to `.modal-overlay--closing` in `components.css`:

```css
.modal-overlay--closing {
  animation: modal-overlay-out 0.2s var(--ease) both;
  pointer-events: none;  /* ← allow clicks to pass through during close */
}
```

## Impact

- Bug 1 causes a confusing "error" toast to appear after every successful backup operation, creating the impression that backups fail.
- Bug 2 makes the notification history button (and any other interactive element under the overlay) appear broken when clicked shortly after dismissing a confirm modal.
- Together, these bugs contribute to a poor UX on the Operations page after backup operations.

## Similar patterns to check

- Any other page that uses `confirmationModal()` with the same `setTimeout`-based close pattern
- SSE streams elsewhere in the codebase (e.g., training SSE) — check if `error` event handlers have the same unresolved-completion issue

## See also

- [[Sessions/2026-06-27-backup-sse-error-overlay-fix|Backup SSE Error-After-Complete and Modal Overlay Fix]] — session log
- [[Discoveries/backup-row-actions-not-rendered|Backup row actions silently discarded in `_updateBackupRow`]] — related backup UI fix