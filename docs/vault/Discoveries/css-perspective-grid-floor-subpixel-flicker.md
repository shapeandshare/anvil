---
title: 'CSS Perspective Grid Floor: Sub-Pixel Line Flicker (Moiré Shimmer)'
type: discovery
tags:
  - type/discovery
  - domain/ui
created: '2026-06-20T00:00:00.000Z'
updated: '2026-06-20T00:00:00.000Z'
source: agent
aliases:
  - Perspective Grid Flicker
  - Grid Floor Moiré Shimmer
code-refs:
  - anvil/api/static/css/themes/grid.css
status: draft
---
# CSS Perspective Grid Floor: Sub-Pixel Line Flicker (Moiré Shimmer)

**Discovered**: 2026-06-20, while building the Grid theme's receding "light-grid floor".

## The Symptom

A `repeating-linear-gradient` grid laid flat on the ground plane via
`transform: perspective(...) rotateX(70deg)` and scrolled toward the viewer
(animated `background-position`) **flickers/shimmers along the bottom of the
screen** — a restless, strobing twinkle, worst near the horizon and worst in
motion.

## Root Cause — Sub-Pixel Aliasing Under Steep Perspective

The grid lines are crisp 2px bands. The `rotateX` tilt foreshortens the plane:
rows of the texture that are "far away" (near the horizon) get compressed into
**less than one device pixel** of screen height. A 2px line squeezed below 1px
cannot be drawn faithfully — the rasterizer must decide which pixel(s) it lands
in. As the animation advances `background-position`, each line crosses pixel
boundaries every frame, so the rasterizer's choice flips frame-to-frame. That
flip **is** the flicker. It's classic moiré/aliasing between the texture's
spatial frequency and the screen's pixel grid, amplified by motion.

Two things make it worse:

1. **Hard-edged lines** (`solid 79px → solid 81px → transparent`) have infinite
   spatial frequency at the edge — the worst possible input for a minifying
   sampler.
2. **A steep angle** (`rotateX(70deg)`) crushes a huge depth range into a few
   pixels near the horizon, so a large band of lines is all sub-pixel at once.

## The Fix — Four Compounding Mitigations

```css
[data-skin="grid"] .app-main::before {
  /* 1. SOFT-EDGED LINES: ramp transparent→solid→transparent so the edges are
        pre-anti-aliased and degrade gracefully when minified below 1px. */
  background-image:
    repeating-linear-gradient(to right,
      transparent 0, transparent 78px,
      rgba(var(--grid-rgb), 0.6) 80px,
      transparent 82px, transparent 160px),
    repeating-linear-gradient(to bottom,
      transparent 0, transparent 38px,
      rgba(var(--grid-rgb), 0.5) 40px,
      transparent 42px, transparent 80px);

  /* 3. FADE OUT THE FAR REGION: the most-compressed (worst-aliasing) rows live
        near the horizon — mask them away entirely instead of fighting them. */
  mask-image: linear-gradient(to bottom, transparent 22%, #000 58%, #000 100%);

  /* 2. GENTLER TILT + DEEPER PERSPECTIVE: less foreshortening => fewer rows
        crushed sub-pixel. */
  transform: perspective(60vh) rotateX(58deg);
  transform-origin: bottom center;

  /* 4. GPU COMPOSITING HINTS + SLOWER SCROLL: stabilize the layer and reduce
        the per-frame strobe rate. */
  backface-visibility: hidden;
  will-change: background-position;
  animation: grid-floor 2.4s linear infinite; /* was 1.6s */
}
```

Ranked by impact: **(3) fading the far region** is the single biggest win
(it removes the pixels that can't be drawn cleanly), followed by
**(1) soft edges** and **(2) the gentler angle**. **(4)** is polish.

## Heuristics / Takeaways

- **Never animate a hard-edged high-frequency texture through a steep
  perspective minification.** Either soften the texture, reduce the
  minification, or clip the minified region.
- A `mask-image` that fades the *receding* end of a perspective plane is almost
  always desirable anyway — it doubles as the "fades into the distance" look and
  as the anti-aliasing fix.
- When you change the base `transform`'s `perspective(...)`/`rotateX(...)`, you
  MUST update **every keyframe** that re-declares `transform` (e.g. a shake
  animation). A mismatched perspective between the base rule and a state
  keyframe causes a visible snap when that state toggles. In Grid, the `derez`
  divergence shake (`grid-derez`) had to be re-pinned from the old
  `perspective(36vh) rotateX(70deg)` to the new `perspective(60vh) rotateX(58deg)`.

## Where This Lives

- `anvil/api/static/css/themes/grid.css` — `.app-main::before` (the grid floor)
  and the `grid-derez` divergence keyframes.

## Related

- [[Reference/theme-creation-guide|Theme Creation Guide]]
- [[Discoveries/canvas-particle-amplitude-vs-frequency-perceived-speed|Particle Perceived Speed Trap]] — sibling motion-perception gotcha
- [[Sessions/2026-06-20-grid-theme-and-flicker-fix|Session: Grid Theme + Flicker Fix]]
