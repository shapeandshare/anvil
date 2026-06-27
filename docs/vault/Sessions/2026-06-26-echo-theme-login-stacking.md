---
created: '2026-06-26'
aliases:
  - Echo Theme Login Stacking
  - Echo Login Stacking Session
related:
  - Discoveries/echo-theme-login-page-stacking-and-visual-enhancement
  - Reference/theme-creation-guide
source: agent
tags:
  - type/session-log
  - domain/ui
title: Echo Theme — Login Page Stacking & Visual Enhancement
type: session-log
updated: '2026-06-26'
aliases:
  - Echo Theme — Login Page Stacking & Visual Enhancement
---
# Session: Echo Theme — Login Page Stacking & Visual Enhancement

**Date**: 2026-06-26
**Status**: Draft

## Summary

Fixed the echo theme's pulsing ring (`::after` pseudo-element at `z-index: 41`) rendering on top of the login card. Rather than hiding it entirely (like grid/hyperspace), lowered it to `z-index: 0` so it sits behind the card, and thickened the ring with a diffuse box-shadow glow for visual presence on the login page where no training metrics drive the `--ping` variable.

## Changes

### `anvil/api/static/css/login.css` — Echo login page override
- Added `[data-skin="echo"] .app-main:has(.login-page)::after` rule block
- `z-index: 0` — renders behind `.login-page` card at `z-index: 2`
- `border-width: 6px` — thicker ring
- `box-shadow: 0 0 70px 30px rgba(74, 200, 230, 0.15)` — diffuse cyan glow

## Stacking Architecture

| Layer | Login page (before) | Login page (after) |
|-------|-------------------|--------------------|
| z-index 41 | Echo ring (overlaps card) | — |
| z-index 2 | `.login-page` | `.login-page` |
| z-index 0 | — | Echo ring (behind card) |

## Key Discovery

### Echo ring visibility at rest

On the login page, no training session is active, so `bus.on('metrics')` never fires. The `--ping` variable stays at `0`, making the ring very faint by default (2px border at 0.05 alpha, 0.2 opacity). The login-page override compensates with a thicker border and a box-shadow glow so the ring is visually present even without metric data driving it.

### Per-theme login page treatment differs

- **Grid / Hyperspace**: effects hidden entirely (`display: none`) — their fixed-position pseudo-elements at `z-index: 0` still paint above the card in the stacking context
- **Echo**: `z-index` lowered to render behind the card, with enhanced styling for visibility
- **Unicorn**: class-based gating with `html.page-login` to avoid `:has()` persistence issues during client-side nav

Each theme's login page treatment depends on whether its effect benefits from being visible as a backdrop, or would just be visual noise.

## Files Modified

```
Modified:
  anvil/api/static/css/login.css    — Echo ring z-index + thickness + glow on login
```

## Wikilinks

- [[Discoveries/echo-theme-login-page-stacking-and-visual-enhancement]]
- [[Reference/theme-creation-guide]]
