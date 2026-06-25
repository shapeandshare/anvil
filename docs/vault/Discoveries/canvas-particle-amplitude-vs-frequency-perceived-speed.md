---
title: >-
  Canvas Particle Wander: Amplitude vs Frequency and the Velocity-Accumulation
  Trap
type: discovery
tags:
  - type/discovery
  - domain/ui
created: '2026-06-20T00:00:00.000Z'
updated: '2026-06-20T00:00:00.000Z'
source: agent
aliases:
  - Particle Perceived Speed Trap
  - Wander Amplitude vs Frequency
code-refs:
  - anvil/api/static/js/theme/particle-system.js
  - anvil/api/static/js/themes/oldgrowth.js
status: draft
---
# Canvas Particle Wander: Amplitude vs Frequency and the Velocity-Accumulation Trap

**Discovered**: 2026-06-20, while tuning the Old Growth firefly particle effect.

## The Symptom

When asked to make fireflies "slower with more meander", the natural move was to **raise the wander amplitude** and **lower the wander frequency**. The result was the opposite of intent: the fireflies looked *faster and more frantic*, not slower.

## Root Cause — Two Compounding Bugs

The original motion code added an oscillation directly to position **every frame**:

```js
q.x += q.vx * speed + Math.sin(ts * q.wanderF + q.ph) * q.wanderA;
```

There are two problems here:

### 1. The wander term is a velocity, not a position

Because `Math.sin(...) * wanderA` is **added to `x` each frame** (`q.x +=`), the amplitude `wanderA` is not how far the particle sways — it is how many pixels it moves *per frame*. The per-frame displacement of an oscillation added to position scales with `wanderA · wanderF` (its time-derivative). Raising `wanderA` from ~2 to ~3.6 directly multiplied per-frame travel, so "more meander" became "more speed".

### 2. Amplitude was driving perceived speed

Even when treated as a true positional offset, perceived speed is governed by the **derivative** `amplitude × frequency`, not amplitude alone. A large-amplitude sway completes each swing by covering a large distance; during the mid-swing the particle visibly races across a wide arc even if the full cycle period is long.

## The Fix — Separate Base Drift from Positional Sway

Model the motion as a **slowly-drifting base position** plus a **bounded positional offset**:

```js
// base position drifts slowly — this is the net "crossing the screen" motion
q.bx += q.vx * (0.4 + sig * 0.6);

// rendered position = base + a POSITIONAL sway (NOT accumulated into bx)
q.x = q.bx
    + Math.sin(ts * q.wanderF + q.ph)  * q.wanderA
    + Math.sin(ts * q.wanderF * 0.37 + q.ph2) * q.wanderA * 0.5;  // 2nd wave = curvier path

// wrap on the BASE coordinate so a wide sway never pops it off-screen
if (q.bx > w + 120) { q.bx = -120; }
else if (q.bx < -120) { q.bx = w + 120; }
```

Key properties of this model:

- **Amplitude (`wanderA`) = how wide the path is.** Frequency (`wanderF`) = how fast. They are now independent. You can make the meander *much* wider (30–100 px) while keeping it genuinely slow by holding frequency low.
- **Net drift (`vx`) is the only thing that accumulates** into the base coordinate, so the particle reliably traverses the screen over time regardless of how wild the sway is.
- **Layering a second, slower sine wave** (here `0.37×` the frequency, with its own phase `ph2`) makes the path curvy and non-repetitive instead of a clean repeating sine.
- **Edge-wrap on the base coordinate** (`bx`), not the rendered `x`, with a generous margin (`±120`) so the amplitude swing doesn't cause an abrupt jump at the edge.

## Tuning Heuristic

- To make particles **slower**: lower the time-based rates (`vx`, all `*F` frequencies). **Do not** touch amplitudes.
- To make particles **meander more**: raise amplitudes (`wanderA`, `bobA`) and/or the vertical-wander contribution. **Do not** raise frequencies (that reads as speed).
- "Eventually crosses the screen even if not directly" = a small persistent `vx` net drift layered under a large-amplitude, low-frequency sway.

## Where This Lives

- `anvil/api/static/js/theme/particle-system.js` — the `leaf` effect (used by the Old Growth theme; registered name kept as `leaf` for backward-compatible `particleConfig` / saved prefs).

## Related
- [[Discoveries/Discoveries|Discoveries]]

- [[Reference/theme-creation-guide|Theme Creation Guide]] — particle effect contract
- [[Sessions/2026-06-20-firefly-tuning-and-tide-shimmer|Session: Firefly Tuning + Tide Shimmer]]
