---
aliases: []
created: '2026-06-23T00:00:00.000Z'
source: agent
tags:
  - type/session-log
  - domain/ui
title: 'Session: Theme Picker Dropdown Z-Index and Excited Mode Fix'
type: session-log
updated: '2026-06-23T00:00:00.000Z'
---

# Theme Picker Dropdown Z-Index and Excited Mode Fix

**Type**: session-log
**Tags**: type/session-log, domain/ui
**Created**: 2026-06-23
**Updated**: 2026-06-23

## Summary

Three related fixes to the theme picker dropdown and Old Growth excited mode:

1. **Dropdown background transparency** — `.theme-picker__grid` had no explicit background; items used `var(--surface)` without fallback
2. **Dropdown appears behind hero content** — `.nav-bar` z-index (1) competed with `.hero-actions` z-index (1) in same stacking context; later DOM order won
3. **Old Growth excited "on" acts like "off"** — fake metrics emission lacked `grad_norm`, the primary signal Old Growth's mapping consumes

## Changes

### 1. `.theme-picker__grid` background

**File**: `anvil/api/static/css/base.css`

Added `background: var(--surface)` to `.theme-picker__grid`. The scrollable grid container for theme items had no background, so even though `.theme-picker__menu` and each `.theme-picker__item` both used `--surface`, the grid's gap areas could appear transparent if CSS variable resolution had any edge-case timing issues.

### 2. `.nav-bar` z-index stacking

**File**: `anvil/api/static/css/base.css`

Bumped `.nav-bar` z-index from `1` to `10`.

**Root cause**: `.hero-actions` (position: relative; z-index: 1) participates in `.app-shell`'s stacking context alongside `.nav-bar` (position: relative; z-index: 1). Both at the same z-index level, but `.hero-actions` appears later in DOM → paints on top. The theme-picker dropdown (child of `.nav-bar`, z-index: 60 within nav-bar's context) escapes vertically into `.app-main`'s area, where `.hero-actions` covers it.

**Fix reasoning**: The nav-bar should always stack above page content. Bumping to 10 leaves room below for any future positioned content (toasts are at 9999).

### 3. Old Growth excited mode

**File**: `anvil/api/static/js/theme/theme-manager.js`

Added `grad_norm: 0.85` to the fake metrics event emitted in the excited 'on' block:

```js
// Before:
bus.emit('metrics', { tokens_per_sec: 600000, loss: 0.5 });

// After:
bus.emit('metrics', { tokens_per_sec: 600000, loss: 0.5, grad_norm: 0.85 });
```

**Root cause**: Old Growth's `mapping()` computes `--disturbance` primarily from `grad_norm` and secondarily from loss stddev. The fake metrics only carried a single stable loss value → zero stddev → zero disturbance → `setDisturbance(0)` identical to "off".

## Stacking Context Detail

Stacking order within `.app-shell` (position: relative; z-index: 2):

| Element | Z-Index | Paint Step | Note |
|---------|---------|------------|------|
| `.forge-glow-container` | 0 | Step 6 | Positioned, z-index: 0 |
| `.forge-embers` | 0 | Step 6 | Positioned, z-index: 0 |
| `.app-main` | auto | Step 6 | Positioned, z-index: auto |
| `.nav-bar` | **1→10** | Step 7 | Was competing with `.hero-actions` |
| `.forge-icon`, `.hero-title`, `.hero-tagline`, `.hero-subtitle`, `.hero-actions` | 1 | Step 7 | All at z-index: 1, later in DOM → paint above nav-bar |
| `.forge-glow-container` | 0 | Step 6 | |

Both `.nav-bar` and `.hero-actions` at z-index: 1 → `.hero-actions` wins via paint order. Fix: `.nav-bar` at z-index: 10.

## Files Changed

- `anvil/api/static/css/base.css` — `.theme-picker__grid` background added; `.nav-bar` z-index bumped to 10
- `anvil/api/static/js/theme/theme-manager.js` — `grad_norm` added to excited 'on' fake metrics

## Related

- [[Discoveries/nav-bar-z-index-positioned-content-stacking.md]] — Nav-bar stacking context competition with hero page positioned elements
- [[Discoveries/theme-mapping-excited-fake-metrics-grad-norm.md]] — Excited mode fake metrics need `grad_norm` for theme mappings that consume it
- [[Sessions/2026-06-23-hero-page-footer-stacking-and-layout]]
