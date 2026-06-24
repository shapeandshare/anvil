---
aliases:
  - Glass Diffusion for Reduce Effects
created: '2026-06-23T00:00:00.000Z'
source: agent
tags:
  - type/session-log
  - domain/ui
title: 'Session: Glass Diffusion for Reduce Effects'
type: session-log
updated: '2026-06-23T00:00:00.000Z'
---
# Session: Glass Diffusion for Reduce Effects

**Date**: 2026-06-23
**Status**: Completed

## Summary

Changed the "Reduce effects" accessibility mode to blur the particle canvas (filter: blur(12px)) instead of hiding it (opacity: 0), so ambient particles remain visible but motion-diffused. Also mutes the shell background gradient to further reduce visual motion. Replaced an earlier failed approach (DOM overlay with backdrop-filter) that caused z-index conflicts with dropdown menus and compositing issues with the particle canvas.

## Changes

### `anvil/api/static/js/theme/particle-system.js`

- **`onEffectLevelChange()`**: Changed `canvas.style.opacity = '0'` to `canvas.style.filter = 'blur(12px')` when `snap.legible` is true; restored to `canvas.style.filter = ''` when legible is false (clear instead of `opacity = '1'`).
- **`apply()`**: Added `canvas.style.filter = legible ? 'blur(12px)' : ''` after `startAnimation()` so the blur is applied on initial load, not only on toggle.

### `anvil/api/static/js/theme/theme-manager.js`

- Added `updateGlassDiffusion(snap)` — sets/removes `data-glass-diffusion` attribute on `<html>` based on `snap.legible`.
- Registered `updateGlassDiffusion` as an `EffectLevel.onChange` listener in `init()`.
- Calls `updateGlassDiffusion` with the initial snapshot so the attribute is set on page load if the preference is already active.

### `anvil/api/static/css/base.css`

- Added `[data-glass-diffusion] .app-shell` rule that halves the accent-orange mix from 12% to 6% in the background gradient, muting the shell background when reduce effects is active.

## Vault Updates

- Updated `Reference/particle-effect-authoring.md` — changed "zeroing canvas opacity" to "applying a blur filter" and linked to the new discovery note.
- Created `Discoveries/glass-diffusion-via-canvas-blur.md` — documents the canvas-blur approach, why the overlay approach failed, and the z-index/compositing lessons learned.

## Retrospective

The first attempt used a DOM overlay div with `backdrop-filter: blur()`. This caused:

1. z-index competition with the nav-bar (both at z-index 1 within `.app-shell`'s stacking context), requiring `.app-main` to be bumped to z-index 1.
2. Bumping `.app-main` at z:1 created stacking context conflicts with the theme-picker dropdown menu (z:60 within nav-bar, but nav-bar's stacking context rendered at shell's z:1 level behind the now-bumped main content).
3. `backdrop-filter` even on an invisible element created compositing layers that interfered with the fixed-position particle canvas at the same z-index.
4. Using `::after` on `.app-shell` was also ruled out because pseudo-elements paint after all DOM children at the same z-index, blurring everything including content.

The winning approach — filter the canvas directly — is dramatically simpler: two lines of JS, no new DOM elements, no z-index changes.
