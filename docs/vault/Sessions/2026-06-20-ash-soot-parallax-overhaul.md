---
aliases:
  - Ash Soot Parallax Overhaul
created: '2026-06-21T04:07:13.000Z'
updated: '2026-06-21T04:07:13.000Z'
source: agent
title: 'Session: Ash Theme — Embers to Falling-Soot Parallax'
type: session-log
tags:
  - type/session-log
  - domain/ui
related:
  - '[[Discoveries/css-multi-background-position-parallax]]'
  - '[[Reference/theme-creation-guide]]'
  - '[[Reference/particle-effect-authoring]]'
---
# Session: Ash Theme — Embers to Falling-Soot Parallax

**Date**: 2026-06-20
**Status**: Completed

## Summary

Reworked the **Ash** behavioral theme from its original warm cooling-ember motif into "black soot falling down." The signal mapping was inverted (high loss now drives heavy soot fall instead of loss cooling embers), and the atmospheric layer was rebuilt as a four-band CSS parallax particle field in a single `.app-main::after` pseudo-element. Two iterations were needed: the first was invisible (dark-on-dark), the second is a crisp, depth-layered, wind-swept soot field.

## Changes

### `anvil/api/static/css/themes/ash.css`

- **Palette** shifted from warm amber accents (`#e07840`) to cool ash grey (`#a09080`); text softened to match.
- **`::before`** — ash-haze gradient rolling in from the top (55vh), opacity driven by `--ash`.
- **`::after`** — four-band parallax soot field via the multi-`background-position` technique (see Discovery):
  - **NEAR** (300px tile) — large 3–3.5px bright sharp flecks (alpha to 0.90), fastest fall
  - **MID** (190px tile) — 1.5–2px medium grey soot
  - **FAR** (110px tile) — 1–1.5px dim specks
  - **DUST** (70px tile) — sub-pixel faint grain, slowest fall
  - Near:far speed ratio ≈ 4.3:1; one `soot-fall` keyframe scrolls each band by its own tile height.
  - `soot-sway` keyframe adds a ±12px horizontal wind oscillation on the whole element; element inset `-10%` so sway never reveals an edge.
  - Each `radial-gradient` ends in an explicit `transparent` stop → crisp flecks, not haze.
- **`[data-ash-state="ashfall"]`** (divergence) — brighter/bigger particles across all four bands, full opacity, 4s fall + 7s sway.
- Reduced-motion: both pseudo-elements hidden.

### `anvil/api/static/js/themes/ash.js`

- `--ember` → `--ash`; mapping inverted to `ash = clamp01(loss / L0)` (high loss = heavy fall).
- Divergence sets `data-ash-state="ashfall"` (was `"smoke"`).
- `previewHint` updated; `particleConfig` corrected to `{ type: 'css' }` (was `'ember'`, briefly mis-set to the unregistered `'soot'`).

## Key Techniques & Findings

1. **Multi-background-position parallax** — multiple `radial-gradient` layers in one element, each scrolled by its own tile height in a single keyframe, yields per-band fall speeds (true depth) from a single pseudo-element. Three parallel lists (`background-image` / `background-size` / keyframe `to`) must stay index-aligned. Captured in [[Discoveries/css-multi-background-position-parallax]].
2. **Dark-on-dark contrast trap** — soot is conceptually dark but must be authored *light* (catches ambient light) on a near-black background, with contrast in per-dot alpha and a high element-opacity floor, not a low element opacity.
3. **Unregistered `particleConfig.type` fallback** — `particle-system.js` silently treats an unknown effect name as `default` (CSS pseudo-elements, no canvas). Combined with the invisible CSS, this caused the initial "no effects." The original `ember` was a real canvas effect; the rebuilt theme is pure CSS, so `type: 'css'` is the correct declaration.

## Files Modified

- `anvil/api/static/css/themes/ash.css` — full rewrite (~165 lines)
- `anvil/api/static/js/themes/ash.js` — signal mapping + registration metadata

## Verification

- CSS brace/paren balance OK; all three parallax lists verified at 19 aligned entries (base and divergence states).
- `ash.js` parsed clean (no syntax errors).
- `tests/system/test_theme_engine.py` asserts only file existence and registration presence for `ash` — both unaffected; no `THEME_IDS` change needed (Ash already registered).
