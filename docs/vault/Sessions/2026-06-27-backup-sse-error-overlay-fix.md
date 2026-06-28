---
title: 'Session: Backup SSE Error-After-Complete and Modal Overlay Fix'
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
  - backup-sse-error-overlay-fix
---

# Session: Backup SSE Error-After-Complete and Modal Overlay Fix

**Date**: 2026-06-27
**Trigger**: User reports that after receiving a backup notification on the Operations page, the notification history button (🔔) stops responding to clicks and notifications never appear in the history list.

## What was done

### 1. Root cause analysis — two interacting bugs

Investigated the Operations page (`operations.html`) and component CSS to trace the user's reported symptoms:

- **"Button stops responding to clicks"** — Traced to the backup confirm modal's `close()` function leaving a transparent overlay (`z-index: 10000`) on the page for 250ms during its close animation. Clicking any element under the overlay during that window is intercepted.
- **"Notifications don't appear in the list"** — The `window._toastHistory` array was correctly populated by `toast()`, but the user could never trigger `openNotificationHistory()` because the overlay blocked the button click. The error toast from the SSE error-after-complete double-fire compounded the confusion.

### 2. SSE error-after-complete guard

Added `backup._operationResolved` flag:

- Reset to `false` at the start of each `_startSSE` call
- Set to `true` in the `complete` event handler
- Checked at the top of the `error` event handler — early return if already resolved

This prevents the browser from firing both `complete` and `error` handlers when the server closes the EventSource connection after a successful backup.

### 3. Stale modal overlay click-through

Added `pointer-events: none` to `.modal-overlay--closing` in `components.css` so the fading overlay allows clicks to pass through immediately, rather than blocking the UI for 250ms.

## Key files changed

| File | Changes |
|------|---------|
| `anvil/api/templates/operations.html` | Added `_operationResolved` flag; set in `complete` handler; checked in `error` handler |
| `anvil/api/static/css/components.css` | Added `pointer-events: none` to `.modal-overlay--closing` |

## Discovery notes

- [[Discoveries/sse-error-after-complete-and-modal-overlay-click-capture|SSE error event fires after successful complete, and stale modal overlay captures clicks]] — new

## Related

- [[Sessions/2026-06-27-backup-restore-ui-fixes-and-async-debt|Backup UI Fixes, Async Debt, Notification History]] — prior session that introduced the toast history system and confirm modal pattern
- [[Sessions/2026-06-27-backup-ui-csp-fixes|Backup UI CSP Fixes]] — prior session that refactored the operations page