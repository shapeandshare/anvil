---
title: 'Storm Front Rain Speed — 2026-06-20'
type: session-log
status: draft
source: agent
tags:
  - domain/ui
  - type/session-log
created: '2026-06-20'
updated: '2026-06-20'
aliases:
  - Storm Front Rain Speed
---

# Storm Front Rain Speed — 2026-06-20

**Date**: 2026-06-20
**Context**: User reported that "the rain in Storm Front needs to fall faster." The rain effect in the canvas particle system (registered by `stormfront.js` via `particleConfig: { type: 'rain', params: {} }`) had a base drop speed of 1.5–3.5 px/frame, which felt sluggish even at peak charge.

## What Was Done

- **Doubled rain base speed** in `anvil/api/static/js/theme/particle-system.js`:
  - `createDrop()`: `speedVal` changed from `1.5 + Math.random() * 2` → `3 + Math.random() * 4`
  - `update()` respawn reset: `d.speed` same change to match
- The charge-driven multiplier (`vy = d.speed * (1 + charge * 0.6)`) continues to scale speed upward during training — faster baseline + charge scaling compounds for a noticeably heavier downpour.
- No other rain parameters touched (drop count, length, opacity, wind) — minimal diff, one file changed.

## Relevant Files

- `anvil/api/static/js/theme/particle-system.js` — rain effect `registerEffect('rain', ...)`, lines 418 and 491

## Wikilinks

- [[Sessions/2026-06-20-particle-system-always-on-and-rain-overhaul]]
- [[Reference/theme-creation-guide]]
- [[Decisions/ADR-031-behavioral-theme-engine]]
