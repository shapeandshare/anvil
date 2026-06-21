---
title: 'Session: Loom Thread Particle Redesign'
type: session-log
tags:
  - type/session-log
  - domain/ui
created: '2026-06-20T00:00:00.000Z'
updated: '2026-06-20T00:00:00.000Z'
source: agent
aliases:
  - Loom Thread Particle Redesign
---
# Session: Loom Thread Particle Redesign

**Date**: 2026-06-20
**Status**: Completed

## Summary

Redesigned the Loom theme's `thread` particle effect. The original had two problems: random warm hue threads (greenish-yellow, 50-90°) clashing with the cold purple theme palette, and aimless bidirectional drifting that didn't evoke weaving. Replaced with theme-accurate purple/cyan horizontal shuttle threads that criss-cross with the CSS vertical warp stripes, plus a snag divergence state.

## What Changed

**File**: `anvil/api/static/js/theme/particle-system.js` — the `thread` effect (~line 826)

### Problems fixed

1. **Color clash** — Original used `hsla(50-90°, ...)` (greenish-yellow) which clashed with Loom's dark purple palette (`--bg: #0c0a10`, `--accent: #b890f0`). Switched to theme tokens: 70% purple (`rgba(184, 144, 240, ...)`) and 30% cyan (`rgba(96, 204, 224, ...)`).

2. **Aimless motion** — Original particles had random horizontal/vertical assignment (`hor: Math.random() > 0.5`) and drifted aimlessly in both axes. Replaced with purely horizontal left-to-right shuttle motion — all threads move horizontally and wrap around screen edges, evoking a loom shuttle passing through warp.

3. **Snag integration** — Original had no divergence awareness. Now reads `data-loom-state="snag"` and draws threads as jagged red tangled knots with randomized angles and thicker strokes during divergence — mirroring the CSS `loom-snag` animation on the weft overlay.

4. **Criss-cross pattern** — Purely horizontal particle threads naturally criss-cross with the vertical CSS warp stripes (`.app-main::before` `repeating-linear-gradient` at 90deg), creating a woven fabric feel without duplicating the warp in the canvas layer.

### Tuning

- `BASE` reduced from 20→12, `MAX` from 80→50 — cleaner at idle, denser under load
- Line width: `0.6 + sig * 0.4` — thin elegant strands at rest, thicker under weave tension

## User follow-up

User requested purely horizontal movement (no vertical wobble) so the criss-cross comes from canvas threads × CSS warp stripes. Removed the `q.y += Math.sin(...)` vertical undulation.

## Files Modified

- `anvil/api/static/js/theme/particle-system.js` — `thread` effect rewritten

## Verification

- `lsp_diagnostics` clean (no errors) after each change.

## Related

- [[Reference/particle-effect-authoring|Particle Effect Authoring]]
- [[Reference/theme-creation-guide|Theme Creation Guide]]
- [[Sessions/2026-06-20-nine-new-themes|Nine New Themes]]
- [[Sessions/2026-06-19-theme-gallery-expansion|Theme Gallery Expansion]]
