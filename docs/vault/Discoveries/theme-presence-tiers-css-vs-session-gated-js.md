---
aliases:
  - Theme Presence Tiers — CSS vs Session-Gated JS
code-refs:
  - anvil/api/static/js/theme/theme-manager.js
  - anvil/api/static/js/themes/unicorn.js
  - anvil/api/static/css/themes/unicorn.css
created: '2026-06-20'
related:
  - '[[Reference/theme-creation-guide]]'
  - '[[Reference/css-data-uri-animated-svg-sprite]]'
  - '[[Sessions/2026-06-20-unicorn-mascot-flying-sprites]]'
session: 2026-06-20-unicorn-mascot-flying-sprites
source: agent
summary: >-
  A behavioral theme's JS mapping() only runs while a training signal bus is
  attached, so anything that must be visible at rest (with no active run) has to
  live in the CSS layer, not the JS module. Themes therefore have two distinct
  presence tiers.
tags:
  - type/discovery
  - domain/ui
  - status/draft
title: Theme Presence Tiers — CSS vs Session-Gated JS
type: discovery
updated: '2026-06-20'
---

A behavioral theme appears to be "active" the moment a user selects it, but its
**JavaScript is not always running**. The theme manager only binds a theme's
`mapping(bus, effectLevel)` when a signal bus with an attached session exists —
`bindMapping` short-circuits on `!bus || !bus.session()` in
`anvil/api/static/js/theme/theme-manager.js`. The bus is attached via
`ThemeManager.bindSession(session)`, which only happens when a live training run is
streaming metrics over SSE.

The consequence: any visual a theme produces **from inside its `mapping()`**
(injected DOM sprites, signal-driven CSS variables, event-driven bursts) is absent
whenever there is no active run — i.e. on every static page, and on the dashboard
before training starts. This is easy to miss because the theme's CSS layer (tokens,
pseudo-element ambience) loads unconditionally via `ensureLayer`, so the theme still
*looks* applied; only the dynamic behavior is dormant.

This splits theme visuals into two presence tiers:

1. **Session-gated (JS)** — sprites/effects driven by `metrics` / `milestone` /
   `complete` / `divergence`. Present only during/around a run. This is the correct
   home for anything that should *respond* to training.
2. **Always-on (CSS)** — decoration that must exist regardless of run state. Must be
   implemented in the CSS layer (token blocks, `.app-main` ambient pseudo-elements,
   or a dedicated `.app-shell::after` mascot). The IIFE registration body runs at
   load, but it should only `register()` — it must not start always-on visuals,
   because that would run for every theme/page even when the skin is not selected.

The Unicorn theme demonstrated both: signal-driven floating unicorns + flying
rainbows live in `unicorn.js` (session-gated), while an always-present prancing
mascot was a CSS `background-image` data-URI SVG on `.app-shell::after`
(see [[Reference/css-data-uri-animated-svg-sprite]]). The mascot was later removed
pending a redesign, but the tier distinction it illustrates is unchanged — the
constraint is structural, not specific to that one element.

`.app-shell` is a safe always-on anchor: it exists on every page and has no
transformed ancestor, so a `position: fixed` pseudo-element on it is viewport-relative
and is not clipped by its `overflow`.

## References

- `anvil/api/static/js/theme/theme-manager.js` — `bindMapping` / `bindSession`
- `anvil/api/static/js/themes/unicorn.js` — session-gated sprite overlay
- `anvil/api/static/css/themes/unicorn.css` — always-on `.app-shell::after` mascot
- [[Reference/theme-creation-guide]]
- [[Sessions/2026-06-20-unicorn-mascot-flying-sprites]]
