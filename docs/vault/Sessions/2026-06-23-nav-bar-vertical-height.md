---
title: Nav-Bar Vertical Height Fix
type: session-log
tags:
  - type/session-log
  - domain/ui
created: '2026-06-23'
updated: '2026-06-23'
aliases:
  - 2026-06-23-nav-bar-vertical-height
source: agent
---
# Nav-Bar Vertical Height Fix

**Type**: session-log  
**Tags**: type/session-log, domain/ui  
**Created**: 2026-06-23  
**Updated**: 2026-06-23  

## Summary

The top nav-bar had grown too narrow vertically after the app-shell layout rework (removal of `flex: 1` and `min-height: 0` from `.app-main` altered the visual weight balance). Increased vertical padding and min-height, and fixed a vertical scroll leak in the tabs container.

## What Was Tried

### Attempt 1: --space-4 vertical padding, min-height 64px
- Changed `padding: var(--space-3) var(--space-4)` → `padding: var(--space-4) var(--space-4)`
- Changed `min-height: 52px` → `min-height: 64px`
- **Result**: User said "still too narrow"

### Attempt 2: --space-5 vertical padding, min-height 72px
- Changed to `padding: var(--space-5) var(--space-4)`, `min-height: 72px`
- **Result**: User said "still too narrow"

### Attempt 3: --space-6 vertical padding, min-height 88px
- Changed to `padding: var(--space-6) var(--space-4)`, `min-height: 88px`
- **Result**: User said "too far, go shorter"

### Attempt 4: 24px vertical padding, min-height 80px
- Changed to `padding: 24px var(--space-4)`, `min-height: 80px`
- **Result**: User said "still too narrow" after some reconsideration

### Final: 24px vertical padding, min-height 88px
- Kept `padding: 24px var(--space-4)`, bumped `min-height: 88px`
- Added `overflow-y: hidden` to `.nav-bar__tabs` (see discovery below)

## Discovery: overflow-x: auto leaks vertical scroll

When a CSS element sets `overflow-x` to a non-`visible` value (e.g., `auto`), browsers implicitly compute `overflow-y` to `auto` as well — even though only horizontal overflow was intended. This causes a scroll container to form on both axes, and if tab items overflow vertically (e.g., `min-height: 44px` > container content area), a vertical scrollbar appears within the nav-bar tabs.

**Fix:** Explicitly set `overflow-y: hidden` on `.nav-bar__tabs` alongside `overflow-x: auto`.

## Files Changed
- `anvil/api/static/css/base.css` — Nav-bar vertical padding 24px, `min-height: 88px` (mobile: 20px), `overflow-y: hidden` on `.nav-bar__tabs`

## Tags
- `domain/ui` — CSS layout, nav-bar, overflow scroll containment

## Related

- [[Design/Design|Design]] — UI design system including nav-bar component
- [[Discoveries/nav-bar-z-index-positioned-content-stacking|Nav-Bar Z-Index Competition with Page Content]] — related nav-bar discovery
- [[Reference/ArchitectureOverview|Architecture]] — app shell layout context