---
title: Hyperspace Grid Floor — Perspective Animation Debug & Fix
type: session-log
tags:
  - type/session-log
  - domain/ui
created: '2026-06-26'
updated: '2026-06-26'
source: agent
related:
  - Discoveries/css-background-position-dead-on-perspective-transform
  - Discoveries/overflow-hidden-ancestor-breaks-position-fixed-pseudo-element
  - Discoveries/css-perspective-grid-floor-subpixel-flicker
  - Reference/theme-creation-guide
aliases:
  - Hyperspace Grid Floor Animation Fix
  - Perspective Grid Floor Debug Session
---
# Session: Hyperspace Grid Floor — Perspective Animation Debug & Fix

**Date**: 2026-06-26
**Status**: Draft

## Summary

Extended the hyperspace theme's wireframe grid floor to reach further into the background and made it visibly animated. Two non-obvious root causes were discovered and fixed: (1) `overflow: hidden` on `.app-shell` and `body` was silently breaking `position: fixed` on pseudo-elements, causing all CSS changes to be invisible, and (2) `background-position` animation on a perspective-transformed element produces no visible screen-space movement because foreshortening compresses the texture scroll to sub-pixel displacement.

## Final Architecture

The grid floor is now a two-element DOM structure injected into `base.html`:

```html
<div class="hyper-grid" aria-hidden="true">
  <div class="hyper-grid__floor"></div>
</div>
```

- **`.hyper-grid`** — outer container: `position: fixed`, perspective transform, mask-image fade, opacity. Static — never animates.
- **`.hyper-grid__floor`** — inner element: background grid pattern, `animation: translateY(0 → 360px)`. The `translateY` moves the element in the perspective-transformed coordinate space, which projects as visible forward-flight motion in screen space.

## Root Causes Found

### 1. overflow: hidden on ancestor breaks position: fixed on pseudo-elements

`[data-skin="hyperspace"] .app-shell::before` was `position: fixed` but `.app-shell` has `overflow-x: hidden; overflow-y: auto` and `body` has `overflow: hidden`. Any ancestor with `overflow` other than `visible` creates a new scroll/stacking context that contains `position: fixed` descendants — they become fixed relative to that ancestor, not the viewport. The pseudo-element was being clipped inside the scroll box and rendered nowhere visible.

Attempted workarounds (all failed for different reasons):
- Moving to `body::before` — body also has `overflow: hidden`
- Moving to `[data-skin="hyperspace"]::before` (= `html::before`) — animation worked but `background-position` still produced no visible motion

Final fix: real DOM element as a direct child of `<body>` before `.app-shell`.

### 2. background-position animation is invisible on perspective-transformed elements

Animating `background-position` on an element with `perspective() rotateX()` applied produces visually zero movement. The reason: `background-position` shifts the texture in the element's **pre-transform flat coordinate space**. After `rotateX(40–72deg)` + `scale(...)`, the foreshortening crushes the top of the element (the "far distance") to near-zero screen pixels. A 360px background scroll in flat space maps to less than 1px of screen movement at the top of the projected plane — imperceptible.

The fix: animate `translateY` on a child element *inside* the perspective-transformed container. `translateY` moves the element itself in the transformed space, and the entire grid plane shifts — this projects as real visible motion (lines rushing toward the viewer) in screen space.

### 3. Duplicate @keyframes blocks cause undefined animation behavior

During iteration, duplicate `@keyframes hyper-grid-scroll` blocks accumulated in the file. The last block wins in CSS, so earlier `background-position` keyframes were silently overridden by a later `transform` keyframe block — and vice versa. Cleaned up to a single authoritative keyframe block.

## Perspective Tuning Findings

`rotateX` angle is counter-intuitive:

| rotateX | Effect |
|---------|--------|
| Higher (72–82°) | Steeper, more overhead — horizon line moves DOWN — floor covers LESS screen |
| Lower (40–50°) | Shallower — horizon near screen center — floor covers MORE screen |
| scale higher | Zooms in, fewer grid tiles visible, lines appear closer |
| scale lower | Zooms out, more tiles visible, appears higher above floor |

The sweet spot for "high above the floor, deep into the distance": `rotateX(45deg) scale(1.2)` with the outer container extended via `left: -50%; right: -50%; top: -100%` to give the perspective projection room to fill the full viewport width.

## Effects Removed

At user request, all effects other than the grid floor were removed:
- Warp Core Glow (`.app-shell::after`)
- Warped Starfield (`.app-main::before`)
- Surface Rush (`.app-main::after`)
- All associated `@keyframes` and milestone flash overrides

## Files Modified

```
Modified:
  anvil/api/static/css/themes/hyperspace.css   — complete rewrite (grid only)
  anvil/api/templates/base.html                — added .hyper-grid DOM element
```

## Wikilinks

- [[Discoveries/css-background-position-dead-on-perspective-transform]]
- [[Discoveries/overflow-hidden-ancestor-breaks-position-fixed-pseudo-element]]
- [[Discoveries/css-perspective-grid-floor-subpixel-flicker]]
- [[Reference/theme-creation-guide]]
