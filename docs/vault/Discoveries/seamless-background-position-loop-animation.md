---
aliases:
  - Seamless CSS Loop Animation
  - Background-Position Clean Repeat
code-refs:
  - anvil/api/static/css/themes/hyperspace.css
created: '2026-06-20'
related:
  - '[[Sessions/2026-06-20-hyperspace-theme-warp-effects]]'
session: 2026-06-20-hyperspace-theme-warp-effects
source: agent
status: draft
summary: >-
  Using background-position animation on repeating-linear-gradient to create
  seamless (zero-pop) loop animations for CSS-only warp-speed visual effects.
  The key: animate by exact multiples of the pattern repeat interval.
tags:
  - type/discovery
  - domain/ui
title: Seamless background-position Loop Animation
type: discovery
updated: '2026-06-20'
---
Animate `background-position` on a `repeating-linear-gradient` by the **exact pattern repeat interval** — the loop is mathematically seamless because the pattern tile at position `0` is identical to the pattern tile at position `-N` (where N is any multiple of the total repeat width).

## The Problem

CSS `transform: scale()` or `background-size` animations for warp/zoom effects always pop when the animation resets, because the interpolated value jumps back to its starting point. `ease-in-out` only smooths the curve within the cycle — the hard reset remains.

## The Technique

```css
/* Pattern with total repeat width of 44px */
background: repeating-linear-gradient(
  0deg,
  transparent 0 5px,
  rgba(157, 123, 255, 0.12) 5px 6px,
  transparent 6px 12px,
  ...
  transparent 37px 44px
);

/* Scroll by 88px (44px × 2 = exact multiple) — zero pop */
@keyframes seamless-scroll {
  from { background-position: 0 0; }
  to   { background-position: 0 -88px; }
}
```

## Requirements

1. **Calculate total repeat width** — add up all stop positions in the `repeating-linear-gradient`. The last stop position IS the repeat width.
2. **Animate by an exact multiple** — use `2x` (or any integer multiple) as the displacement. At `2x`, every tile has scrolled by exactly 2 full pattern widths, so position `-2W` is visually identical to position `0`.
3. **Use `linear` easing** — `ease-in-out` would make the scroll slow at the start/end of each cycle, which draws attention to the reset. `linear` keeps the motion constant and the reset invisible.
4. **Multiple layers** — comma-separate `background-position` values for multi-layer backgrounds: `from { background-position: 0 0, 0 0; } to { background-position: 0 -88px, 84px 0; }`.

## When to Use

- Any scroll/streak/track effect that needs to loop without visual artifacts
- Warp-speed surface rush, racing stripes, conveyor belts, scrolling terrain
- Avoids the need for JavaScript `requestAnimationFrame` or canvas for simple patterned motion

## When NOT to Use

- Non-repeating background patterns (cannot tile seamlessly by default)
- Random or organic motion that shouldn't look tiled
- Zoom/perspective effects that need scale animation (these inherently need a different approach — consider a cross-fade between two offset elements instead)

## Hyperspace Theme Application

Applied in `anvil/api/static/css/themes/hyperspace.css` for the `::after` surface-rush effect — horizontal bars scroll upward at 4s per cycle (44px × 2 = 88px displacement, `linear` timing), with speed modulated by `--velocity` via `animation-duration`.

## See Also

- [[Discoveries/Discoveries|Discoveries]]
