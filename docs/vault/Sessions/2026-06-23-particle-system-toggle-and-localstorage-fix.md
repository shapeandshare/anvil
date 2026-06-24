---
aliases:
  - Particle System Toggle + localStorage Override Fix
created: '2026-06-23'
source: agent
status: draft
tags:
  - domain/ui
  - type/session-log
title: Particle System Toggle + localStorage Override Fix — 2026-06-23
type: session-log
updated: '2026-06-23'
---
# Particle System Toggle + localStorage Override Fix

**Date**: 2026-06-23
**Context**: User reported that a "spinning particle effect" was always active across
all themes and pages, running on top of each theme's own particles. Investigation
revealed two independent problems: (1) `getEffectiveConfig()` allowed a
`localStorage.theme:particle` pref to override every theme's `particleConfig` with a
single forced effect, and (2) the `spin` registered effect had been enabled at some
point via this mechanism. Additionally, the theme picker dropdown had a transparency
issue from `background-clip: padding-box` exposing the translucent `--glass-border`.

## What Was Done

### 1. Removed localStorage effect override

`anvil/api/static/js/theme/particle-system.js` `getEffectiveConfig()` had a fallback
path: if `localStorage.getItem('theme:particle')` returned a value matching any
registered effect name, it would override the theme's own `particleConfig` with that
forced effect. A single effect (e.g. `spin`) could run on ALL themes, on top of each
theme's intended particles. Removed the override path — the pref now strictly controls
on/off (`'none'` = off, anything else = fall through to theme config).

### 2. Added "Show particles" toggle

Added a checkbox in the theme picker controls (above "Reduce effects") in
`anvil/api/static/js/theme/theme-manager.js`. When unchecked, calls
`ParticleSystem.writePref('none')` and re-applies the current theme — stopping all
canvas particles. When checked, clears the pref and restores the theme's own effect.
Particles default to ON (unset pref = theme config runs as normal).

### 3. Fixed theme picker dropdown transparency

`anvil/api/static/css/base.css` `.theme-picker__menu` had `background-clip:
padding-box` which clipped the solid `--surface` background away from the 1px border
area, and the border used near-transparent `--glass-border` (rgba(255,255,255,0.08)).
Removed `background-clip: padding-box` and changed border to opaque `--separator`.

## Files Changed

```
Modified:
  anvil/api/static/js/theme/particle-system.js (getEffectiveConfig: removed localStorage override, pref is on/off only)
  anvil/api/static/js/theme/theme-manager.js   (added "Show particles" toggle + wiring; readParticlesOn helper)
  anvil/api/static/css/base.css                (theme-picker__menu: opaque border, no background-clip)
```

## Validation

- `lsp_diagnostics` clean on both JS files (only pre-existing unused-var hints in
  particle-system.js). CSS has no LSP diagnostics.
- Toggle wiring sets `theme:particle` to `'none'` on uncheck, clears on check.
- Re-apply on toggle change so `ParticleSystem.apply()` picks up new pref immediately.
- No effect name in localStorage can override a theme's `particleConfig` anymore.

## Notes / Follow-ups

- The `spin` effect (registered in `particle-system.js` at line 1306) is still
  registered but unused by any theme's `particleConfig`. It was the specific effect
  the user observed running across all themes. If a theme wants spinning particles, its
  `particleConfig` should explicitly set `type: 'spin'`.
- Existing users who had a stale `theme:particle` pref in localStorage will have it
  silently ignored (only `'none'` is recognized). They can toggle "Show particles" off
  and back on to clear it.
- The default theme's CSS `.ambient-particles` (orange floating sparks in `base.html`)
  are unaffected by this toggle — they are controlled by `data-skin="default"` in CSS
  and are separate from the canvas particle system entirely.

## Wikilinks

- [[Discoveries/particle-canvas-always-on-idle-baseline]]
- [[Discoveries/localstorage-particle-pref-override]]
- [[Discoveries/theme-presence-tiers-css-vs-session-gated-js]]
- [[Reference/theme-creation-guide]]
- [[Sessions/2026-06-20-particle-system-always-on-and-rain-overhaul]]
