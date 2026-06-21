---
title: Signal-Gated Decorations Are Invisible at Rest
type: discovery
status: draft
source: agent
related:
  - '[[Discoveries/theme-presence-tiers-css-vs-session-gated-js]]'
  - '[[Reference/theme-creation-guide]]'
  - '[[Sessions/2026-06-20-vinyl-theme-reroll-tape-deck]]'
code-refs:
  - anvil/api/static/js/themes/vinyl.js
  - anvil/api/static/css/themes/vinyl.css
  - anvil/api/static/js/theme/theme-manager.js
session: 2026-06-20-vinyl-theme-reroll-tape-deck
tags:
  - type/discovery
  - domain/ui
  - status/draft
aliases:
  - Signal-Gated Decorations Are Invisible at Rest
created: '2026-06-20'
updated: '2026-06-20'
---
When a theme builds its *primary* decorative furniture inside the session-gated JS `mapping()` (e.g. DOM-injected sprites or gauges), that furniture is absent on every static page and before any training run begins — so a theme can look almost bare at rest even though it appears "fully applied."

The Vinyl tape-deck pivot (see [[Sessions/2026-06-20-vinyl-theme-reroll-tape-deck]]) made this concrete. Its centerpiece visuals — the two rotating tape reels, the tape band, and the two VU meters — are created by `buildTapeDeck()` inside `vinylMapping()` in `anvil/api/static/js/themes/vinyl.js`, which is only invoked when the theme manager binds a signal bus with an attached session. The manager short-circuits binding otherwise (`bindMapping` checks for an attached session in `anvil/api/static/js/theme/theme-manager.js`), and a session is only attached when a live training run is streaming metrics over SSE. The theme's CSS layer loads unconditionally, but the only always-on visual it defines is the warm amber glow on `.app-main::before`. The result: selecting Vinyl on, say, the datasets page or the idle dashboard shows just the warm glow — the reels and meters do not exist until a run starts.

This is the same structural constraint documented in [[Discoveries/theme-presence-tiers-css-vs-session-gated-js]], but from the opposite design choice. That note's example (the Unicorn mascot) moved an always-on element *out of* JS *into* CSS to guarantee presence. Vinyl deliberately accepted the inverse: its reels/meters are conceptually "the machine running," so it is defensible for them to appear only while training. The lesson is to make that an explicit decision, not an accident — if a theme should have obvious presence at rest, its at-rest furniture must live in the CSS layer (token blocks, `.app-main` pseudo-elements, or an `.app-shell::after` anchor), and only signal-*responsive* behavior should live in `mapping()`.

A practical corollary for reviewing or demoing a theme: evaluate it both with and without an active training session. A theme that reads well mid-run can be nearly invisible on a cold page, and vice versa.

## References

- `anvil/api/static/js/themes/vinyl.js` — `buildTapeDeck()` inside the session-gated `mapping()`
- `anvil/api/static/css/themes/vinyl.css` — the only always-on visual is the `.app-main::before` warm glow
- `anvil/api/static/js/theme/theme-manager.js` — `bindMapping` / `bindSession` gating
- [[Discoveries/theme-presence-tiers-css-vs-session-gated-js]]
- [[Reference/theme-creation-guide]]
- [[Sessions/2026-06-20-vinyl-theme-reroll-tape-deck]]
