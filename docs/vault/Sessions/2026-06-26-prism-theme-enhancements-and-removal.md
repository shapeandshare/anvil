---
title: Prism Theme — Enhancements & Removal
type: session-log
tags:
  - type/session-log
  - domain/ui
created: '2026-06-26'
updated: '2026-06-26'
source: agent
aliases:
  - Prism Theme — Enhancements & Removal
related:
  - Sessions/2026-06-20-unicorn-theme-and-prism-vibrancy
  - Discoveries/radial-gradient-center-bloom-for-theme-overlays
---

# Session: Prism Theme — Enhancements & Final Removal

**Date**: 2026-06-26
**Status**: Draft

## Context

The user made iterative requests about the Prism theme over multiple rounds. Starting from a complaint that the prism "does not rotate through or do something visually unique", the session progressed through enhancement rounds and ended with the theme's removal.

## What Was Done

### Round 1 — Continuous Hue Rotation

The prism theme's `--hue` was static (only bumped on training milestones/completions). Added a `requestAnimationFrame` loop to `prism.js` that continuously drifts the hue through the full color spectrum:

- **Rotation speed scales with `--prism` intensity**: low loss (high prism) = faster swirl
  - `prism=0` → 360°/120s (barely perceptible)
  - `prism=0.3` → 360°/39s (original default)
  - `prism=1` → 360°/15s (fast at convergence)
- Training events (milestones +45°, complete +60°) still cause instant hue jumps on top of the continuous drift
- Respects `prefers-reduced-motion: reduce` (disables the animation frame)
- Respects paused state
- Proper teardown (cancels animation frame on theme switch)

### Round 2 — Brightness Boost (3 iterations)

"more" → "more" aggressive brightness boosts across all visual parameters:

| Parameter | Start | Mid | Final |
|-----------|-------|-----|-------|
| `--prism` baseline | 0.3 | 0.5 | 0.7 |
| Dark opacity | `0.05 + prism×0.28` | `0.08 + prism×0.32` | `0.15 + prism×0.35` |
| Light opacity | `0.06 + prism×0.20` | `0.08 + prism×0.28` | `0.15 + prism×0.32` |
| HSL lightness range | 48-60% | 55-68% | 68-78% |
| Dark saturate | 1.3 | 1.5 | 1.8 |
| Light saturate | 1.2 | 1.4 | 1.6 |
| Flash peak opacity | 0.65 | 0.78 | 0.92 |
| Flash peak saturate + brightness | 1.8×1.3 | 2.0×1.5 | 2.5×1.8 |

### Round 3 — Center Bloom (radial-gradient overlay)

The diagonal `linear-gradient` left the screen center washed out (all stops blended together). Added a `radial-gradient` layer on top to concentrate a bright prismatic bloom in the middle of the viewport:

```css
background:
  radial-gradient(
    ellipse 70% 60% at 50% 50%,
    hsl(calc(var(--hue, 0) + 30),  100%, 88%) 0%,
    hsl(calc(var(--hue, 0) + 120), 100%, 75%) 25%,
    hsl(calc(var(--hue, 0) + 240), 100%, 62%) 50%,
    transparent 72%
  ),
  linear-gradient(135deg, ...);
```

Applied to all states: dark, light, flash 0%, flash 100%.

### Round 4 — Removal

The user requested the theme be removed entirely. Deleted:

- `anvil/api/static/css/themes/prism.css`
- `anvil/api/static/js/themes/prism.js`
- Removed script include from `anvil/api/templates/base.html`
- Removed `"prism"` from `THEME_IDS` in `tests/system/test_theme_engine.py`
- Removed the `registerEffect('prism', ...)` particle effect from `anvil/api/static/js/theme/particle-system.js`

## Files Changed

```
Modified:
  anvil/api/static/js/themes/prism.js        (hue rotation, brightness baseline)
  anvil/api/static/css/themes/prism.css      (brightness, center bloom)
  anvil/api/templates/base.html              (removed prism script include)
  anvil/tests/system/test_theme_engine.py    (removed "prism" from THEME_IDS)
  anvil/api/static/js/theme/particle-system.js  (removed prism particle effect)
Deleted:
  anvil/api/static/css/themes/prism.css
  anvil/api/static/js/themes/prism.js
```

## Wikilinks

- [[Sessions/2026-06-20-unicorn-theme-and-prism-vibrancy]]
- [[Reference/theme-creation-guide]]
- [[Reference/particle-effect-authoring]]
