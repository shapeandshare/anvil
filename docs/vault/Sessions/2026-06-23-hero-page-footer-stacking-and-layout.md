---
title: Hero Page Footer Stacking and Layout Fix
type: session-log
tags:
  - type/session-log
  - domain/ui
created: '2026-06-23'
updated: '2026-06-23'
aliases:
  - 2026-06-23-hero-page-footer-stacking-and-layout
source: agent
---
# Hero Page Footer Stacking and Layout Fix

**Type**: session-log  
**Tags**: type/session-log, domain/ui  
**Created**: 2026-06-23  
**Updated**: 2026-06-23  

## Summary

Debugged why the copyright footer appeared "under the content blocks" / "floating on top of content boxes" on the hero page. Root cause was a CSS stacking context conflict between `.app-main { isolation: isolate }` and `.site-footer { position: relative }`.

## What Was Tried

### Attempt 1: Flex layout changes
- Changed `.hero-page` from `min-height: 100%` to `flex: 1`  
- Added `display: flex; flex-direction: column` to `.app-main`  
- **Result**: Footer disappeared from all pages (due to flex container change on `.app-main`)

### Attempt 2: Sticky footer
- Moved `overflow-y: auto` from `.app-shell` to `.app-main`  
- Made `.site-footer` sticky with `position: sticky; bottom: 0`  
- **Result**: Footer "frozen in place" — user didn't want sticky behavior

### Attempt 3: Classic sticky footer (flex push)
- Reverted overflow changes, kept `.site-footer` CSS class  
- Removed `flex: 1` from `.app-main`  
- Added `margin-top: auto` on `.site-footer`  
- **Result**: Footer still reported as "under the content blocks" because when content fills the viewport, there's no free space for `margin-top: auto` to push it to the bottom

### Attempt 4: Stacking context fix
- Removed `isolation: isolate` from `.app-main`  
- Removed `position: relative` from `.site-footer`  
- Added `background: var(--bg)` to `.site-footer` for opaque backdrop  
- **Result**: Footer no longer paints on top of content due to stacking order

## Root Cause

`.app-main { isolation: isolate }` creates a new CSS stacking context. In the parent stacking context's paint order (Step 6), "positioned descendants with z-index: auto" and "child stacking contexts" are painted in DOM order. `.site-footer { position: relative }` is a positioned descendant, so it lands in Step 6 of the parent context. `.app-main` (with `isolation: isolate`) is a child stacking context, also Step 6. Since `.app-main` precedes `.site-footer` in the DOM, `.app-main`'s stacking context is painted first, then `.site-footer` is painted ON TOP — causing the footer to overlay `.app-main`'s overflow content.

**Fix:** Remove `isolation: isolate` (the stacking context separation wasn't needed for theme pseudo-elements since they use `position: fixed`) and remove `position: relative` from the footer so it remains a non-positioned block in Step 3, painted before `.app-main`'s content.

## Files Changed
- `anvil/api/static/css/base.css` — Removed `isolation: isolate` and `min-height: 0` from `.app-main`; replaced `position: relative` with `background: var(--bg)` on `.site-footer`  
- `anvil/api/templates/base.html` — Updated inline styles to match

## Tags
- `domain/ui` — CSS stacking, layout, footer