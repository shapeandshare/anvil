---
created: '2026-06-20'
status: draft
source: agent
tags:
  - domain/ui
  - type/session-log
title: Particle System Always-On + Rain Overhaul — 2026-06-20
type: session-log
updated: '2026-06-20'
aliases:
  - Particle System Always-On + Rain Overhaul
---
# Particle System Always-On + Rain Overhaul

**Date**: 2026-06-20
**Context**: User reported that selecting a behavioral theme (e.g. Storm Front) only
ever showed the orange "sparks" rising from the bottom of every page, never the
theme's own particles, and the particle dropdown did nothing. Investigation revealed
the canvas particle system only ran during an active training run, while an unrelated
always-on CSS spark layer dominated. A sequence of follow-up requests then tuned the
behavior: keep the sparks on the default theme only, make every theme's particles
visible at rest, layer particles behind content, keep the nav legible, eliminate a
load-time "wave", widen wind coverage, align the rain streak angle with the wind, and
slow the rain down.

## What Was Done

### 1. Particles always-on (was training-only)

`anvil/api/static/js/theme/theme-manager.js` `apply()` previously forced CSS-only
particles unless a training signal bus session was attached, so canvas effects (rain,
snow, embers, …) were invisible on every static page. It now always calls
`ParticleSystem.apply(theme, null, false)` — particles render the moment a theme is
selected and intensify once training drives the signals.

### 2. Default-theme sparks, scoped

The orange/yellow rising "sparks" are the hardcoded `.ambient-particles` block in
`anvil/api/templates/base.html` — they were always-on for every theme. They are the
*default* theme's intended effect (it has no `particleConfig`, so it falls back to
`type: 'css'`). Scoped them to `[data-skin="default"] .ambient-particles` in
`anvil/api/static/css/base.css` so other themes show their own canvas particles
instead. `DESIGN.md`'s Ambient Background section was reconciled.

### 3. Idle-signal baseline (visibility at rest)

Most canvas effects scale both particle count and opacity by a signal CSS var that is
only set during training, so at rest they were near-invisible (Ember Drift was
effectively blank in dark mode). Added `IDLE_SIGNAL = 0.5` plus `readSignal(name)` /
`readSignalChain(primary, fallback)` helpers in
`anvil/api/static/js/theme/particle-system.js`: an **unset** signal var yields the
idle baseline; a **set** var (even `"0"` during training) wins. Routed all 17 intensity
signals through these helpers (left `--hue` alone — it is a rotation, not an intensity).
See [[Discoveries/particle-canvas-always-on-idle-baseline]].

### 4. Layering — particles behind content, nav above

The canvas was `position: absolute; z-index: 40` (over the content). Changed to
`position: fixed; z-index: 0` so it sits behind `.app-main` (which has its own
`isolation: isolate` stacking context) but above the `.app-shell` background. Because a
positioned `z-index:0` canvas still paints over a *static* sibling, the `.nav-bar`
washed out; fixed it by giving `.nav-bar` `position: relative; z-index: 1` in
`base.css` (`--surface` is opaque, so the bar is solid again).

### 5. No second "wave" on load

Two causes, both fixed:
- `ThemeManager.bindSession()` called `ParticleSystem.apply()` when the page connected
  its SSE session, tearing down and rebuilding the already-running canvas (a second
  wave after a pause). Removed that redundant re-apply — `bindSession` now only
  attaches the bus and (re)binds the mapping; the running effect picks up live metrics.
- The rain effect seeded all drops *above* the viewport at init, so the screen filled
  top-to-bottom (a wave). `init()` now seeds drops across the **full** screen.

### 6. Rain coverage, angle, and speed

- **Wind coverage**: wind pushed every drop the same way and bared the windward side.
  Widened the spawn band (-50%…150% of width) and added **horizontal wraparound** so
  drops blown off one edge re-enter the other — uniform coverage under any wind.
- **Streak angle**: the streak used a fixed tilt that ignored real motion. It now draws
  along the normalized per-frame velocity vector `(vx, vy)`, so streaks lean exactly
  the way drops travel and re-angle live with gusts.
- **Fall speed**: lowered drop speed from `3–6` to `1.5–3.5` at the user's request.

## Files Changed

```
Modified:
  anvil/api/static/js/theme/theme-manager.js   (always-on apply; bindSession no re-apply)
  anvil/api/static/js/theme/particle-system.js (idle baseline; fixed/z-index 0 canvas; rain spawn/wrap/angle/seed/speed)
  anvil/api/static/css/base.css                (ambient sparks scoped to default; nav-bar z-index)
  anvil/api/templates/base.html                (ambient-particles markup retained)
  anvil/api/static/js/themes/stormfront.js     (kept rain effect)
  DESIGN.md                                     (Ambient Background reconciled)
```

No engine, registry, or test-list changes.

## Validation

All verified against the running server with headless Chromium (Playwright), reading
the live `canvas.particle-canvas` pixels:

- Default theme shows the CSS sparks (`display:block`, 20 spans, no canvas); Storm Front
  hides them and runs the rain canvas (`canvasDrawn: true`).
- Idle dark-mode brightness/density jumped after the baseline change (Ember
  ~388→~2173 lit px, maxAlpha 66→177; Aurora 375→2278, 26→77; rain ~17k→~44k).
- Canvas computed `z-index: 0`; `elementFromPoint` over hero/nav returns content/nav,
  not the canvas (particles are behind content; nav is solid above).
- Simulated a session connect: 0 canvas adds/removes, 0 `ps.apply` calls, same canvas
  node — no rebuild, no second wave; bus session still binds.
- Rain coverage under strong wind: all 8 vertical columns lit (min/max ≈ 0.67, no empty
  bands); full-height coverage present within ~120 ms of load.
- `lsp_diagnostics` clean (only pre-existing unused-var hints remain).

## Notes / Follow-ups

- The full-screen-seed wave fix was applied to the **rain** effect only; other
  falling/rising effects (snow, ember, …) still seed from their edge and may show a
  milder startup wave. Worth propagating if it bothers users.
- `IDLE_SIGNAL = 0.5` is the single tuning knob for at-rest liveliness.
- Static assets carry ETags but no `Cache-Control`; a stale browser cache masked early
  fixes until hard refresh — see [[Discoveries/static-css-no-cache-busting]].

## Wikilinks

- [[Discoveries/particle-canvas-always-on-idle-baseline]]
- [[Reference/theme-creation-guide]]
- [[Decisions/ADR-031-behavioral-theme-engine]]
- [[Discoveries/theme-presence-tiers-css-vs-session-gated-js]]
- [[Discoveries/static-css-no-cache-busting]]
- [[Sessions/2026-06-20-ui-layout-overhaul]]
