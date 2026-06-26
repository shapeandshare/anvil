---
aliases:
  - Forge Spark Effect
  - Metal-Struck Sparks
source: agent
created: '2026-06-20'
status: draft
source: agent
aliases:
  - Forge Spark Effect — Metal-Struck Sparks Replace Ember Glow
tags:
  - type/session-log
  - domain/ui
  - status/draft
title: Forge Spark Effect — Metal-Struck Sparks Replace Ember Glow
type: session-log
updated: '2026-06-20'
code-refs:
  - anvil/api/static/js/theme/particle-system.js
  - anvil/api/static/css/themes/forge.css
  - anvil/api/static/js/themes/forge.js
  - Reference/particle-effect-authoring.md
---
# Forge Spark Effect — Metal-Struck Sparks Replace Ember Glow

**Date**: 2026-06-20

## Summary

Replaced the Forge theme's existing ambient heat glow + ember particle effect with a striking-metal-sparks effect driven by a new `spark` particle system effect. Sparks burst from a bottom anvil band, travel on ballistic physics (velocity + friction + gravity), and are drawn as sharp line streaks oriented along their trajectory — visually distinct from the gentle rising ember dots.

## Changes

### `anvil/api/static/js/theme/particle-system.js`
- Added new `spark` effect registration (~80 lines, after `spin` effect)
- Physics-based particle: velocity vector, per-particle friction (0.96–0.99), slight gravity (0.02/frame)
- Spawn band at `BAND_Y = 0.92` (92% viewport height)
- Particles drawn as `lineTo` streaks in velocity direction, not `arc` circles
- Color lifecycle: white-hot (life > 0.7) → yellow-orange (0.4–0.7) → dim red (< 0.4)
- Glow dot at streak head when life > 30%
- Signal-driven count: BASE=80, MAX=350, scales with `--heat` (throughput)
- All vars declared at function root to satisfy lint hoisting rule

### `anvil/api/static/css/themes/forge.css`
- Replaced single soft radial glow with dual-layer forge fire bed:
  - Core fire: tight 30% hotspot, `rgba(255, 200, 120, ...)` — bright, focused
  - Outer glow: wider 50% warmth, `rgba(255, 122, 26, ...)` — ambient forge ambience
- Quench state (milestone/complete): cyan flash with tighter core (`20% 40%`)
- Divergence state: angry red with two-layer hot gradient

### `anvil/api/static/js/themes/forge.js`
- Changed `particleConfig` from `{ type: 'ember' }` to `{ type: 'spark' }`
- Updated `previewHint` from `'Loss as cooling metal'` to `'Sparks flying from the anvil'`

## Tuning Notes
- Initial spark velocity was `2 + Math.random() * 5` but doubled to `4 + Math.random() * 8` on user request for taller arcs
- Spawn band moved from `0.78` to `0.92` (too high originally)
- Spark effect reads `--heat` (via throughput signal), same CSS var the existing mapping already publishes — no mapping changes needed

## Files Touched
1. `anvil/api/static/js/theme/particle-system.js` — new `spark` effect registration
2. `anvil/api/static/css/themes/forge.css` — forge fire bed redesign
3. `anvil/api/static/js/themes/forge.js` — particleConfig + previewHint
4. `docs/vault/Reference/particle-effect-authoring.md` — catalog updated with spark description

## Related

- [[Design/Design|Design]] — UI design system including forge theme and particle effects
- [[Reference/particle-effect-authoring|Particle Effect Authoring]] — particle system reference
- [[Reference/theme-creation-guide|Theme Creation Guide]] — theme authoring reference
