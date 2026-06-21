---
aliases:
  - Unicorn Cloud + Rainbow Particle Effects
created: '2026-06-20'
session: 2026-06-20-unicorn-cloud-particles
source: agent
status: draft
tags:
  - domain/ui
  - type/session-log
title: Unicorn Cloud + Rainbow Particle Effects — 2026-06-20
type: session-log
updated: '2026-06-20'
---
# Unicorn Cloud + Rainbow Particle Effects

**Date**: 2026-06-20
**Context**: User asked for cloud particles on the Unicorn theme — "clouds and
rainbows" as floating particle effects alongside the existing unicorn sprites.

## What Was Done

### 1. SVG Cloud Factory (`unicorn.js`)

Added `createCloudSVG(size, hue)` — builds an inline SVG cloud from overlapping
circles (back-shadow puffs + flat-bottom filler rect + front puffs) with slight
random jitter per instance so every cloud is unique. Colors are hue-tinted in the
purple/pink pastel range (240°-300°). Each cloud gets a per-instance `feGaussianBlur`
glow filter.

### 2. Session-Gated Clouds (in `unicornMapping`)

Clouds join the existing session-driven sprite system alongside unicorns and rainbows:

- **Constants**: `MAX_CLOUDS = 8`, `CLOUD_LIFETIME = 40000`, `CLOUD_SPAWN_MS = 3000`
- **`spawnCloud()`** — creates a cloud at a random sky position, assigns very slow
  drift velocity (dx: -0.035 to -0.008 px/ms), wraps it in `.unicorn-cloud` div, adds
  to the rAF animation loop
- **Animation**: slow leftward drift with slight vertical bob in the existing
  `requestAnimationFrame` loop; expired clouds culled like unicorns/rainbows
- **Cadence**: spawns every ~3s via `setInterval` in `startSpawnTimers()`; at
  `magic > 0.6` doubles up (2 clouds per tick)
- **Initial spawn**: 2 clouds on boot (normal + reduced motion modes)
- **Cleanup**: full teardown via `removeAllSpawned()`, `stopSpawnTimers()`,
  divergence fade, and mapping teardown

### 3. Ambient Cloud System (always-on, no training session)

**Key architectural discovery**: The theme manager's `bindMapping()` gates on
`bus.session()` — mapping only runs during active training, so session-gated sprites
are absent on every static page. Added a standalone **ambient cloud system** in the
unicorn.js IIFE (outside the mapping function) that activates via `MutationObserver`
on `data-skin`:

- Creates a `.unicorn-ambient` overlay (z-index 4, below session overlay at z-index 5)
- Spawns 3 drifting SVG clouds that slowly float leftward
- Clouds respawn when they drift off-screen (replenish to 3)
- 3-second CSS fade-in on spawn
- Deactivates cleanly when switching away from the unicorn theme
- No conflict with session-driven clouds — ambient and session overlays are separate
  DOM layers; during training both run simultaneously

This extends the theme presence tiers described in
[[Discoveries/theme-presence-tiers-css-vs-session-gated-js]] — we previously knew of
two tiers (always-on CSS and session-gated JS). The ambient cloud system adds a third:
**always-on JS via IIFE + MutationObserver**, which can inject dynamic DOM sprites
even without a training session.

### 4. CSS Layer (`unicorn.css`)

- `.unicorn-cloud` — absolute positioned, `transition: opacity 1.2s ease-out`, fade-in
  via `.visible` class, drop-shadow on SVG
- `.unicorn-ambient` — fixed overlay for always-on clouds (z-index 4)
- `.unicorn-ambient-cloud` — shares `will-change: transform` and SVG drop-shadow
  with `.unicorn-cloud`
- Reduced-motion: both `.unicorn-cloud` and `.unicorn-ambient` hidden via
  `display: none`
- Divergence: ambient clouds unaffected (no divergence state on ambient layer); session
  clouds inherit grayscale via `.unicorn-overlay` CSS

### 5. Rainbow Enhancement

The existing rainbows already scale with `--magic` (`magic > 0.25 && Math.random() < magic`
in the spawn timer). At higher magic levels rainbows spawn more frequently. No code
change was needed — the existing mechanism was sufficient.

## Files Changed

```
Modified:
  anvil/api/static/js/themes/unicorn.js   (+200 lines: cloud factory, session-driven cloud system,
                                            ambient cloud system, MutationObserver, all wiring)
  anvil/api/static/css/themes/unicorn.css (+40 lines: cloud/ambient classes, keyframes, reduced-motion)
```

No engine, registration, `base.html`, or test-list changes.

## Validation

- `lsp_diagnostics` clean on both files (zero errors, zero warnings beyond shared
  pre-existing reduced-motion `!important`)
- Ambient system activates on theme selection without training session (MutationObserver)
- Ambient system deactivates on theme switch (full DOM/timer/rAF cleanup)
- Session-driven clouds activate during training (via existing `startSpawnTimers` path)
- Both overlay layers coexist without conflict (different z-index, different class names)

## Wikilinks

- [[Discoveries/theme-presence-tiers-css-vs-session-gated-js]]
- [[Reference/theme-creation-guide]]
- [[Decisions/ADR-031-behavioral-theme-engine]]
- [[Sessions/2026-06-20-unicorn-mascot-flying-sprites]]
- [[Sessions/2026-06-20-unicorn-theme-and-prism-vibrancy]]
