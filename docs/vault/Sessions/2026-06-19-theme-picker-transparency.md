---
aliases:
  - 'Session: Theme Picker Transparency Fix'
  - Theme Picker Transparency
created: '2026-06-19T00:00:00.000Z'
source: agent
tags:
  - type/session-log
  - domain/ui
title: 'Session: Theme Picker Transparency Fix'
type: session-log
updated: '2026-06-19T01:00:00.000Z'
---
# Session: Theme Picker Transparency Fix

**Date**: 2026-06-19
**Branch**: opencode/crisp-island

## Summary

Fixed theme picker menu appearing fully transparent — the `backdrop-filter` glass effect on `.theme-picker__menu` combined with `rgba` background caused the menu background to wash out on some browsers/configurations, leaving only text and buttons visible.

## Change

Replaced `.theme-picker__menu` background from `var(--glass-bg)` (rgba with `backdrop-filter`) to `var(--surface)` (solid opaque). This matches the nav-bar's fallback pattern used in `prefers-reduced-transparency` but applies it unconditionally for the dropdown menu, which is too small a surface to benefit from the glass aesthetic enough to justify the transparency bug.

## Files Changed

- `anvil/api/static/css/base.css` — `.theme-picker__menu`: `background: var(--glass-bg); backdrop-filter: var(--glass-blur)` → `background: var(--surface)`

## Follow-up

Re-reported afterward; see [[Sessions/2026-06-19-theme-picker-transparency-recheck]]. Root cause was transparent `.theme-picker__item` backgrounds (not the container) combined with flex `gap` — documented as [[Discoveries/transparent-items-gap-trick]].
