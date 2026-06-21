---
aliases:
  - Static Electrostatic Particles
created: '2026-06-20'
source: agent
status: draft
tags:
  - domain/ui
  - type/session-log
title: Static Electrostatic Particle Enhancement — 2026-06-20
type: session-log
updated: '2026-06-20'
---
# Static Electrostatic Particle Enhancement

**Date**: 2026-06-20
**Context**: The user noted the Static theme had "not static particle effect" and wanted something thematic or a visual effect added.

## What Was Done

### Static Theme Enhancement

Added an electrostatic discharge particle field to the Static theme via `::before` on `.app-main`:

- **15 radial-gradient particles** (1–2px blue-white dots) at diverse viewport positions, simulating tiny electrostatic sparks
- **`static-sparks` animation** (6s, 5-keyframe) pans `background-position` across a 300% canvas, creating a drifting/sparking feel
- **Opacity pulsing per keyframe** gives the illusion of individual particles popping in and fading
- **Driven by `--snow`** — the existing loss-volatility CSS variable — so particle intensity scales with training volatility
- **Snowstorm state** (divergence): separate `static-storm-sparks` keyframe with `steps(4)` for chaotic 0.6s flicker, opacity 0.1–0.3
- **Reduced motion**: `display: none` on both `::before` and `::after`
- **z-index layering**: particles at 40, noise overlay at 41 (depth effect)

No JS changes needed — the existing `--snow` variable already carries the right signal.

### Vault Enrichment

- Created `Discoveries/static-electrostatic-particle-field.md` — documents the multi-position radial-gradient particle field technique with key parameters, edge cases, and comparison to other theme effect patterns.

## Wikilinks

- [[Discoveries/static-electrostatic-particle-field]]
- [[Discoveries/theme-presence-tiers-css-vs-session-gated-js]]
- [[Sessions/2026-06-20-nine-new-themes]] (Static theme origin)
