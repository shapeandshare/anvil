---
aliases:
  - Tectonic Theme Overlay Removal + Undeclared Variable Fix
created: '2026-06-26'
source: agent
status: draft
tags:
  - domain/ui
  - type/session-log
title: Tectonic Theme Overlay Removal + Undeclared Variable Fix — 2026-06-26
type: session-log
updated: '2026-06-26'
---
# Tectonic Theme Overlay Removal + Undeclared Variable Fix

**Date**: 2026-06-26
**Context**: User reported the tectonic theme's two crossing fracture lines (`.app-main::after` with dual-angle `linear-gradient`) looked bad. After trying a glowing bottom fissure replacement (rejected), the overlay was removed entirely. A browser console error (`ReferenceError: shake is not defined`) surfaced in the `debris` particle effect, revealing a strict-mode undeclared variable bug.

## What Was Done

### 1. Removed tectonic theme's `.app-main::after` overlay

`anvil/api/static/css/themes/tectonic.css` — Removed both the normal-state crossing line gradients and the `[data-tectonic="rupture"]` state entirely. The tectonic theme now has no pseudo-element overlay. Its visual response to training instability is limited to the `tectonic-shake` animation (driven by `--tremor`) and the `debris` canvas particles.

The `data-tectonic="rupture"` attribute is still set by the JS mapping on divergence, but is now inert in CSS — the shake at max `--tremor` provides natural feedback.

### 2. Fixed undeclared `shake` variable in `debris` particle effect

`anvil/api/static/js/theme/particle-system.js` line 1536 — Added `shake` to the `var` declaration list. Same bug class as the previously-fixed `glow` in the `energy` effect: a variable introduced mid-development and never declared, throwing `ReferenceError` in strict mode.

## Files Changed

```
Modified:
  anvil/api/static/css/themes/tectonic.css         (removed .app-main::after overlay block, ~24 lines)
  anvil/api/static/js/theme/particle-system.js     (fixed undeclared shake variable in debris effect)
```

## Validation

- `lsp_diagnostics` clean on `tectonic.css` (only pre-existing `!important` warnings in `prefers-reduced-motion` block)
- `particle-system.js` fix verified by inspection — variable declaration is now correct
- Tectonic theme no longer has a pseudo-element overlay; `--tremor` still drives the shake animation and debris particle count/opacity

## Notes / Follow-ups

- The `debris` effect now has the same `var i, q, tc, glow, shake;` pattern as the `biolum` effect — all effect variables properly declared.
- Consider adding a script or CI check to catch undeclared variable assignments in `particle-system.js` — two occurrences of the same bug class have now been found.

## Wikilinks

- [[Discoveries/particle-effect-strict-mode-undeclared-shake]]
- [[Discoveries/particle-effect-strict-mode-undeclared-glow]]
- [[Discoveries/css-transform-breaks-position-fixed-modal]]
- [[Reference/theme-creation-guide]]
- [[Sessions/2026-06-20-nine-new-themes]]
