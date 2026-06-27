---
title: Radial-Gradient Center Bloom for Theme Overlays
type: discovery
tags:
  - type/discovery
  - domain/ui
created: '2026-06-26'
updated: '2026-06-26'
source: agent
aliases:
  - Radial-Gradient Center Bloom for Theme Overlays
code-refs:
  - anvil/api/static/css/themes/prism.css
related:
  - Sessions/2026-06-26-prism-theme-enhancements-and-removal
  - Reference/theme-creation-guide
---

# Radial-Gradient Center Bloom for Theme Overlays

A CSS technique for making a theme's background gradient effect more visible in the center of the screen, where `linear-gradient` tends to produce a muddy blend of all color stops.

## The Problem

A full-viewport `linear-gradient(135deg, ...)` with multiple color stops creates a diagonal band. The center of the screen corresponds to the middle of the gradient band, where many HSL stops overlap and blend — producing a washed-out muddy mix rather than distinct spectrum colors.

## The Solution

Layer a `radial-gradient` **on top** of the `linear-gradient`. The radial gradient is centered at `50% 50%` (dead center of the viewport) with an elliptical shape that covers roughly 60-70% of the screen before fading to transparent:

```css
background:
  /* Top layer: central bloom */
  radial-gradient(
    ellipse 70% 60% at 50% 50%,
    hsl(calc(var(--hue, 0) + 30),  100%, 88%) 0%,
    hsl(calc(var(--hue, 0) + 120), 100%, 75%) 25%,
    hsl(calc(var(--hue, 0) + 240), 100%, 62%) 50%,
    transparent 72%
  ),
  /* Bottom layer: peripheral coverage */
  linear-gradient(135deg, ...);
```

## Key Parameters

- **Shape**: `ellipse 70% 60%` — wider than tall, matching a typical landscape viewport
- **Position**: `at 50% 50%` — exact center
- **Stops**: Use triadic hue offsets (e.g. +30°, +120°, +240°) from the theme's base hue to produce a colorful center bloom
- **Lightness**: 10-15 points higher than the linear gradient stops for the center to pop
- **Fade**: `transparent 72%` — smooth edge fade into the linear gradient underneath
- **Opacity + filter**: The surrounding `opacity` and `filter: saturate()` apply to the entire multi-background, so the bloom inherits the same intensity controls

## When to Use

Any theme with a full-viewport gradient overlay that needs the center area to be more visually prominent. Particularly useful for:
- Rainbow/prismatic spectrum overlays
- Radial glow effects
- Center-focused ambient lighting

## Discovery Context

First applied to the Prism theme during the 2026-06-26 enhancement rounds, then removed along with the theme. The technique itself remains available for future themes.

## References

- [[Sessions/2026-06-26-prism-theme-enhancements-and-removal]]
- [[Reference/theme-creation-guide]]