---
title: CSS Multi-Background-Position Parallax Particle Field
type: discovery
aliases:
  - CSS Multi-Background-Position Parallax
  - Pseudo-Element Parallax Particle Field
created: '2026-06-21T04:07:13.000Z'
updated: '2026-06-21T04:07:13.000Z'
source: agent
status: draft
related:
  - '[[Reference/theme-creation-guide]]'
  - '[[Reference/particle-effect-authoring]]'
  - '[[Discoveries/css-grid-overlay-replacement-techniques]]'
code-refs:
  - anvil/api/static/css/themes/ash.css
  - anvil/api/static/js/themes/ash.js
  - anvil/api/static/js/theme/particle-system.js
session: '[[Sessions/2026-06-20-ash-soot-parallax-overhaul]]'
summary: Layered falling-particle depth in a single CSS pseudo-element via one keyframe that scrolls each background layer by its own tile height; plus the dark-on-dark contrast trap and the unregistered-particleConfig fallback.
tags:
  - type/discovery
  - domain/ui
---

A single CSS pseudo-element can render a multi-band parallax particle field — without a canvas, without JavaScript, and without one element per depth band — by exploiting the fact that the `background-position` property is a *list* and each entry animates independently within one keyframe.

## The technique

A behavioral theme's atmospheric layer normally lives in `.app-main::before` / `::after` (see `anvil/api/static/css/themes/`). The Ash theme needed falling soot with real depth, but a pseudo-element gives only two layers and a single `background-position` animation appears to move everything in lockstep. The escape hatch: stack many `radial-gradient` "dot" layers in one `background-image` list, give each a tile via `background-size`, and then animate `background-position` with a *per-entry* `to` list whose Y delta equals that entry's tile height. Because each layer scrolls by a different distance over the same duration, near bands fall faster than far bands — genuine parallax from one element and one keyframe.

The Ash field uses four bands (NEAR/MID/FAR/DUST) at tile sizes 300/190/110/70px, giving a near:far speed ratio of roughly 4.3:1. The three parallel lists — `background-image`, `background-size`, and the keyframe `to` positions — MUST stay index-aligned across all entries (19 in this case); a misaligned list silently mis-sizes or mis-scrolls a layer with no error. The source carries band-label comments precisely to keep those three lists in sync, and a count check (all three lists equal length) is the cheapest correctness guard.

Two refinements that make it read as falling soot rather than a static texture: each `radial-gradient` ends in an explicit `transparent` stop so dots are crisp flecks instead of fuzzy haze, and a second `soot-sway` keyframe applies a small horizontal `translateX` oscillation to the whole element for wind. Because the sway moves the element (not the background), it does not break the per-layer parallax. The element is also inset past the viewport edges (`inset: -10%`) so the sway never reveals a hard border.

## The dark-on-dark contrast trap

The first iteration was invisible — "no effects." Two compounding causes. First, soot is *conceptually* dark, so the dots were authored as dark grey (RGB ~50–70) on a near-black background (`--bg: #0e0c0a`), i.e. no luminance contrast. Real falling ash reads light because flecks catch ambient light; the fix was to author the dots as *light* warm-grey (RGB ~120–230, brightest in the near band) and let per-dot alpha carry the density. Second, the element `opacity` was driven near zero at rest, multiplying the whole field into nothing; a high opacity floor (≈0.55) with contrast living in per-dot alpha keeps the field visible at idle while still responding to signal. The general rule for these atmospheric layers: contrast belongs in the particle's own color/alpha, not in a low element-level opacity.

## The unregistered `particleConfig.type` fallback

The original Ash declared `particleConfig: { type: 'ember' }`, which binds the shared **canvas** ember effect (see `anvil/api/static/js/theme/particle-system.js` and [[Reference/particle-effect-authoring]]). Renaming it to a made-up `type: 'soot'` did not throw: `particle-system.js` looks up `effects[config.type]`, finds nothing, and silently falls back to `setParticleAttr('default')` — i.e. no canvas, CSS pseudo-elements left visible (suppression is only enabled for `type: 'none'`). So an unregistered effect name behaves like `type: 'css'` by accident. This masks a real authoring mistake: if the entire effect is pseudo-element CSS, the config MUST say `type: 'css'`; an invented name implies a registered canvas effect that does not exist. The combination of dropping the real `ember` canvas effect and shipping an invisible dark-on-dark CSS layer is what produced the original "I don't see any effects."

## References

- `anvil/api/static/css/themes/ash.css` — the four-band parallax field, `soot-fall` + `soot-sway` keyframes, and the divergence `ashfall` state
- `anvil/api/static/js/themes/ash.js` — `--ash` signal mapping (loss → fall density) and the corrected `particleConfig: { type: 'css' }`
- `anvil/api/static/js/theme/particle-system.js` — `apply()` effect lookup and the unknown-type → `default` fallback (around the `effects[config.type]` guard)
