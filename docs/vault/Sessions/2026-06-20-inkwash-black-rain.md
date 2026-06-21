---
aliases:
  - Inkwash Black Rain Session
created: '2026-06-20'
source: agent
status: draft
tags:
  - domain/ui
  - type/session-log
title: Inkwash Black Rain — 2026-06-20
type: session-log
updated: '2026-06-20'
---
# Inkwash Black Rain

**Date**: 2026-06-20

**Context**: User requested adding a "black rain" atmospheric effect to the Ink Wash theme. The rain should be visible at rest (no training run) and intensify with loss.

## Attempts

### Attempt 1: `background-size: 100% 200%` with 20 droplets

- `z-index: 1` on `.app-main::before`
- Percentage-based background-sizing meant only ~50% of droplets in viewport at any time
- Squared opacity curve (`--rain² × 0.45`): at baseline 0.4 → ~7% opacity
- **Result**: Invisible (user: "I don't see black rain")

### Attempt 2: Increased baseline + linear opacity

- Changed to `applyRain(0.4)` (baseline drizzle instead of 0)
- Flattened opacity to linear `--rain × 0.45`: baseline 0.4 → ~18%
- **Result**: Still invisible

### Attempt 3: Fixed 200×200px tile with 40 droplets

- Switched from percentage to fixed pixel tiling (Ash theme's pattern)
- `background-size: 200px 200px`, repeating
- Pixel-based animation from `0 0` to `0 -200px`
- Opacity `--rain × 0.55`: baseline ~22%
- **Result**: Still invisible

### Attempt 4: `.app-shell::before` with 49 droplets

- Moved to `.app-shell::before` (same as Hyperspace's working grid)
- `z-index: 0`, `background-size: 240px 240px`
- Opacity `--rain × 0.6`: baseline ~24%
- **Result**: Still invisible

### Attempt 5: Diagnostic — solid background

- Replaced `background-image` with `background: rgba(0, 0, 0, 0.12)` at `z-index: 999`
- **Result**: Faint dark tint visible (user uncertain)

### Attempt 6: Diagnostic — solid red

- `background: red` at `z-index: 999`
- **Result**: Full red screen confirmed (user: "all red")

### Attempt 7: Simple 5-droplet test

- 5 large ellipses (5×10px to 6×12px) at `z-index: 999`
- Much larger than earlier attempts, hard opacity values (0.6–0.9)
- **Result**: Pending user confirmation

## Root Cause Analysis

The pseudo-element mechanism works (proven by red overlay). The `background-image` with 40–49 `radial-gradient()` layers, each with two color stops and elliptical shapes, failed to produce visible output. Comparison with Ash's working soot pattern (~24 single-stop circular gradients) suggests the combination of:

- High layer count (40–49)
- Two-stop soft-edged gradients (fade to transparent)
- Tiny droplet sizes (1.5–2px × 2–5px)

…may exceed browser compositing limits or result in sub-pixel rendering too faint to perceive. See [[Discoveries/multi-layer-radial-gradient-rain-failure]].

## What Remains

The `--rain` CSS var and JS mapping (signal bus → `applyRain`) are wired and working. The approach needs fixing — likely fewer, larger droplets with hard edges, or a different mechanism (canvas particle, SVG filter, repeating pattern).

## Files Changed

```
Modified:
  anvil/api/static/css/themes/inkwash.css   — Rain pseudo-element (multiple approaches)
  anvil/api/static/js/themes/inkwash.js      — --rain signal mapping, baseline applyRain(0.4)
```

## Wikilinks

- [[Discoveries/multi-layer-radial-gradient-rain-failure]]
- [[Discoveries/static-css-no-cache-busting]]
- [[Reference/theme-creation-guide]]
- [[Decisions/ADR-031-behavioral-theme-engine]]
