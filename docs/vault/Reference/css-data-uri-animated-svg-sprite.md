---
title: CSS Data-URI Animated SVG Sprite
type: reference
status: reviewed
created: 2026-06-20
updated: 2026-06-20
tags:
  - type/reference
  - domain/ui
aliases:
  - CSS Data-URI Animated SVG Sprite
  - Animated SVG background-image technique
  - Self-gating reduced-motion SVG
---

# CSS Data-URI Animated SVG Sprite

A reusable technique for rendering a **self-contained, self-animating SVG** as a
CSS `background-image` data URI on a pseudo-element — no DOM nodes, no JS, no
external asset. It was prototyped as the always-on Unicorn mascot
(`[data-skin="unicorn"] .app-shell::after`), which has since been removed pending a
later redesign — see [[Sessions/2026-06-20-unicorn-mascot-flying-sprites]]; the
implementation lives in git history. This note captures the technique independently.

This matters because some visuals must exist **independent of any JavaScript
runtime** (see [[Discoveries/theme-presence-tiers-css-vs-session-gated-js]] — theme
JS only binds when a training session is attached, so always-on decoration must be
pure CSS).

## When to use it

- You need an animated illustration that is present whenever a CSS class/attribute
  is active, with zero JS lifecycle to manage.
- The animation can be expressed in self-contained CSS keyframes (sub-element
  motion: wiggling eyes, prancing legs, flicking tails).
- You want it to honor `prefers-reduced-motion` without any external rule.

## Three rules that make it work

### 1. Percent-encoding (the part that silently breaks)

The string after `data:image/svg+xml,` is URL-decoded by the browser. Inside a
double-quoted `url("...")` you must encode:

- `#` → `%23` for every hex color (`stroke='%23ff1744'`)
- `%` → `%25` for **every** literal percent — this includes both `@keyframes`
  stops (`0%25{...}`) and percentage `transform-origin` values (`50%25 0%25`)

Keep SVG attribute values in **single quotes**, leave `<` `>` `{` `}` raw, and keep
the whole data URI on **one physical line** (a CSS string cannot span newlines).
Forgetting `%25` on a `transform-origin` percentage is the most common silent
failure — it decodes to a malformed token and the animation just doesn't run.

Validate before shipping by percent-decoding the data URI and parsing it as XML
(e.g. `urllib.parse.unquote` → `xml.etree.ElementTree.fromstring`). A clean parse
plus an accounted-for count of remaining `%` (one per legitimate keyframe/origin
percentage) catches every encoding mistake.

### 2. Reduced-motion self-gating (inside the SVG)

SVG-embedded `<style>` supports media queries. Wrap the animation *assignments* in
`@media (prefers-reduced-motion:no-preference){ ... }` so motion only runs when the
user permits it. The drawing stays; only the movement stops. This is fully
self-contained — the host page's reduced-motion rules cannot reach inside a
`background-image` SVG, so it must gate itself.

Note: a host rule like `[data-skin="x"] *` does **not** match pseudo-elements, so the
host stylesheet still needs its own `::after` rule if it also wants to park/disable
the element-level animation (the SVG-internal gate only covers the SVG's own motion).

### 3. Per-element pivots for sub-part animation

To rotate a sub-part (leg, tail) around its own anchor, set
`transform-box: fill-box; transform-origin: 50% 0%` on that element so the origin is
relative to its own bounding box, then animate `transform: rotate(...)`.

## Autonomous "looping at a different spot" without JS

To make a host element traverse the viewport and re-enter at a *different* position
each pass (impossible to randomize in pure CSS), animate **independent properties on
non-harmonic periods** so they never repeat in phase:

- `left` on one period (e.g. 14s linear) — the horizontal sweep / boundary loop
- `top` on a different, non-multiple period (e.g. 17s) — the vertical wander
- `transform` on a fast period (e.g. 1.1s) — flutter/bob/tilt

Because the properties are independent, the animations **compose** (they would
override each other if they all targeted `transform`). Because the periods are
non-harmonic, each horizontal pass occurs at a different height — a deterministic
system that reads as organic variation. See `unicorn-prance-x/y/bob` in
`anvil/api/static/css/themes/unicorn.css`.

## References

- `anvil/api/static/css/themes/unicorn.css` — always-on prancing-unicorn mascot
- [[Discoveries/theme-presence-tiers-css-vs-session-gated-js]]
- [[Reference/theme-creation-guide]]
- [[Sessions/2026-06-20-unicorn-mascot-flying-sprites]]
