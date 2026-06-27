---
aliases:
  - Aurora Starfield 2026-06-26
created: '2026-06-26'
domain: ui
related:
  - Discoveries/csp-blocks-dynamic-style-injection
source: agent
tags:
  - type/session-log
  - domain/ui
title: Aurora Starfield Implementation
type: session-log
updated: '2026-06-26'
---
# Session: Aurora Starfield Implementation

**Date**: 2026-06-26
**Status**: Draft

## Summary

Attempted to add a starry night-sky background to the aurora theme across 5 failing approaches before discovering that CSP nonce restrictions block dynamically injected `<style>` elements. The final working approach creates a real `<div>` DOM element with inline styles via `element.style.cssText`, bypassing CSP entirely.

The starfield uses 50 `radial-gradient` layers (1–2.5 px dots at percentage-based positions) on a `position: fixed; z-index: 0` element, visible through the transparent `.app-shell` background.

## Approaches Attempted

| # | Approach | File | Result |
|---|---|---|---|
| 1 | `::before` + `box-shadow` (1 px element) | `aurora.css` | Failed — box-shadows on a tiny element unreliable |
| 2 | `background-image` on `.app-shell` | `aurora.css` | Failed — cascade conflict with base.css shorthand |
| 3 | `background` shorthand on `.app-shell` | `aurora.css` | Failed — cascade conflict persisted |
| 4 | `::before` + `background: radial-gradient()` | `aurora.css` | Failed — possibly CSP blocking CSS file |
| 5 | Injected `<style>` via `auroraMapping` callback in `aurora.js` | `aurora.js` | Failed — CSP blocks injected `<style>` AND mapping never fires (theme manager runs before themes register) |
| 6 | Injected `<style>` via IIFE body in `aurora.js` | `aurora.js` | Failed — CSP blocks injected `<style>` |
| **7** | **Real `<div>` DOM element with inline `style.cssText`** | `aurora.js` | **Success** — bypasses CSP, renders immediately |

## Root Causes

### CSP Nonce Restriction
The server applies a Content Security Policy that requires a `nonce` attribute on `<style>` elements. All static `<link>` stylesheets load without nonces and work — but dynamically created `<style>` nodes are silently dropped by the browser. This was the first time CSP blocked a frontend change in this project, making it a non-obvious failure mode.

### Theme Manager Script Order
`theme-manager.js` loads in `<head>` (via `<script>` tags) **before** any theme files (`aurora.js`, etc.). Theme registration with `window.ThemeRegistry.register()` stores configs, but the `mapping` callback may never be invoked for the active theme because the manager finished executing before any themes were registered. The `--calm` and `--flow` CSS variable defaults come from `aurora.css` (set via `data-skin` attribute), not from the mapping function.

### box-shadow Technique Limitation
The box-shadow technique requires the element to be tiny (1×1 px) for each shadow to render as a dot. When the element fills the viewport (`inset: 0`), each shadow copies the full viewport shape, creating overlapping rectangles instead of points.

## Final Implementation

**`anvil/api/static/js/themes/aurora.js`**:
- IIFE-injected starfield element at lines 12–75 (runs immediately on script load)
- 50 `radial-gradient` layers: sizes 1–2.5 px, opacities 0.3–0.85
- Percentage-based positions (e.g., `at 5% 12%`) — scales to any viewport
- Element: `position: fixed; z-index: 0` — root stacking context, below `.app-shell` (z-index: 2)
- Teardown removes element by ID when switching themes
- Light mode would use muted gray tones (not yet implemented in JS; CSS was reverted)

**`anvil/api/static/css/themes/aurora.css`** — reverted to original 74-line state (no starfield additions)

## Key Lessons

1. **CSP blocks dynamic `<style>` injection** — use real DOM elements with `element.style.cssText` for inline styles
2. **Theme manager runs before themes** — don't rely on `mapping` callbacks for active-theme setup; use IIFE body checks
3. **box-shadow starfield requires a tiny element** — not suitable for full-viewport pseudo-elements
4. **`radial-gradient` multi-layer backgrounds work** when applied via inline styles on real DOM elements
5. **Multi-layer `background` shorthand** replaced by `background-image` due to cascade with base.css — using a separate `::before` element with its own `background` avoids this

## Files Modified

```
Modified:
  anvil/api/static/js/themes/aurora.js           — Starfield DOM element injection
```

## Wikilinks

- [[Discoveries/csp-blocks-dynamic-style-injection]]
- [[Discoveries/theme-mapping-excited-fake-metrics-grad-norm]]
- [[Reference/theme-creation-guide]]
