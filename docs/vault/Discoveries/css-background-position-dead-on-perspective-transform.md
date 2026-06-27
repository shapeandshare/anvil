---
title: background-position Animation is Invisible on Perspective-Transformed Elements
type: discovery
status: draft
source: agent
aliases:
  - Background Position Dead on Perspective Transform
  - Perspective Transform Kills Background Animation
code-refs:
  - anvil/api/static/css/themes/hyperspace.css
  - anvil/api/templates/base.html
session: 2026-06-26-hyperspace-grid-floor-animation-fix
created: '2026-06-26'
updated: '2026-06-26'
summary: >-
  Animating background-position on an element with perspective() rotateX()
  applied produces no visible screen-space movement. The foreshortening
  compresses texture scroll to sub-pixel displacement at the distant end of the
  plane. Fix: animate translateY on a child element inside the perspective
  container instead.
tags:
  - type/discovery
  - domain/ui
  - status/draft
related:
  - Discoveries/css-perspective-grid-floor-subpixel-flicker
  - Discoveries/seamless-background-position-loop-animation
  - Sessions/2026-06-26-hyperspace-grid-floor-animation-fix
---
# background-position Animation is Invisible on Perspective-Transformed Elements

Animating `background-position` on an element that has `perspective() rotateX()` applied produces no visible movement in screen space, even though the browser reports the animation as running.

## Why It Happens

`background-position` shifts the background texture in the element's **pre-transform flat coordinate space**. After `rotateX(40–72deg)` the element is projected onto the screen with heavy foreshortening: the top of the element (the "far distance" of the floor plane) is compressed to near-zero screen pixels. A 360px background scroll in flat space maps to a fraction of a pixel at the foreshortened top — imperceptible.

Confirmed via Playwright: `getComputedStyle(el).backgroundPosition` reports values like `69px, 43px, 120px` changing each frame, but no visible change is observable in screenshots taken 0.5s apart. The animation is running; the motion is simply invisible after projection.

The effect worsens with steeper `rotateX` angles (higher values = more foreshortening) and with larger `scale()` values that zoom into the near portion of the plane.

## The Fix

Separate the perspective container from the scrolling element:

```html
<div class="hyper-grid">          <!-- perspective transform here, static -->
  <div class="hyper-grid__floor"> <!-- background pattern here, animates translateY -->
  </div>
</div>
```

```css
.hyper-grid {
  transform: perspective(900px) rotateX(45deg) scale(1.2);
  /* mask, opacity, position — never animates */
}

.hyper-grid__floor {
  position: absolute;
  inset: 0;
  bottom: -360px; /* extra canvas so lines fill the frame throughout travel */
  background-image: /* the grid pattern */;
  animation: grid-scroll 4s linear infinite;
}

@keyframes grid-scroll {
  from { transform: translateY(0); }
  to   { transform: translateY(360px); }
}
```

`translateY` on the inner child moves the element itself inside the perspective-transformed space. The entire grid plane physically shifts, which projects as lines rushing toward the viewer — real visible motion in screen space.

The `bottom: -360px` extension ensures that as the floor element scrolls 360px downward each cycle, new grid lines enter from the bottom edge continuously without the container going empty.

## Seamless Looping

`translateY(0 → 360px)` resets at the end of each cycle. Because the background pattern repeats every 120px (major tiles) and 360 = 3 × 120, position `0` and position `360px` are visually identical grid states — the loop is seamless with no visible snap.

## Key Distinction from seamless-background-position-loop-animation

[[Discoveries/seamless-background-position-loop-animation]] documents seamless `background-position` loops on flat (non-transformed) elements. That technique is correct for flat elements. On perspective-transformed elements, use `translateY` on an inner child instead.

## References

- `anvil/api/static/css/themes/hyperspace.css` — `.hyper-grid` and `.hyper-grid__floor`
- `anvil/api/templates/base.html` — DOM structure
- [[Discoveries/css-perspective-grid-floor-subpixel-flicker]] — sibling: moiré aliasing under steep perspective
- [[Discoveries/seamless-background-position-loop-animation]] — the flat-element version of this pattern
- [[Sessions/2026-06-26-hyperspace-grid-floor-animation-fix]]
