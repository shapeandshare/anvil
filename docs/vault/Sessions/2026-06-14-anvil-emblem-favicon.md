---
title: Anvil Emblem Re-path + Favicon Set
type: session
tags:
  - type/session
  - domain/ui
  - domain/assets
created: '2026-06-14T00:00:00.000Z'
---

# Session: Anvil Emblem Re-path + Favicon Set

**Date**: 2026-06-14
**Type**: Session Log
**Tags**: [type/session, domain/ui, domain/assets]

## Summary

Replaced the handcrafted left-facing anvil silhouette with a re-pathed version derived from an SVGRepo reference (`anvil-svgrepo-com.svg`). Also created a full favicon set (SVG + apple-touch-icon PNG) and wired it into the app shell.

## Anvil Emblem Re-path

### What changed

The original `anvil-emblem.svg` used a custom left-facing horn (horn tip at `(10,66)`). The reference SVG (svgrepo.com, 32×32) uses an **English-pattern anvil** — horn pointing right, flat face extending left, beveled heel step on the left foot.

### Methodology

The reference path was traced to absolute coordinates in its native 32×32 space, then transformed into the project's 240×160 viewBox using:

```
new_x = (x - 1.146) × 7 + 15
new_y = (y - 6.655) × 7 + 5
```

Scale factor 7× chosen to fill ~87% width / ~94% height of the 240×160 canvas while preserving aspect ratio.

### New emblem landmark coords (240×160 viewBox)

| Feature | Coords |
|---------|--------|
| Horn tip | `(224, 40)` — rightmost, ~25% down |
| Face (main work surface) | `x=60..192, y=5` |
| Heel (lower left extension) | `x=15..60, y=17` |
| Left undercut | `(15,17) → (60,58)` via cubic |
| Waist | left `x=60..94`, right `x=159..192`, at `y=77` |
| Left foot bevel step | `(47,129) → (47,141) → (47,156)` |
| Base bottom | `x=47..212, y=156` |
| Right foot | `x=194..212, y=129` |

### Files updated (3 locations)

All three locations hardcoded the path — all updated together to keep emblem consistent:

- `anvil/api/static/anvil-emblem.svg` — standalone SVG asset (with landmark comments)
- `anvil/api/templates/archetypes/hero.html` — inline SVG in forge section
- `README.md` — inline SVG in repo header

## Favicon Set

### Files created

| File | Details |
|------|---------|
| `anvil/api/static/favicon.svg` | 32×32 SVG, dark `#1c1c1e` bg + orange `#ff9500` anvil; `@media (prefers-color-scheme: light)` switches to `#f2f2f7` bg + `#1c1c1e` anvil. `rx="7"` (~22% radius). Reference path with `-1.5` y-shift to vertically center. |
| `anvil/api/static/apple-touch-icon.png` | 180×180 PNG, black `#000000` bg + orange anvil. Generated from a 180×180 intermediate SVG via `sips`. Reference path with `scale(4.5) translate(3.92, 2.54)` to center in viewport. |

### base.html wiring

Added to `<head>` immediately after `<title>`, before the theme script:

```html
<link rel="icon" href="/static/favicon.svg" type="image/svg+xml">
<link rel="apple-touch-icon" href="/static/apple-touch-icon.png">
```

Static mount at `/static` maps to `anvil/api/static/` (confirmed via `app.py`).

### Tool used for PNG generation

`sips` (macOS built-in image processing tool) — no external dependencies required. `cairosvg`, `magick`, and `rsvg-convert` were all absent from the environment. Pillow was present but lacks SVG rasterisation without cairosvg. `sips` on macOS handles SVG → PNG natively.

## Non-issues

LSP errors surfaced on Python files (`cli.py`, `inference.py`, `torch_engine.py`) during SVG writes — all pre-existing unrelated issues (union syntax, missing torch import, UTC symbol). Not introduced by this session.

## Related

- [[Decisions/ADR-006-ios-theme-overhaul]] — established the forge visual identity (orange, hero emblem)
- [[Sessions/2026-06-14-design-canonization]] — canonised the forge sub-theme and Archetype E
