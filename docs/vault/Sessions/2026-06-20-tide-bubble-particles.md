---
aliases:
  - Tide Bubble Particles
created: '2026-06-20T00:00:00.000Z'
source: agent
tags:
  - type/session-log
  - domain/ui
title: 'Session: Tide Bubble Particles'
type: session-log
updated: '2026-06-20T00:00:00.000Z'
---
# Session: Tide Bubble Particles

**Date**: 2026-06-20
**Status**: Completed

## Summary

Replaced the Tide theme's particle effect with rising air bubbles that float to the top of the viewport and sway in time with the wave ripples, then tuned them to be sparser and slower. Along the way, documented the previously-undocumented canvas particle-system authoring layer in a new Reference note.

## Changes

### New `bubble` particle effect

**File**: `anvil/api/static/js/theme/particle-system.js`

Added a `bubble` effect registered immediately after the existing `spray` effect. Bubbles spawn below the waterline and rise to the top, recycling from the bottom once they pass off-screen. The defining behavior is that their **horizontal sway frequency and amplitude both derive from `--surge`** — the same CSS variable Tide publishes from `tokens_per_sec` and that drives the CSS wave-swell animation speed in `tide.css` (`calc(14s - var(--surge) * 9s)`). Because the canvas sway and the CSS ripple read the same signal, the bubbles sway in tempo with the visible ripples rather than drifting independently. Each bubble renders as a translucent body, a brighter rim ring, and a small specular glint, with per-bubble phase offsets and horizontal edge-wrapping.

### Tide points at the new effect

**File**: `anvil/api/static/js/themes/tide.js`

Changed `particleConfig` from `{ type: 'spray' }` to `{ type: 'bubble' }`. No other theme changes; the mapping that publishes `--surge`/`--level` was already in place.

### Tuning pass — fewer and slower

Per follow-up feedback, lowered the population (`BASE` 28→10, `MAX` 140→55), the rise speed (`0.4 + sig*0.9` → `0.18 + sig*0.42`), and the sway frequency/amplitude (both roughly halved). The structural pattern was untouched — only the `BASE`/`MAX` pair and the `base + sig * range` coefficients changed.

### Incidental fix

While editing the adjacent `spray` effect, added the `ph` field its `create()` was missing. `spray.update` already referenced `q.ph`, so the term was evaluating `Math.sin(... + undefined)` → `NaN` and silently freezing spray's horizontal jitter. Now correct (though `spray` is no longer referenced by any theme).

## Key Techniques

1. **Signal-synced canvas + CSS** — driving a canvas particle effect and a CSS keyframe animation from one shared CSS custom property (`--surge`) makes independent layers move in visual lockstep.
2. **Tuning by coefficient, not structure** — density and speed are `BASE + sig*(MAX-BASE)` and `base + sig*range`; making an effect calmer is a matter of shrinking both ends of each pair.

## Files Modified
- `anvil/api/static/js/theme/particle-system.js` — added `bubble` effect (+ `ph` fix on `spray`)
- `anvil/api/static/js/themes/tide.js` — `particleConfig` → `{ type: 'bubble' }`

## Vault
- New: [[Reference/particle-effect-authoring]] — documents the `registerEffect`/`particleConfig` contract and the `readSignal` idle-baseline behavior (a gap not covered by [[Reference/theme-creation-guide]])
- Cross-linked from [[Reference/theme-creation-guide]]

## Tests / Verification
- `lsp_diagnostics` clean on `particle-system.js` for the new code (remaining hints are pre-existing unused-var warnings in other effects)
- No system test asserts a particle `type` string; `tests/system/test_theme_engine.py` only checks that `tide.js` exists and is registered, which is unchanged
- `spray` effect remains registered, so the effect registry is intact

## See Also
- [[Reference/particle-effect-authoring]]
- [[Reference/theme-creation-guide]]
- [[Reference/css-data-uri-animated-svg-sprite]]
