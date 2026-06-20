---
aliases:
  - CSS Grid Replacement Techniques
  - Irregular Polygon CSS Technique
created: '2026-06-20T00:00:00.000Z'
source: agent
code-refs:
  - anvil/api/static/css/themes/stainedglass.css
  - anvil/api/static/css/themes/hologram.css
tags:
  - type/discovery
  - domain/ui
title: CSS Techniques for Replacing Rigid Grid Overlays in Behavioral Themes
type: discovery
updated: '2026-06-20T00:00:00.000Z'
---
# CSS Techniques for Replacing Rigid Grid Overlays

## Context

Two behavioral themes (Stained Glass and Hologram) shipped with rigid square-grid atmospheric overlays: orthogonal perpendicular `linear-gradient` masks that created uniform graph-paper/square-tile patterns. These were visually unappealing compared to more organic or sci-fi wireframe patterns.

## Technique 1: Multi-Angle Gradient Came (Stained Glass)

Replace a square-grid mask with three `repeating-linear-gradient` layers at **non-harmonic angles** with **non-matching spacings**:

```css
background:
  repeating-linear-gradient(40deg, transparent 0 84px, rgba(came-color) 84px 87px),
  repeating-linear-gradient(-35deg, transparent 0 69px, rgba(came-color) 69px 72px),
  repeating-linear-gradient(18deg, transparent 0 102px, rgba(came-color) 102px 105px),
  /* base gradient(s) below */
  conic-gradient(...);
```

**Key parameters**:
- Angles should differ by > 15° to avoid near-parallel lines
- Spacings should have no simple common divisor (87, 72, 105 — none divide evenly into another)
- Came line width ≈ 3px for stained glass (scales with tile size, ~2% of spacing)
- Came opacity ≈ 0.5: intersections compound naturally (1 - (1-0.5)³ = 0.875 at triple cross)
- Tile size (160×160px in this case) should match the LCM-approximation of the spacings

**Advantages**: Pure CSS, no SVG, no mask compositing, no JavaScript. Lightweight and debuggable.

## Technique 2: SVG Data URI Hex Grid (Hologram)

Replace a square-grid background with an inline SVG hexagon pattern stored as a CSS custom property:

```css
[data-skin="hologram"] {
  --hex-grid: url("data:image/svg+xml,%3Csvg xmlns='...'%3E%3Cdefs%3E%3Cpattern ...%3E%3C/pattern%3E%3C/defs%3E%3Crect fill='url(%23h)'/%3E%3C/svg%3E");
}
```

**Hex tile math** (flat-top, R=20):
- Tile width: 3×R = 60px
- Tile height: √3×R ≈ 34.64px (one row of alternating columns)
- Four hexes per tile: (0,0), (34.64,0) in row 1; (30,17.32), (64.64,17.32) in row 2 (offset)

Element definitions for the SVG `<path>`:
```
M-17.32,-10 L17.32,-10 L34.64,0 L17.32,10 L-17.32,10 L-34.64,0 Z         -- hex at (0,0)
M17.32,-10 L51.96,-10 L69.28,0 L51.96,10 L17.32,10 L0,0 Z                  -- hex at (34.64,0)
M12.68,7.32 L47.32,7.32 L64.64,17.32 L47.32,27.32 L12.68,27.32 L-4.64,17.32 Z  -- hex at (30,17.32)
M47.32,7.32 L81.96,7.32 L99.28,17.32 L81.96,27.32 L47.32,27.32 L30,17.32 Z      -- hex at (64.64,17.32)
```

**Edge cases**:
- SVG data URIs in CSS custom properties: `%` in `100%` → `100%25`; `#` in `url(#id)` → `url(%23id)`
- Use `stroke-opacity` instead of `rgba()` in SVG for broader renderer compatibility
- The pattern tile height (34.64px) is non-integer — no visible seams in modern browsers

## When to Use Each

| Pattern | Best for | Complexity |
|---------|----------|------------|
| Multi-angle gradient | Organic/irregular shapes (glass, mosaic, fabric) | Low — CSS only |
| SVG pattern | Regular geometric tiling (hex, diamond, honeycomb) | Medium — SVG URL encoding |
| Multiple mask intersection | Precise cutout shapes | High — browser `mask-composite` support varies |
