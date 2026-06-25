---
title: CSS Transform Breaks Position Fixed Modal
type: discovery
tags:
  - type/discovery
  - domain/ui
  - status/draft
created: '2026-06-20'
updated: '2026-06-20'
aliases:
  - Transform Ancestor Breaks Fixed Positioning
  - Modal Position Fixed Bug
related:
  - Reference/overflow-clipping-pattern
session: 2026-06-20-forge-modal-fix
source: agent
summary: >-
  CSS transform on any ancestor creates a new containing block for position:
  fixed, breaking viewport-relative modal positioning. Fix: render modals at
  <body> level via Jinja2 block inheritance.
code-refs:
  - anvil/api/templates/base.html
  - anvil/api/templates/archetypes/training.html
  - anvil/api/static/css/components.css
---
## Problem

The forge confirmation modal (`#train-confirm-modal`) appeared stuck to the bottom of the viewport instead of centered. It used `position: fixed; inset: 0; display: flex; align-items: center; justify-content: center;` which should center the dialog — yet it rendered at the bottom.

## Root Cause

CSS `transform` (and `filter`, `will-change: transform`, `perspective`) on any **ancestor** of a `position: fixed` element creates a **new containing block** for that element. The fixed positioning becomes relative to the transformed ancestor instead of the viewport.

The modal was nested inside:

```
.app-main  ← themes apply transform via animation or static rules
  └── .training-dashboard
       └── .training-output.section-card
            └── .modal-overlay (position: fixed)
```

Several themes apply `transform` to `.app-main`:
- **Vinyl** — `animation: vinyl-wobble` with `transform: rotate(...)` keyframes
- **Tectonic** — `animation: tectonic-tremor` with `transform: translate(...)` keyframes  
- **Reactor** — `transform: translate(-50%, -50%)` on `.app-main::after`

Any of these break `position: fixed` on descendants, making the modal's `inset: 0` relative to `.app-main`'s coordinate space — which after scrolling places it at the bottom of the viewport.

## Fix

Moved the modal HTML out of all transform-bearing ancestors to the `<body>` level using Jinja2 block inheritance:

1. **`anvil/api/templates/base.html`** — Added `{% block modals %}{% endblock %}` right before `</body>`, outside both `.app-shell` and `.app-main`.
2. **`anvil/api/templates/archetypes/training.html`** — Moved the forge modal from inside `.training-output` into `{% block modals %}`. Same element IDs, same JS references.

The modal now renders as a direct child of `<body>`, guaranteed to have no `transform` ancestors. `position: fixed` is truly viewport-relative.

## Reusable Pattern

Any future modal should use `{% block modals %}` in `base.html` rather than nesting inside page content. The block renders at `<body>` level, safe from any ancestor `transform`/`filter`.

### Checklist for adding a new modal

- [ ] Add modal HTML to a `{% block modals %}` override in the page template (inherits from `base.html`)
- [ ] Never nest a `.modal-overlay` inside scrollable content or elements with `transform`
- [ ] Modal overlay CSS must use: `position: fixed; inset: 0; z-index: 10000; display: flex; align-items: center; justify-content: center;`
- [ ] JS: `document.getElementById('...').style.display = 'flex'` to show, `'none'` to hide
- [ ] Click handler on overlay that closes when `e.target === overlay` allows click-away dismissal

## References
- [[Discoveries/Discoveries|Discoveries]]

- `anvil/api/templates/base.html` — `{% block modals %}` at line 128
- `anvil/api/templates/archetypes/training.html` — `{% block modals %}` override at line 1350, JS modal logic at lines 1020-1084
- `anvil/api/static/css/components.css` — `.modal-overlay` and `.modal-dialog` rules (lines 469-628)
- [MDN: CSS position fixed and transform](https://developer.mozilla.org/en-US/docs/Web/CSS/position#fixed) — "The element is removed from the normal document flow... and its containing block is established by the viewport... **except** when the element's ancestor has `transform`, `perspective`, or `filter` property set to something other than `none`"
- `anvil/api/static/css/themes/vinyl.css` — `.app-main` transform animation (line 67-71)
- `anvil/api/static/css/themes/tectonic.css` — `.app-main` transform animation (line 55-61)
