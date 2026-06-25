---
aliases: []
created: '2026-06-23T00:00:00.000Z'
source: agent
tags:
  - type/discovery
  - domain/ui
title: Excited Mode Fake Metrics Need grad_norm for Grad-Norm-Driven Mappings
type: discovery
updated: '2026-06-23T00:00:00.000Z'
code-refs:
  - anvil/api/static/js/theme/theme-manager.js
---

# Excited Mode Fake Metrics Need `grad_norm` for Grad-Norm-Driven Mappings

**Type**: discovery
**Tags**: type/discovery, domain/ui
**Created**: 2026-06-23
**Updated**: 2026-06-23
**Status**: status/draft

## Summary

When excited mode is set to `'on'`, `theme-manager.js` emits a fake `metrics` bus event to simulate training activity. The original event only carried `loss: 0.5`. Theme mappings that derive their visual signal primarily from `grad_norm` (like Old Growth's `--disturbance`) produced zero response — making "on" visually identical to "off".

## The Problem

Excited mode emission in `bindMapping()`:

```js
bus.emit('metrics', { tokens_per_sec: 600000, loss: 0.5 });
```

Old Growth's mapping handler:

```js
// Primary path: grad_norm
if (m.grad_norm != null && isFinite(m.grad_norm)) {
    instability = clamp01(m.grad_norm);  // undefined → 0
}
// Secondary path: loss stddev (single value → zero variance)
if (typeof m.loss === 'number' && isFinite(m.loss)) {
    recent.push(m.loss);               // [0.5]
    instability = Math.max(instability, clamp01(stddev(recent) * 3));  // stddev([0.5]) = 0 → 0
}
setDisturbance(instability);  // 0 — "off" state
```

No `grad_norm` in the event → instability stays 0. A single loss produces zero stddev. Result: `setDisturbance(0)`.

## The Fix

Add `grad_norm` to the fake metrics:

```js
bus.emit('metrics', { tokens_per_sec: 600000, loss: 0.5, grad_norm: 0.85 });
```

Value `0.85` produces `clamp01(0.85) → 0.85` — high but not maxed, creating a visibly active but natural-looking disturbance.

## Lesson

Fake metrics for excited mode should include **all** signal fields that any theme mapping might consume. Currently consumed by mappings:
- `loss` — used by multiple themes for loss-based effects
- `grad_norm` — used by Old Growth for disturbance
- `tokens_per_sec` — informational, not consumed by any mapping

If a new theme mapping relies on a signal not in this list, excited 'on' will silently fail. Keep this list in sync when adding new signal-driven themes.

## Related

- [[Sessions/2026-06-23-theme-picker-dropdown-z-index-and-excited-fix]]
