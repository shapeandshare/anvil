---
title: 'Session: Firefly Tuning (Old Growth) + Tide Wave Shimmer'
type: session-log
tags:
  - type/session-log
  - domain/ui
created: '2026-06-20T00:00:00.000Z'
updated: '2026-06-20T00:00:00.000Z'
source: agent
aliases:
  - Firefly Tuning + Tide Shimmer
---
# Session: Firefly Tuning (Old Growth) + Tide Wave Shimmer

**Date**: 2026-06-20
**Status**: Completed

## Summary

Two UI polish tasks on behavioral themes, both CSS/JS-only with no engine changes:

1. **Old Growth** — Rewrote its particle effect from falling green "leaf" motes into **blinking fireflies that drift across the screen**, then iteratively tuned count, speed, meander, and twinkle through several user rounds. Surfaced and fixed a non-obvious perceived-speed bug.
2. **Tide** — Replaced the hard diagonal striped band at the bottom of the page with a **soft, layered wave shimmer**.

## Part 1 — Old Growth Fireflies

**File**: `anvil/api/static/js/theme/particle-system.js` (the `leaf` effect, ~line 777)

The Old Growth theme registers `particleConfig: { type: 'leaf' }` and drives the `--disturbance` CSS var (grad_norm + rolling loss stddev). The `leaf` effect is used **exclusively** by Old Growth, so it was repurposed in place — the registered name `leaf` was kept so `particleConfig` and any saved `theme:particle` localStorage prefs stay valid. No other theme, registration, or test references `leaf`.

### Visual rewrite (leaf → fireflies)

- Three stacked `hsla` circles per firefly (soft halo → mid glow → bright core), yellow-green hue ~70–92°.
- `ctx.globalCompositeOperation = 'lighter'` (wrapped in `save`/`restore`) for warm additive bloom where fireflies overlap.
- Independent per-firefly blink, horizontal crossing, vertical bob.
- Count + flight speed + blink rate scale with `--disturbance`.

### Iterative tuning (multiple user rounds)

- "reduce the number slightly" → `BASE` 18→12, `MAX` 70→48.
- "move slower, meander more, twinkle in/out more often" → first pass.
- "meander longer horizontally, twinkle slower/less flashy, slower overall, eventually cross the screen" → widened wander, swapped sharp `sin²` blink for a smooth remapped sine (`sin*0.5+0.5`) with a raised dim floor so they never fully snap off; kept a small persistent `vx` net drift so they always traverse the screen.
- "slower" ×3 → progressively halved all time-based frequencies.
- **"crazy but they look much faster now"** → diagnosed the velocity-accumulation bug (see Discovery below) and refactored the motion model.
- "much closer, now speed them up" → raised frequencies ~2.2× while keeping wide meander amplitudes.

### The key fix (full detail in Discovery)

The wander oscillation was being **added to position every frame** (`q.x += sin(...) * wanderA`), making amplitude behave as velocity. Raising amplitude for "more meander" made them faster. Fixed by modeling motion as a **slowly-drifting base position (`bx`, only `vx` accumulates) + a bounded positional sway** (`x = bx + sin-sum`), with edge-wrap on `bx`. This decouples path width (amplitude) from speed (frequency).

→ [[Discoveries/canvas-particle-amplitude-vs-frequency-perceived-speed|Canvas Particle: Amplitude vs Frequency Perceived-Speed Trap]]

## Part 2 — Tide Wave Shimmer

**File**: `anvil/api/static/css/themes/tide.css` (the `.app-main::before` layer)

**Before**: A `repeating-linear-gradient` at 115° — sharp-edged diagonal cyan stripes (transparent 28px / cyan 4px) sliding sideways via `tide-swell`. Read as a static screen-door / barber-pole texture, clashing with the soft water gradient (`::after`) below.

**After**: Three overlapping soft `radial-gradient` blobs (cyan + teal) anchored at the bottom edge, drifting horizontally past each other at different rates/directions so their overlap forms shifting, organic highlight crests — like light on a water surface.

- Feathered edges (radial gradients fade to transparent) → no banding.
- Vertical `mask-image` (transparent top → opaque bottom) so the shimmer emerges *from* the water and blends into the `::after` gradient instead of cutting off.
- `ease-in-out ... alternate` for a soft breathing sway; base period slowed to ~20s, still accelerates with `--surge`.
- Base opacity bumped `0.2`→`0.35` (soft gradients are subtler than the old hard stripes).

Preserved: `--level`/`--surge` height response, the `tide-swell` keyframe name, the riptide `::after` override (only touches `::after`), and the `prefers-reduced-motion` disable.

## Files Modified

- `anvil/api/static/js/theme/particle-system.js` — `leaf` effect rewritten + tuned
- `anvil/api/static/css/themes/tide.css` — `.app-main::before` + `tide-swell` keyframe

## Verification

- `lsp_diagnostics` clean (no errors) after each change to `particle-system.js`.
- No test references the `leaf` particle id or the tide `::before` band; `tide.js` untouched, so the theme registry contract is intact.

## Related

- [[Discoveries/canvas-particle-amplitude-vs-frequency-perceived-speed|Particle Perceived-Speed Trap]]
- [[Reference/theme-creation-guide|Theme Creation Guide]]
- [[Sessions/2026-06-20-nine-new-themes|Nine New Themes]]
- [[Sessions/2026-06-20-theme-square-grid-fixes|Theme Square-Grid Fixes]]
