---
title: Global Particle Speed via Sim-Step Cadence Gating
type: discovery
tags:
  - type/discovery
  - domain/ui
  - status/draft
created: '2026-06-20'
updated: '2026-06-20'
source: agent
aliases:
  - Global Particle Speed Knob
  - Sim-Step Cadence Gating
  - SPEED_SCALE
code-refs:
  - anvil/api/static/js/theme/particle-system.js
related:
  - '[[Reference/particle-effect-authoring]]'
  - '[[Discoveries/canvas-particle-amplitude-vs-frequency-perceived-speed]]'
  - '[[Sessions/2026-06-20-matrix-glyphs-and-global-particle-speed]]'
---
# Global Particle Speed via Sim-Step Cadence Gating

**Discovered**: 2026-06-20, when asked to slow down *all* particle effects "to about half speed" across both the idle and active signal ranges.

## The problem: two motion sources, only one is time-based

Every effect in `particle-system.js` advances particles in its `update()` via **two independent motion sources**:

1. **Per-frame position integration** — `q.y += q.s * (0.18 + sig * 0.42)`. This advances a **fixed step *per animation frame***. It has **no delta-time term**; it implicitly assumes a steady frame rate.
2. **Time-based oscillation** — `q.x += Math.sin(ts * q.wanderF + q.ph) * amp`. This reads the real `timestamp` the loop passes in.

This split is the trap. The obvious "scale the timestamp" idea (`update(timestamp * 0.5, …)`) slows **only** the oscillation (#2) and leaves the falling/rising/drifting integration (#1) at full speed. You'd get half-speed sway on top of full-speed descent — visibly wrong.

The other obvious idea — editing all ~28 per-site coefficients (`0.18 + sig * 0.42` → `0.09 + sig * 0.21`, etc., across ~22 effects) — is mechanical, error-prone, and risks inconsistent tuning. It also bakes the factor in, so there's no single knob.

## The fix: gate the simulation step on wall-clock time

Slow **both** sources uniformly with one change at the animation-loop choke point. Instead of stepping the sim every `requestAnimationFrame` tick, accumulate elapsed wall-clock time and only step when a scaled interval has passed:

```js
var SPEED_SCALE = 0.5;
var SIM_INTERVAL = (1000 / 60) / SPEED_SCALE;  // 0.5 -> 33.3ms (~30 steps/sec)
var simClock = 0, lastTs = null, sinceStep = 0;

function animationLoop(timestamp) {
  if (!ctx || !canvas || !isRunning) { rAFid = null; lastTs = null; return; }
  var w = window.innerWidth, h = window.innerHeight;

  if (lastTs == null) lastTs = timestamp;
  sinceStep += timestamp - lastTs;
  lastTs = timestamp;

  if (sinceStep >= SIM_INTERVAL) {
    sinceStep -= SIM_INTERVAL;
    if (sinceStep > SIM_INTERVAL) sinceStep = 0;  // clamp after a tab-away / long stall
    simClock += 1000 / 60;                         // advance the effect's clock one "frame"
    ctx.clearRect(0, 0, w, h);
    if (activeImpl && activeImpl.update) activeImpl.update(simClock, w, h, ctx);
  }
  rAFid = requestAnimationFrame(animationLoop);
}
```

Why this halves **both** motion types at once:

- **Per-frame integration**: the sim now steps ~30×/sec instead of ~60×/sec → half as many fixed steps per second → **half the descent/drift speed**. No per-site math touched.
- **Time-based oscillation**: effects read `simClock`, which advances `1000/60` ms **per sim-step**. Because sim-steps happen at half the wall-clock rate, `simClock` progresses at half real time → oscillation phase also runs at **half speed**.
- **Idle and active both scale**: the idle baseline (`IDLE_SIGNAL = 0.5`, see [[Discoveries/particle-canvas-always-on-idle-baseline]]) and high-`sig` active motion ride the same step cadence, so they slow together.

`SPEED_SCALE` is now the **single global speed knob**: `0.33` ≈ 3× slower, `0.7` a gentle reduction, `1.0` original.

## Two non-obvious correctness details

- **No flicker on skipped frames.** Critically, the canvas is cleared (`clearRect`) **inside** the gated block, not every frame. On a skipped frame nothing clears and nothing redraws, so the previous frame's pixels persist. An early attempt that cleared every frame and tried to redraw via a separate `draw()` method flickered, because effects have no `draw()` — only `update()` paints.
- **Reset accumulators on stop.** `stopAnimation()` must reset `lastTs = null; sinceStep = 0;` (and the loop resets `lastTs` on exit) so a long pause / tab-away doesn't inject a giant `sinceStep` that fires a burst of catch-up steps on resume. The `if (sinceStep > SIM_INTERVAL) sinceStep = 0` clamp is the same guard from the other direction.

## Relationship to the other speed lever

This is the **global** speed control. The **per-effect** perceived-speed lever — and why raising amplitude reads as "faster" — is a separate finding in [[Discoveries/canvas-particle-amplitude-vs-frequency-perceived-speed]]. Use `SPEED_SCALE` to slow the whole system at once; use the amplitude/frequency separation to tune an individual effect's *character*.

## Where this lives

- `anvil/api/static/js/theme/particle-system.js` — `SPEED_SCALE`, `SIM_INTERVAL`, `simClock`, the gated `animationLoop`, and the `stopAnimation` reset.

## See Also

- [[Discoveries/Discoveries|Discoveries]]
