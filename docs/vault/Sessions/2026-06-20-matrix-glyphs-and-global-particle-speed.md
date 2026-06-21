---
title: 'Session: Matrix Right-Angled Glyphs + Global Particle Speed Halving'
type: session-log
tags:
  - type/session-log
  - domain/ui
created: '2026-06-20'
updated: '2026-06-20'
source: agent
aliases:
  - Matrix Glyphs and Global Particle Speed
---
# Session: Matrix Right-Angled Glyphs + Global Particle Speed Halving

**Date**: 2026-06-20
**Scope**: `anvil/api/static/js/theme/particle-system.js` only. No theme registration, CSS, manager, or test changes.

## What changed

Three iterative tweaks to the canvas particle system, all driven by live user feedback on the Mainframe theme's `matrix` effect and the system at large.

### 1. Mainframe `matrix`: round "snow" dots → right-angled glyphs

The `matrix` effect originally rendered gently-falling **round green dots** (`ctx.arc`, radius `1–3.5`), which read as snow rather than the digital/terminal aesthetic the Mainframe theme wants. Rewrote it to render **axis-aligned rectangles snapped to a 12px column grid** (`ctx.fillRect`, pixel-snapped via `Math.round` for crisp corners): a brighter leading glyph plus a tail of dimming `3×3` trailing squares. Same `--activity` signal drive, same `BASE 40 → MAX 200` count scaling, same depth-fade (`interp`).

### 2. Global speed: all effects halved (idle + active), one choke point

User: "most need to be very slow compared to what I am seeing." Confirmed scope = **all effects**, **~half speed**, **both idle and active ranges**.

The naive approaches both fail:
- Scaling the `timestamp` passed to `update` slows only **time-based oscillation** (`Math.sin(ts * …)`); it does nothing to **per-frame position integration** (`q.y += q.s * …`), which has no delta term and advances a fixed step *per frame*.
- Editing the ~28 per-site motion coefficients is error-prone and risks inconsistent tuning across ~22 effects.

The fix is a single localized change in the animation loop: **gate the simulation step on accumulated wall-clock time** so the sim advances at ~30 steps/sec instead of ~60 (`SIM_INTERVAL = (1000/60) / SPEED_SCALE`, `SPEED_SCALE = 0.5`), and feed effects a `simClock` that advances `1000/60` ms *per sim-step*. This halves both motion types uniformly. On skipped frames the canvas is **not** cleared and `update` is not called, so the last frame persists → no flicker. `SPEED_SCALE` is now the single global speed knob. See [[Discoveries/global-particle-speed-via-sim-step-cadence|Global Particle Speed via Sim-Step Cadence Gating]].

### 3. `matrix`: varied shape sizes, with a low wide-block rate

User wanted size variety, "some that are wider", then "much smaller spawn rate" for the wide ones. Replaced the binary `wide` flag with a per-particle randomized width/height from a weighted `pickShape()` roll:

- **55%** tall thin bars (`~2–4` × `10–18`)
- **37%** small squares (`~3–5` × `3–6`)
- **8%** wide blocks (`~7–17` × `3–8`) — the occasional chunky accent

Shapes re-roll on recycle; trailing-segment width scales with the glyph's width (`gw * 0.6`, min 2) so a wide stream reads as a cohesive wide trail. Note: a block-scoped `var reshape` inside the loop tripped the project's "var at function root" lint — hoisted to the top `var` line (recurring gotcha, see [[Reference/particle-effect-authoring]]).

## Verification

`lsp_diagnostics` clean after each step — only the file's pre-existing unused-var hints (`glow`/`cx`/`ts` across other effects). No test references the matrix internals or the per-frame cadence (grep over `test_theme*` / `animationLoop` found none), so the cadence change is safe.

## Related

- [[Discoveries/global-particle-speed-via-sim-step-cadence|Global Particle Speed via Sim-Step Cadence Gating]]
- [[Discoveries/canvas-particle-amplitude-vs-frequency-perceived-speed|Amplitude vs Frequency Perceived-Speed Trap]] — the *per-effect* speed lever; this session adds the *global* one
- [[Reference/particle-effect-authoring|Particle Effect Authoring]]
- [[Reference/theme-creation-guide|Theme Creation Guide]]
