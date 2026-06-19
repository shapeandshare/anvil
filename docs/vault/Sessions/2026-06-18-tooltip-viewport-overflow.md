---
created: '2026-06-18'
tags:
  - type/session-log
  - domain/ui
title: Tooltip Viewport Overflow Fix
type: session
updated: '2026-06-18'
aliases:
  - Tooltip Viewport Overflow Fix
source: agent
---
# Session: Tooltip Viewport Overflow Fix

**Date**: 2026-06-18

## Summary

Fixed tooltip popups (triggered by ⓘ icons on the training configuration page) being cut off by the screen edge. The CSS-only `.tooltip-trigger` system centered content via `left: 50%; transform: translateX(-50%)`, but had no viewport-edge detection — tooltips near the right edge overflowed past the viewport.

## What Was Done

### CSS (`components.css`)
- Added `margin-left: var(--tooltip-shift, 0px)` to `.tooltip-content` — allows JS to nudge the tooltip horizontally without interfering with the `transform`-based center+animation
- Changed `.tooltip-content::after` to `left: calc(50% + var(--tooltip-arrow-x, 0px))` — counter-shifts the caret to stay aligned with the trigger when the tooltip shifts

### JS (`core.js`)
- Added `initTooltips()` function:
  - On `mouseenter`: uses `requestAnimationFrame` to measure `getBoundingClientRect()` after the CSS `:hover` applies `display: block`, detects right/left overflow, and sets `--tooltip-shift` / `--tooltip-arrow-x` to nudge the tooltip into view (+12px padding)
  - On `mouseleave`: clears both custom properties, restoring the default centered position
- Called in `DOMContentLoaded` handler
- Called in `loadContent()` after SPA content swaps — ensures tooltips on dynamically-loaded pages get listeners
- Exported as `window.core.initTooltips`

## Key Decisions

| Decision | Rationale |
|----------|-----------|
| CSS variables for shift (`margin-left`) rather than inline styles | Avoids specificity wars and keeps the animation keyframe (`transform`-based) untouched |
| `requestAnimationFrame` timing | Ensures layout is complete after `:hover` applies `display: block` before measuring; correction paint is deferred to the same frame — no visual flash |
| +12px padding from viewport edge | Matches common OS tooltip margin conventions |
| Edge detection for both left AND right overflow | Symmetric fix — though the ⓘ triggers are left-aligned in the config grid, the pattern is reusable |

## Files Changed

- `anvil/api/static/css/components.css` — 2 lines added/modified
- `anvil/api/static/js/core.js` — `initTooltips()` function, 2 call sites, window.core export

## Vault Enrichments

- Created [[Discoveries/css-tooltip-viewport-overflow|CSS Tooltip Viewport Overflow]] — discovery note documenting the pattern and fix

## See Also

- [[Discoveries/css-tooltip-viewport-overflow]] — Full discovery note
- [[Reference/overflow-clipping-pattern]] — Related UI overflow pattern (parent `overflow: hidden` clipping)
