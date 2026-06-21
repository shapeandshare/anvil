---
aliases:
  - Always-On Canvas Particles — Idle Baseline, Layering, Wave Avoidance
code-refs:
  - anvil/api/static/js/theme/particle-system.js
  - anvil/api/static/js/theme/theme-manager.js
  - anvil/api/static/css/base.css
created: '2026-06-20'
related:
  - '[[Reference/theme-creation-guide]]'
  - '[[Discoveries/theme-presence-tiers-css-vs-session-gated-js]]'
  - '[[Sessions/2026-06-20-particle-system-always-on-and-rain-overhaul]]'
session: 2026-06-20-particle-system-always-on-and-rain-overhaul
source: agent
summary: >-
  The canvas particle system is a third theme presence tier that now runs on every
  page (not just during training). Making signal-driven canvas effects visible at rest
  required an idle-signal baseline that distinguishes an unset var from a set "0",
  layering them behind content without washing out the static nav, and avoiding a
  load-time "wave" from re-application and edge-only seeding.
tags:
  - type/discovery
  - domain/ui
  - status/draft
title: Always-On Canvas Particles — Idle Baseline, Layering, Wave Avoidance
type: discovery
updated: '2026-06-20'
---

The behavioral theme system has a `<canvas>` particle layer
(`anvil/api/static/js/theme/particle-system.js`) that is distinct from a theme's
signal-driven CSS-var `mapping()` and from always-on CSS pseudo-elements. It is a
**third presence tier**, and several non-obvious constraints govern making it visible
and stable at rest (i.e. with no active training run). This note records them as a
cluster because they only make sense together.

**Always-on vs training-only.** Originally the manager forced CSS-only particles
unless a training signal bus session was attached, so canvas effects never appeared on
static pages. The manager now always applies the canvas effect in
`theme-manager.js`. The theme's `mapping()` is still session-gated (see
[[Discoveries/theme-presence-tiers-css-vs-session-gated-js]]) — only the *canvas* layer
became unconditional.

**Idle-signal baseline — unset is not zero.** Each effect scales particle count and
opacity by a theme-private signal var (e.g. `--charge`, `--ember`, `--depth`). Those
vars are only written by the (session-gated) mapping, so at rest they were absent and
the effects collapsed to near-invisible. The fix distinguishes two cases that JavaScript
`parseFloat(...) || 0` conflates: a var that is **unset** (no training) should fall back
to a lively baseline, whereas a var explicitly **set** to `"0"` during training should
stay `0`. `readSignal(name)` returns the baseline only when `getPropertyValue` is the
empty string; otherwise it honors the parsed value. A maintainer who "simplifies" this
back to `|| 0` reintroduces the invisible-at-rest bug. The baseline constant is the
single liveliness knob. `readSignalChain(primary, fallback)` applies the same rule to
the one effect that reads a primary-then-fallback pair. Vars that are not intensities
(e.g. a hue rotation) must NOT be routed through the baseline.

**Layering — a positioned z-index:0 canvas still paints over a static sibling.** The
canvas should sit behind page content but above the shell background. Setting it to
`position: fixed; z-index: 0` puts it behind `.app-main` (which owns its own stacking
context via `isolation: isolate`) while staying above the `.app-shell` background. But
CSS stacking paints a *positioned* `z-index:0` element above *non-positioned* (static)
siblings — so the static `.nav-bar` was painted under the canvas and washed out. The
nav must be given its own positive stacking context (`position: relative; z-index: 1`,
with an opaque surface) to stay legible above the particle layer. This is the same
class of stacking subtlety as
[[Discoveries/css-transform-breaks-position-fixed-modal]].

**Wave avoidance — do not rebuild, and seed the whole screen.** A "render, pause, render
again" wave on load had two independent causes. First, `bindSession()` re-applied the
particle effect when the page connected its SSE session, tearing down and rebuilding the
running canvas; since the canvas now always runs from the initial apply, `bindSession`
must only (re)bind the mapping and never re-apply the particles. Second, an effect that
seeds its initial population off-screen (all drops above the top, all embers below the
bottom) visibly fills the viewport edge-to-center on first paint; seeding the initial
population across the **full** viewport makes it look steady immediately and also hides
any momentary main-thread stall during load. The full-screen-seed fix was applied to the
rain effect; other edge-seeding effects can show a milder version of the same wave.

## References

- `anvil/api/static/js/theme/particle-system.js` — `IDLE_SIGNAL`, `readSignal`, `readSignalChain`, canvas `position:fixed; z-index:0`, rain full-screen seed
- `anvil/api/static/js/theme/theme-manager.js` — unconditional `ParticleSystem.apply`; `bindSession` no longer re-applies
- `anvil/api/static/css/base.css` — `.nav-bar { position: relative; z-index: 1 }`; default-scoped `.ambient-particles`
- [[Reference/theme-creation-guide]]
- [[Discoveries/theme-presence-tiers-css-vs-session-gated-js]]
