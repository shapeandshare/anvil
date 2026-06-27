---
title: Ash Theme — Dense Training Attempts & Black Rain
type: session-log
tags:
  - type/session-log
  - domain/ui
created: '2026-06-26'
updated: '2026-06-26'
source: agent
related:
  - Discoveries/css-multi-background-position-parallax
  - Discoveries/multi-layer-radial-gradient-rain-failure
  - Reference/theme-creation-guide
  - Reference/particle-effect-authoring
aliases:
  - Ash Dense Training Black Rain
  - Ash Theme Overhaul 2026-06-26
---
# Session: Ash Theme — Dense Training Attempts & Black Rain

**Date**: 2026-06-26
**Status**: Draft

## Summary

Attempted to make the Ash theme's soot significantly denser during training and add a "black rain" effect. Multiple approaches were tried and reverted. The final surviving change is a modified `--ash` mapping formula in `ash.js` that offsets training values to always produce ash ≥ 0.5 (vs idle 0.3). The black-rain canvas effect was registered in `particle-system.js` but ultimately the Ash theme's `particleConfig` was reverted back to `type: 'css'` (no canvas effect).

A UI consistency observation was noted: the Ash theme's content blocks on hero pages use `--glass-bg` (transparent) while the login panel uses a solid background.

## Changes

### `anvil/api/static/js/themes/ash.js` — Mapping formula (kept)
- Original: `setVar('--ash', clamp01(m.loss / L0).toFixed(3))`
  - Loss=0 → ash=0, which is below idle (0.3), so soot becomes less visible when training starts
- Final: `setVar('--ash', (0.5 + clamp01(m.loss / L0) * 0.5).toFixed(3))`
  - Any training loss produces ash ≥ 0.5, scaling to 1.0 at max loss
  - Idle remains at 0.3 (unchanged)
  - `L0` and `clamp01` preserved for loss calculation

### `anvil/api/static/css/themes/ash.css` — REVERTED
- All attempts to increase particle count (19→26), bump opacity/speed formulas, widen dynamic range, and lower `--ash` default were reverted
- Back to original: 19 particles, `--ash: 0.3`, original opacity/speed formulas

### `anvil/api/static/js/theme/particle-system.js` — Black-rain effect (kept, unused)
- Registered `'black-rain'` canvas effect: 200–700 dark charcoal streaks falling vertically
- Driven by `--ash-rain` signal (only set during training metrics)
- Includes training gate: checks inline `--ash-rain` style before rendering
- Effect remains registered but no theme currently uses it (Ash reverted to `type: 'css'`)

## Mapping Approaches Attempted (all reverted)

| Approach | Formula | Result |
|---|---|---|
| Linear offset ×0.7 | `0.3 + raw * 0.7` | Not dense enough |
| Linear offset ×0.85 | `min(1, 0.3 + raw * 0.85)` | "No improvement" |
| Power curve ^0.3 | `max(0.3, pow(raw, 0.3))` | "No improvement" |
| Power curve ^0.15 | `max(0.3, pow(raw, 0.15))` | "No improvement" |
| Flat 0.8 | `setVar('--ash', '0.8')` | "No longer have a training mode" |
| Offset 0.5 + 0.5×raw | `0.5 + raw * 0.5` | Current (kept) — still "training doesnt look different then idle" |

## Observations

- The `bus.emit('metrics')` only fires once in the codebase (theme preview at `theme-manager.js:136` with `loss: 0.5`)
- No SSE or training-loop JS-side metrics emission was found in `static/js/` — training metrics may be delivered server-side
- The user could not perceive visual changes despite multiple formula iterations, suggesting either:
  a. The rendering pipeline (CSS `var(--ash)` resolution) may not update dynamically during animation
  b. The opacity/speed differences may be too subtle perceptually
  c. Browser caching may have prevented updated JS from loading

## Files Modified (final state)

```
Modified:
  anvil/api/static/js/themes/ash.js           — Mapping formula offset
  anvil/api/static/js/theme/particle-system.js — Black-rain effect registered (unused)
```

## Wikilinks

- [[Discoveries/css-multi-background-position-parallax]]
- [[Discoveries/multi-layer-radial-gradient-rain-failure]]
- [[Reference/theme-creation-guide]]
- [[Reference/particle-effect-authoring]]
