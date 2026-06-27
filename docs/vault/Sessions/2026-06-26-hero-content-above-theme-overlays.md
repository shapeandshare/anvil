---
title: Hero Content Above Theme Overlays
type: session-log
tags:
  - type/session-log
  - domain/ui
created: '2026-06-26'
updated: '2026-06-26'
source: agent
aliases:
  - 2026-06-26-hero-content-above-theme-overlays
---
# Hero Content Stacking Above Theme Overlays

**Type**: session-log  
**Tags**: type/session-log, domain/ui  
**Created**: 2026-06-26  
**Updated**: 2026-06-26  

## Summary

Hero page content (feature cards, buttons, title, subtitle, tagline) was visually washed out across many themes because theme `.app-main::before`/`::after` pseudo-elements painted on top of hero content. Diagnosed and fixed the stacking context pattern so all hero content renders above all theme atmospheric overlays.

## What Was Tried

### Attempt 1: Per-element z-index bump
- Added `position: relative; z-index: 2` to `.hero-card` (was no position, normal flow)
- Rationale: cards in normal flow paint below positioned `::before`/`::after` pseudo-elements
- **Result**: Cards solid in themes with `::after` at z-index 0-1, but Stormfront's `::after` was at `z-index: 41` — still above cards

### Attempt 2: Normalize theme pseudo-element z-indexes
- Lowered all theme `.app-main::before` to `z-index: 0` and `.app-main::after` to `z-index: 1`
- Fixed: stormfront (41→1), solarflare (41→1), static (40/41→0/1), echo (41→1), oldgrowth (40/41→0/1), unicorn overlay (5→1)
- Left mainframe (40) and pulse (40) unchanged — they're corner cursor/dot elements that don't overlap centered hero cards
- **Result**: Cards at z-index 2 now above all theme layers. But text/buttons still at `z-index: 1` — same as `::after`, and `::after` paints on top (same z-index, later tree order since it's `.app-main`'s last pseudo‑element child)

### Attempt 3: Lift entire `.hero-page` container to `z-index: 2`
- Added `position: relative; z-index: 2` to `.hero-page` — all hero content (text, buttons, cards, forge elements) now paints within this single stacking context
- Theme `::before` (z-index 0) and `::after` (z-index 1) render below `.hero-page` in `.app-main`'s stacking context
- Children keep their internal relative stacking (forge glow/embers at z-index 0, icon/title/buttons at z-index 1, cards at z-index 2)
- **Result**: All hero content solid across all 22 themes

## Root Cause

Two interrelated issues:

1. **Missing stacking context on hero container**: The hero page's content (title, tagline, subtitle, buttons, cards) had no unifying stacking context. Individual elements had `z-index: 1` but the theme's `::after` pseudo-element (also at `z-index: 1`) was `.app-main`'s last rendered child — painting on top of all hero content at the same z-index level.

2. **Inconsistent theme z-index values**: Theme `.app-main::before`/`::after` pseudo-elements used arbitrary z-index values (0, 1, 5, 40, 41) with no convention. Decorative atmospheric overlays (gradients, scanlines, sparkles, noise textures) don't need high z-index values — they should always render below content.

## Files Changed

| File | Change |
|------|--------|
| `anvil/api/static/css/archetypes.css` | `.hero-card` → added `position: relative; z-index: 2`; `.hero-page` → added `position: relative; z-index: 2` |
| `themes/stormfront.css` | `::after` → `z-index: 1` (was 41) |
| `themes/solarflare.css` | `::after` → `z-index: 1` (was 41) |
| `themes/static.css` | `::before` → `z-index: 0` (was 40); `::after` → `z-index: 1` (was 41) |
| `themes/echo.css` | `::after` → `z-index: 1` (was 41) |
| `themes/oldgrowth.css` | `::before` → `z-index: 0` (was 40); `::after` → `z-index: 1` (was 41) |
| `themes/unicorn.css` | `.unicorn-overlay` → `z-index: 1` (was 5) |

## Tags

- `domain/ui` — CSS stacking, z-index, hero page, theme system

## Related

- [[Sessions/2026-06-23-hero-page-footer-stacking-and-layout|Hero Page Footer Stacking and Layout]] — prior hero stacking context fix
- [[Discoveries/theme-decorative-layer-z-index-convention|Theme Decorative Layer Z-Index Convention]] — the convention established by this session
- [[Discoveries/isolation-isolate-stacking-context-paint-order|Isolation: Isolate — Stacking Context Effect on Sibling Paint Order]] — related stacking context mechanics

## Files Changed in Detail

### archetypes.css — 2 edits

```css
.hero-page {
  position: relative;   /* added */
  z-index: 2;           /* added — lifts all hero content above theme ::before/::after */
  display: flex;
  ...
}

.hero-card {
  position: relative;   /* added */
  z-index: 2;           /* added — renders at z-index 2 within .hero-page context */
  ...
}
```

### Theme files — 7 edits across 6 themes

All theme `.app-main::before` pseudo-elements lowered to `z-index: 0`.
All theme `.app-main::after` pseudo-elements lowered to `z-index: 1`.
The `.unicorn-overlay` fixed-position layer lowered to `z-index: 1`.

Left at `z-index: 40`: `mainframe.css` `::after` (bottom-right cursor blink), `pulse.css` `::after` (bottom-right heartbeat dot) — these are small corner elements that don't overlap centered hero content.

### Final Layer Diagram

```
.app-main (isolation: isolate)
├── background
├── normal flow descendants
├── ::before (z-index: 0) — gradients, scanlines, sparkles, warp lines
├── ::after  (z-index: 1) — weft, static noise, flashes, vignettes, overlays
└── .hero-page (z-index: 2) — ALL hero content above theme layers
    ├── z-index: 0 — forge glow, ember particles
    ├── z-index: 1 — icon, title, tagline, subtitle, buttons
    └── z-index: 2 — hero feature cards
```
