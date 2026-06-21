---
created: '2026-06-20'
status: draft
source: agent
tags:
  - domain/ui
  - type/session-log
title: Unicorn Mascot + Flying Sprites — 2026-06-20
type: session-log
updated: '2026-06-20'
aliases:
  - Unicorn Mascot + Flying Sprites
---
# Unicorn Mascot + Flying Sprites

**Date**: 2026-06-20
**Context**: User asked to make the existing Unicorn theme "really pop" — SVG
unicorns, googly eyes, floating unicorns, rainbows flying by — then to guarantee a
silly side-profile prancing unicorn with a rainbow trail is always visible.

## What Was Done

### 1. Signal-driven sprite overlay (JS)

Rewrote `anvil/api/static/js/themes/unicorn.js` (80 → ~570 lines) to inject a managed
DOM overlay (`<div class="unicorn-overlay">` on `document.body`, `pointer-events:none`,
`z-index:5`) — the first theme to do live DOM sprite injection rather than pure CSS
pseudo-elements. It builds inline SVG unicorns with **googly eyes** (mismatched,
independently wiggling pupils), drifts them via a single `requestAnimationFrame`
loop, and streaks 6-band **rainbows flying by** across the viewport. Intensity is
signal-driven: lower loss = more sprites + more frequent rainbows; throughput drives
sparkle; `milestone`/`complete` trigger celebratory bursts + hue shift; `divergence`
fades everything to monochrome. Full `teardown()` removes every node/timer/listener/
attr/var.

### 2. Three correctness fixes found in the "double check" pass

- **Memory/perf leak** — `unicornNodes`/`rainbowNodes` were never compacted; culled
  sprites stayed in the arrays and were iterated every frame for the whole run. Now
  the rAF loop rebuilds alive-only arrays each frame.
- **Initial-frame flash** — sprites had no transform until the 2nd rAF frame, briefly
  piling at `(0,0)`. Now the transform is seeded at spawn.
- **Reduced-motion burst hole** — `burst()` did not check `reducedMotion`, so
  milestone bursts in muted mode spawned static orphans that never animated or culled.
  Added the guard.

### 3. Always-on prancing mascot (CSS)

Added `[data-skin="unicorn"] .app-shell::after` in
`anvil/api/static/css/themes/unicorn.css` — a **side-profile unicorn** rendered as a
`background-image` data-URI SVG, present even with no training session. It prances
(legs swing on diagonal pairs via per-element `transform-box: fill-box` pivots),
flicks a rainbow tail, wiggles a googly eye, **trails a 6-band rainbow from its rear**,
and **flies across the screen** (composed `left` 14s / `top` 17s / `transform` 1.1s
animations) re-entering at a new height each pass. Reduced-motion parks it in a
corner; the SVG's own motion self-gates via an in-SVG `prefers-reduced-motion` query.

This was needed because a theme's JS `mapping()` only runs while a signal bus session
is attached — see [[Discoveries/theme-presence-tiers-css-vs-session-gated-js]].

## Key Techniques / Discoveries

- [[Reference/css-data-uri-animated-svg-sprite]] — encoding (`%23`/`%25`),
  self-gating reduced-motion, non-harmonic-period autonomous looping
- [[Discoveries/theme-presence-tiers-css-vs-session-gated-js]] — why always-on
  decoration must be CSS, not the session-gated JS module

## Files Changed

```
Modified:
  anvil/api/static/js/themes/unicorn.js   (DOM sprite overlay, signal mapping, fixes, teardown)
  anvil/api/static/css/themes/unicorn.css (always-on .app-shell::after prancing mascot + flight keyframes)
```

No engine, registration, `base.html`, or test changes — Unicorn was already wired and
in `THEME_IDS`.

## Validation

- Embedded SVGs percent-decode to well-formed XML (verified via `unquote` + XML parse).
- `lsp_diagnostics` clean on both files (only pre-existing shared `!important`
  reduced-motion warnings remain).
- Teardown leaves zero trace (DOM, timers, rAF, listeners, data-attrs, CSS vars).

## Follow-up — Mascot Temporarily Removed

Later the same day the user asked to remove the always-on prancing mascot "for now,
we'll add it back in later". The `[data-skin="unicorn"] .app-shell::after` block (the
data-URI SVG, the `unicorn-prance-x/y/bob` keyframes, and its small-screen +
reduced-motion rules) was deleted from `anvil/api/static/css/themes/unicorn.css`. The
session-gated JS sprite overlay, sparkle field, and theme registration are unchanged.
The full mascot implementation is preserved in git history (this session's diff) for
restoration. The technique notes below remain valid as reusable references.

## Wikilinks

- [[Reference/theme-creation-guide]]
- [[Reference/css-data-uri-animated-svg-sprite]]
- [[Discoveries/theme-presence-tiers-css-vs-session-gated-js]]
- [[Decisions/ADR-031-behavioral-theme-engine]]
- [[Sessions/2026-06-20-unicorn-theme-and-prism-vibrancy]]
