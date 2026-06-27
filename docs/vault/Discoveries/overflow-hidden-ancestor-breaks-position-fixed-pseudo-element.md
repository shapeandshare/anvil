---
title: 'overflow: hidden Ancestor Silently Breaks position: fixed on Pseudo-Elements'
type: discovery
status: draft
source: agent
aliases:
  - Overflow Hidden Breaks Fixed Pseudo-Element
  - Pseudo-Element Fixed Position Clipped by Overflow
code-refs:
  - anvil/api/static/css/base.css
  - anvil/api/static/css/themes/hyperspace.css
  - anvil/api/templates/base.html
session: 2026-06-26-hyperspace-grid-floor-animation-fix
created: '2026-06-26'
updated: '2026-06-26'
summary: >-
  An overflow: hidden or overflow: auto ancestor creates a new scroll container
  that contains position: fixed descendants, including pseudo-elements. The
  element renders clipped/invisible rather than viewport-fixed. Real DOM
  elements placed before the overflow ancestor are the reliable fix.
tags:
  - type/discovery
  - domain/ui
  - status/draft
related:
  - Discoveries/css-transform-breaks-position-fixed-modal
  - Sessions/2026-06-26-hyperspace-grid-floor-animation-fix
---
# overflow: hidden Ancestor Silently Breaks position: fixed on Pseudo-Elements

An `overflow: hidden` or `overflow: auto` ancestor creates a new scroll container. Any `position: fixed` descendant — including pseudo-elements — becomes fixed relative to that ancestor rather than the viewport. The element renders clipped inside the ancestor's box and may be entirely invisible.

## The Symptom

CSS changes to a `position: fixed` pseudo-element have no visible effect, regardless of how many properties are modified. The browser reports the element as existing with correct computed styles, but nothing changes on screen.

## Root Cause

In the anvil layout:

```
body { overflow: hidden }               ← new scroll container
  .app-shell { overflow-y: auto;        ← new scroll container
               overflow-x: hidden }
    .app-shell::before { position: fixed } ← contained by .app-shell, not viewport
```

Both `body` and `.app-shell` have `overflow` set to non-`visible` values. Any `position: fixed` pseudo-element on `.app-shell` is contained by `.app-shell`'s scroll box — it does not escape to the viewport. Changes to `inset`, `transform`, or `background-position` on the pseudo-element move it within `.app-shell`'s coordinate space, which may not map to any visible area.

This is a CSS specification behavior, not a browser bug: `overflow: hidden` (and `overflow: auto`) establish a new formatting context that contains fixed-position descendants.

## The Fix

Place visual effect elements as real DOM nodes **before** the overflow ancestors in the document, not as pseudo-elements on overflow containers:

```html
<body>
  <div class="hyper-grid" aria-hidden="true">  <!-- outside .app-shell -->
    <div class="hyper-grid__floor"></div>
  </div>
  <div class="app-shell"> ... </div>
</body>
```

`position: fixed` on `.hyper-grid` works correctly because `body` is its nearest ancestor with overflow — but `body { overflow: hidden }` still creates a context. Moving to a child of `body` that precedes the overflow containers is the reliable escape hatch.

## Relationship to transform-breaks-fixed

[[Discoveries/css-transform-breaks-position-fixed-modal]] documents the analogous case: `transform` on an ancestor breaks `position: fixed`. Both share the same fix: place fixed elements outside the problematic ancestor in the DOM.

The `overflow` variant is more insidious because:
1. `overflow: hidden` on a layout shell is ubiquitous and rarely documented as a containing-block creator
2. Pseudo-elements cannot be moved in the DOM — they always belong to their host element
3. The failure mode is invisible: computed styles look correct, the element exists, but nothing changes on screen

## Diagnostic

Use Playwright or DevTools to confirm the element is rendering:

```javascript
const cs = window.getComputedStyle(el, '::before');
// position: fixed ✓, animation: running ✓, opacity: 0.3 ✓
// but nothing visible → suspect overflow ancestor containment
```

If computed styles look correct but nothing is visible, check every ancestor for `overflow: hidden`, `overflow: auto`, `overflow: scroll`, or `transform` — any of these contains fixed descendants.

## References

- `anvil/api/static/css/base.css` — `body { overflow: hidden }` and `.app-shell { overflow-y: auto; overflow-x: hidden }`
- `anvil/api/static/css/themes/hyperspace.css` — `.hyper-grid` (the real-DOM fix)
- `anvil/api/templates/base.html` — placement of `.hyper-grid` before `.app-shell`
- [[Discoveries/css-transform-breaks-position-fixed-modal]] — the transform variant of the same problem
- [[Sessions/2026-06-26-hyperspace-grid-floor-animation-fix]]
