---
aliases:
  - Solarflare Training Baseline Lift — Normal Now Looks Like Training
title: Solarflare Training Baseline Lift
type: discovery
status: draft
source: agent
session: '2026-06-26'
code-refs:
  - anvil/api/static/js/themes/solarflare.js
  - anvil/api/static/js/theme/particle-system.js
related:
  - '[[Discoveries/particle-canvas-always-on-idle-baseline]]'
  - '[[Discoveries/signal-gated-decorations-invisible-at-rest]]'
  - '[[Discoveries/theme-mapping-excited-fake-metrics-grad-norm]]'
tags:
  - type/discovery
  - domain/ui
  - status/draft
created: '2026-06-26'
updated: '2026-06-26'
---
When the solarflare theme was first implemented, its `--flare` CSS variable
defaulted to `0` and the canvas flare particle effect had `BASE=20, MAX=120`.
This made the idle state sparse (70 particles from `IDLE_SIGNAL=0.5`) compared
to the training state (120 particles at `sig=1.0`). A deliberate decision was
made to **lift the training baseline to be the new normal**, then push training
intensity higher still.

## What changed

**Mapping** (`solarflare.js`):
- Idle baseline: `setVar('--flare', '0')` → `'0.5'`
- Metrics formula: `clamp01(grad_norm)` → `clamp01(0.5 + grad_norm × 0.5)`
- Range at rest: `0` → `0.5`
- Range during training: `0 → 1.0` → `0.5 → 1.0`

**Particle effect** (`particle-system.js`, flare effect):
- `BASE: 20 → 60`
- `MAX: 120 → 250`

## Particle count at each state

| State | Before | After |
|---|---|---|
| Idle (no training, sig=0.5) | 70 | **155** |
| Training baseline (sig=0.5) | 20 | **155** |
| Training mid (grad_norm=0.5 → sig=0.75) | ~95 | **203** |
| Training peak (sig=1.0) | 120 | **250** |

## Smooth on-ramp

The transition from idle to training is seamless because both states produce the
same `--flare` value: `IDLE_SIGNAL` returns `0.5` when the CSS var is unset (no
training), and `setVar('--flare', '0.5')` sets the same value when the mapping
first binds. There is no particle-count jump when a training run starts. The
first metrics event then pushes the signal upward.

## Glow visibility

The secondary orange hotspot glow particles gate on `sig > 0.4`. With the
baseline lifted to `0.5`, they are now visible in **every state**: idle, training
baseline, and full training. Previously they only appeared mid-run when
`grad_norm` pushed `--flare` above 0.4.

## Code references

- `anvil/api/static/js/themes/solarflare.js` — `solarFlareMapping` baseline and metrics formula
- `anvil/api/static/js/theme/particle-system.js` — `registerEffect('flare', ...)` BASE/MAX constants
- `anvil/api/static/js/theme/particle-system.js` — `IDLE_SIGNAL = 0.5`, `readSignal()` unset detection

## Related

- [[Discoveries/particle-canvas-always-on-idle-baseline]] — The original idle-signal mechanism that makes this work
- [[Discoveries/signal-gated-decorations-invisible-at-rest]] — Contrast: themes that are *invisible* at rest vs themes that should have baseline presence
- [[Discoveries/theme-mapping-excited-fake-metrics-grad-norm]] — Excited mode injects fake grad_norm for grad-norm-driven mappings
