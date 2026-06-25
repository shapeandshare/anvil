---
title: 'Session: Favicon SVG Silhouette Sync'
type: session-log
tags:
  - type/session-log
  - domain/ui
created: '2026-06-14'
updated: '2026-06-14'
aliases:
  - 2026-06-14-favicon-svg-sync
source: agent
---
# Session: Favicon SVG Silhouette Sync

**Date**: 2026-06-14
**Feature**: Visual consistency — favicon/inline SVG alignment

## What was done

- **favicon.svg**: Removed the background rect element and its associated CSS rules (.bg class, dark/light bg fills). The favicon now renders as just the anvil silhouette on a transparent background — orange (#ff9500) in dark mode, dark (#1c1c1e) in light mode. The previous bg rect created a solid #1c1c1e/#f2f2f7 background that overlapped with browser chrome/tab styling.

- **Menu bar icon** (base.html:23): Replaced the abstract blocky SVG paths (5 disconnected rect-like shapes) with the same anvil silhouette path used by the favicon. Uses viewBox 0 0 32 32 (matching favicon coordinate space) and fill currentColor to inherit nav text color.

- **Hero forge icon** (hero.html:21-25): Replaced the old landmark-based anvil-emblem path with the favicon silhouette path, scaled via translate(40, 0) scale(5) into the 240x160 viewBox. The path retains its translate(0, -1.5) transform (identical to favicon) for vertical centering within the 32x32 source space.

## Key details

- All three locations now share one identical path string — any future silhouette updates need only change favicon.svg, then copy the same d attribute to base.html:23 and hero.html:21-25.
- The hero icon transform chain: path translate(0, -1.5) → group translate(40, 0) scale(5). Center is at x=120.375 and y=79.25 — both imperceptibly off from true center (0.16% and 0.47%).

## Leftover

- **README.md** still embeds the old anvil-emblem path inline (the M 192,62 C 202,59... path) in its hero banner SVG. Not updated — not part of the app page chrome, and the README is a separate concern.

## Files changed

- anvil/api/static/favicon.svg (transparent bg, removed bg rect)
- anvil/api/templates/base.html (menu bar Anvil tab icon SVG)
- anvil/api/templates/archetypes/hero.html (hero forge icon SVG)