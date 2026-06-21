---
aliases:
  - Hyperspace Theme Warp Effects
created: '2026-06-20'
source: agent
status: draft
tags:
  - domain/ui
  - type/session-log
title: Hyperspace Theme Warp Effects — 2026-06-20
type: session-log
updated: '2026-06-20'
---
# Hyperspace Theme Warp Effects

**Date**: 2026-06-20
**Context**: Iterative enhancement of the Hyperspace theme's atmospheric effects — from 80s ray-traced wireframe grid through warp-speed tunnel to surface-rush visual, with vault enrichment at session end.

## What Was Done

### 1. 80s 3D Ray-Traced Wireframe Grid (`.app-shell::before`)

Added a perspective wireframe grid floor that scrolls toward the viewer — purple/cyan neon grid lines with vanishing-point perspective via `perspective(350px) rotateX(72deg)`. Speed driven by `--velocity`, brightness by `--focus`. Masks to fade at the horizon.

### 2. Warped Starfield (`.app-main::before`)

Replaced the original 5-dot star pattern with a rich 20-star field: 7 large glow-halo stars (3-4px), 5 medium fill stars (2px), 8 tiny distant stars (1px). White, purple, and cyan accents. `opacity: 0.8` base (always visible), velocity-driven scale stretch (`+35%`) and speed blur (`+0.8px`) at warp velocity. Idle pulse animation (`hyper-star-pulse`) keeps the field alive at rest.

### 3. Surface Rush Effect (`.app-main::after`)

Iterated through three approaches:
- **v1 — Rotating conic tunnel**: `repeating-conic-gradient` spinning at variable speed. Felt like a vortex, not forward motion.
- **v2 — Zooming radial rings**: `repeating-radial-gradient` with `transform: scale(0.6→1.6)`. Better (felt like flying forward through a tube) but had a visible pop on loop repeat because scale animation hard-resets.
- **v3 — Seamless scrolling bars** (shipped): `repeating-linear-gradient` horizontal bars scrolling upward by exact pattern multiples (44px × 2 = 88px). `linear` timing, `background-position` animation. Zero discontinuity on repeat. Horizon mask (`linear-gradient` top fade) creates a ground-plane feel.

### 4. Warp Core Glow (`.app-shell::after`)

New 600px pulsing radial glow centered in the viewport. Purple/cyan gradient that intensifies with `--velocity` and bursts on milestones (`scale(1.8) + brightness(2.5)`). Gives the theme a focal point.

### 5. Theme CSS Cache-Busting

Discovered that dynamically loaded theme CSS had no cache-busting query parameter (unlike `base.css` which uses `?v={{ version }}`). Applied fix:
- `base.html`: inline script now sets `window.ANVIL_VERSION` and appends `?v=` to theme CSS URLs.
- `theme-manager.js`: `ensureLayer()` reads `window.ANVIL_VERSION` and appends cache buster.
- All previously janky zoom/transform animations were replaced with seamless `background-position` scroll (see [[Discoveries/seamless-background-position-loop-animation]]).

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| `position: fixed` pseudo-elements vs real DOM | Pseudo-elements keep the theme self-contained in its CSS file; no JS DOM injection needed for basic effects |
| `background-position` scroll over `transform: scale` | Eliminates the visible loop-reset pop that plagues scale/transform animations |
| Horizon mask (linear) over circular donut mask | Ground-plane feel (moving across a surface) rather than tunnel vision |
| `linear` timing over `ease-in-out` | `ease-in-out` draws attention to the animation boundary by slowing at each end; `linear` keeps the scroll constant and the reset invisible |
| `!important` for milestone overrides and reduced-motion | Needed to override transition-driven values and CSS-variable-driven `animation-duration` |

## Discoveries Captured

- [[Discoveries/seamless-background-position-loop-animation]] — general technique for zero-pop CSS loop animations
- [[Discoveries/static-css-no-cache-busting]] **updated** → status changed to `reviewed`, fix details added

## Files Changed

- `anvil/api/static/css/themes/hyperspace.css` — all three pseudo-element effect layers + warp core glow
- `anvil/api/templates/base.html` — cache-busting version variable + inline script update
- `anvil/api/static/js/theme/theme-manager.js` — `ensureLayer()` cache-busting support
- `docs/vault/Discoveries/static-css-no-cache-busting.md` — updated with fix details
- `docs/vault/Discoveries/seamless-background-position-loop-animation.md` — new discovery
- `docs/vault/Sessions/2026-06-20-hyperspace-theme-warp-effects.md` — this session log
