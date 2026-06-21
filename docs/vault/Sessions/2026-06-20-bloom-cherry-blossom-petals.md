---
aliases:
  - Bloom Cherry Blossom Petals
created: '2026-06-20'
source: agent
status: draft
tags:
  - domain/ui
  - type/session-log
title: Bloom Cherry Blossom Petals — 2026-06-20
type: session-log
updated: '2026-06-20'
---
# Bloom Cherry Blossom Petals — 2026-06-20

**Date**: 2026-06-20
**Context**: The Bloom theme's canvas particle effect (registered via `particleConfig: { type: 'petal' }`) was changed twice in quick succession. First the original floating circles were replaced with rose-shaped petals (bezier teardrops with a center vein and deep pink gradient). Then the user asked to shift direction entirely — instead of rose petals, make it **cherry blossom (sakura) petals** with the characteristic cleft/notch at the tip, pale pink sakura colors, and a gentler flutter. Later adjusted for larger size and faster fall speed.

## What Was Done

### Phase 1 — Rose petals (reverted)
- Replaced the `petal` effect's `arc` circle drawing with a bezier-based teardrop shape (pointed at attachment end, rounded at tip)
- Added 3-stop radial gradient for depth, subtle center vein line, per-particle rotation
- Colors in the deep pink/red range (hue 300-360)
- Reduced base count from 30→20, max from 150→120 (bigger shapes, fewer needed)

### Phase 2 — Cherry blossom petals
- Replaced the teardrop shape with a **sakura cleft shape**: two bezier lobes separated by a `quadraticCurveTo` notch at the tip, narrowing to the base
- Colors shifted to pale sakura pink (hue 335-355, sat 40-65%, lgt 72-88%) — lighter, more delicate
- Removed the center vein (not characteristic of sakura petals at this scale)
- Increased particle count (BASE 25, MAX 140)
- Slightly gentler wobble frequency and amplitude
- After later tuning: petals enlarged to 8-20px wide × 14-36px long, fall speed increased to 0.12-0.37

### Cleanup
- The theme was briefly deleted (bloom.js, bloom.css removed, base.html/theme-creation-guide/test references stripped) then restored from git HEAD
- No net structural changes to the theme — only the `petal` effect implementation in `particle-system.js`

## Key Technique — Sakura Cleft via Beziers

The sakura petal shape is drawn with two bezier curves forming the lobe edges and two quadratic curves forming the central cleft:

```
c.moveTo(0, lh);  // base (bottom point)
// Left lobe: widens then curves to left tip
c.bezierCurveTo(-lw * 0.4, lh * 0.2, -lw * 1.0, -lh * 0.05, -lw * 0.55, -lh * 0.5);
// Left lobe → notch
c.quadraticCurveTo(-lw * 0.18, -lh * 0.25, 0, -lh * 0.55);
// Notch → right lobe
c.quadraticCurveTo(lw * 0.18, -lh * 0.25, lw * 0.55, -lh * 0.5);
// Right lobe → base
c.bezierCurveTo(lw * 1.0, -lh * 0.05, lw * 0.4, lh * 0.2, 0, lh);
```

The cleft is intentionally slightly exaggerated so it remains visible at the small canvas scale (8-20px wide petals).

## Relevant Files

- `anvil/api/static/js/theme/particle-system.js` — `registerEffect('petal', ...)`, the cherry blossom implementation
- `anvil/api/static/js/themes/bloom.js` — host theme, unchanged (already had `particleConfig: { type: 'petal' }`)
- `anvil/api/static/css/themes/bloom.css` — host CSS, unchanged

## Wikilinks

- [[Reference/particle-effect-authoring]]
- [[Reference/theme-creation-guide]]
- [[Decisions/ADR-031-behavioral-theme-engine]]
