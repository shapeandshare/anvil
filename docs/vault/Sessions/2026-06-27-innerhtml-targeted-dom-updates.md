---
title: Replace innerHTML rebuilds with targeted DOM updates
type: session-log
tags:
  - type/session-log
  - domain/ui
  - domain/operations
  - domain/performance
created: '2026-06-27'
updated: '2026-06-27'
status: draft
source: agent
aliases: innerHTML-to-targeted-dom
---

# Replace innerHTML Rebuilds with Targeted DOM Updates

**Session**: Replaced every `element.innerHTML = fullHtmlString` polling/refresh
cycle across all 8 template files with change-detected, in-place DOM patching
via a new `dom.js` utility. Eliminates flicker, animation re-triggers, and
focus loss.

## What was done

### `dom.js` utility library
- **Change-detected setters**: `dom.setText`, `dom.setHtml`, `dom.setClass`,
  `dom.updateBadge`, `dom.setAttr`, `dom.setDisabled`, `dom.setVisible` —
  every function compares old vs new before mutating.
- **In-place keyed reconciliation**: `dom.syncTableBody` and `dom.syncList`
  use `insertBefore`-based in-place reordering instead of detach→fragment→
  reappend. This preserves focus, caret position, and directly-bound event
  listeners on reused nodes.
- **Non-keyed children survive**: Placeholder rows, detail rows, and
  separators without `data-key` attributes are left untouched.
- **Key validation**: Empty/null keys throw explicitly. `Map`/`Set` used
  instead of plain objects to avoid `__proto__` pollution.
- **`setAttr` normalization**: Non-string values are stringified before
  comparison, avoiding redundant attribute sets.

### Templates refactored (8 files)

| File | Old pattern | New pattern |
|------|-------------|-------------|
| **operations.html** | 3 polling loops (10-15s) rebuilt full tables | `dom.syncTableBody` + per-field `dom.setText` |
| **datasets.html** | Full list rebuilds on create/delete | `dom.syncTableBody` with dataset/corpus/combined tables |
| **training.html** | 12+ innerHTML sites | `dom.setHtml` + `dom.syncList` for run history |
| **experiment.html** | row.innerHTML loop | `dom.syncTableBody` for runs + artifacts |
| **models.html** | row.innerHTML loop | `dom.syncTableBody` for model list |
| **model_detail.html** | Single innerHTML rebuild | 11 targeted `dom.setText` calls |
| **playground.html** | Select/table rebuilds | `dom.syncList` for model/version selects |
| **dataset_curation.html** | Sample/op list rebuilds | `dom.syncTableBody` with keyed rows |

### Bugs found & fixed
- **6 double-escaping regressions**: `escHtml()` result passed to
  `textContent`/`dom.setText` (which auto-escapes) → `Tom &amp; Jerry`
  displayed literally. Fixed across datasets.html, model_detail.html,
  experiment.html, dataset_curation.html.
- **Step-0 truthiness bug**: `d.step || '—'` failed when step=0 (falsy).
  Fixed in 3 locations in training.html.
- **Corpus detail-row orphan on delete**: Non-keyed detail rows survived
  reconcile but weren't pruned when their parent corpus was deleted.
  Added orphan pruning + reposition after parent row.
- **updateBadge design flaw**: Was stripping all non-badge classes (hooks,
  size classes). Now only manages `badge-*` color classes.
- **Clear-text protocol in MLflow URL**: `http://` fallback → uses
  `window.location.protocol` for mixed-content safety.

### CI fixes
- **SSE test resilience**: `test_forge_ahead_starts_training` now accepts
  either live SSE metrics OR the FINAL completion marker. Training with
  `local-stdlib` engine (5 steps) completes before the browser renders
  the first SSE metric event.
- **Removed `xfail` marker**: The test that was marked as pre-existing
  flake now passes consistently.
- **CSP compliance**: Replaced inline `onclick` handlers with `data-*`
  attributes + event delegation (merged from PR #203).
- **Test timeout increased**: 15→20 min to accommodate Docker CI latency.

## Key files

- **New utility**: `anvil/api/static/js/dom.js`
- **Templates**: `anvil/api/templates/{operations,datasets,dataset_curation}.html`
  and `anvil/api/templates/archetypes/{training,experiment,models,model_detail,playground}.html`
- **Test**: `tests/browser/test_training_sse_wiring.py`
- **CI workflow**: `.github/workflows/ci-workflow.yml`
