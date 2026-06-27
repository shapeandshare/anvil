---
aliases:
  - Hyperspace Login Stacking Fix
created: '2026-06-26'
related:
  - Discoveries/hyperspace-surface-rush-login-stacking
  - Discoveries/isolation-isolate-stacking-context-paint-order
  - Discoveries/nav-bar-z-index-positioned-content-stacking
  - Sessions/2026-06-26-hyperspace-grid-floor-animation-fix
source: agent
tags:
  - type/session-log
  - domain/ui
title: Hyperspace Surface Rush — Login Page Stacking Fix
type: session-log
updated: '2026-06-26'
---
# Session: Hyperspace Surface Rush — Login Page Stacking Fix

**Date**: 2026-06-26
**Status**: Draft

## Summary

Fixed the hyperspace theme's "surface rush" particle effect (`.app-main::after`) rendering on top of the login card. The root cause is a non-obvious CSS stacking behavior: a `position: fixed; z-index: 0` pseudo-element on a parent with `position: relative; z-index: auto` paints **after** the parent's child content in the parent's stacking context.

## Root Cause

`.app-main` has `position: relative` but no explicit `z-index` (so `z-index: auto`). It does NOT establish a stacking context. Its `::after` pseudo-element has `position: fixed; z-index: 0`, which creates a stacking context at z-index 0 within `.app-shell`'s stacking context. Since `::after` is generated as the last child of `.app-main`, and both the login card (child content) and `::after` are at the same z-index level in `.app-shell`'s context, `::after` paints **on top** of the login card.

## Fix

Added `[data-skin="hyperspace"] .app-main:has(.login-page)::after, [data-skin="hyperspace"] .app-main:has(.login-page)::before` to the existing theme override rule in `login.css` (which already handled the grid theme). This hides the pseudo-elements when the login page is shown with the hyperspace theme active.

## Files Modified

```
Modified:
  anvil/api/static/css/login.css   — added hyperspace to theme override rule
```

## Wikilinks

- [[Discoveries/hyperspace-surface-rush-login-stacking]]
- [[Discoveries/isolation-isolate-stacking-context-paint-order]]
- [[Discoveries/nav-bar-z-index-positioned-content-stacking]]
