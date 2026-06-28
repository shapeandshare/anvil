---
title: Backup row actions silently discarded in _updateBackupRow
type: discovery
tags:
  - type/discovery
  - domain/ui
created: '2026-06-27'
updated: '2026-06-27'
status: draft
source: agent
aliases:
  - backup-row-actions-not-rendered
code-refs:
  - anvil/api/templates/operations.html
---
# Backup Row Actions Silently Discarded in `_updateBackupRow`

**Discovered**: 2026-06-27  
**Context**: `anvil/api/templates/operations.html` — `_updateBackupRow` function  
**Severity**: P2 (functional bug — buttons never appeared)

## The bug

The `_updateBackupRow` function builds a string of action buttons (verify, restore, delete) but **never assigns it to the table cell**:

```javascript
_updateBackupRow: function(tr, b, index) {
    // Sets cells 0–4 correctly:
    dom.setText(tr.cells[0], b.backup_id);
    // ... cells 1, 2, 3, 4 ...

    // Builds actions HTML but DOES NOT assign:
    var actionsHtml = '';
    if (b.status === 'completed') {
        actionsHtml += '<button ...>verify</button> ';
        // ...
    }
    // ❌ missing: tr.cells[5].innerHTML = actionsHtml;
},
```

## Why it happened

- The function was introduced in the 2026-06-27 `innerHTML-to-targeted-dom` session as part of migrating from full `innerHTML` table rebuilds to targeted `dom.syncTableBody` reconciliation.
- `_createBackupRow()` (the creation counterpart) creates 6 `<td>` cells (indices 0-5), and `_updateBackupRow` correctly updates cells 0-4. Cell 5 (actions) was simply never populated.
- The `dom.syncTableBody` mechanism reuses existing `<tr>` elements and calls `_updateBackupRow` to refresh content. Since cell 5 was never populated, it remained empty from the initial `_createBackupRow` call (where `tr.innerHTML` includes an empty 6th `<td>`).

## Impact

Backup action buttons (verify, restore, delete) were **never rendered** for any backup — every backup row appeared with an empty actions column.

## Fix

Added the missing assignment:

```javascript
tr.cells[5].innerHTML = actionsHtml;
```

## Similar patterns to check

This pattern (build HTML string → forget to assign) is easy to miss when a function handles multiple cells. Other `_update*Row` functions in the codebase that use a similar pattern should be audited:
- `experiment.html` — `_updateRunRow`
- `models.html` — `_updateModelRow`
- `datasets.html` — similar table row updaters

## See also

- [[Sessions/2026-06-27-backup-restore-ui-fixes-and-async-debt|Backup UI Fixes, Async Debt, Notification History]] — session log
- [[Sessions/2026-06-27-innerhtml-targeted-dom-updates|innerHTML to targeted DOM updates]] — session that introduced `_updateBackupRow`
