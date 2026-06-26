---
title: 'Session: Graph Canvas Node Left-Edge Clipping Fix'
type: session-log
tags:
  - type/session-log
  - domain/ui
created: '2026-06-20'
updated: '2026-06-20'
source: agent
aliases:
  - 'Session: Graph Canvas Node Left-Edge Clipping Fix'
---
# Session: Graph Canvas Node Left-Edge Clipping Fix

## Summary

Fixed a UI layout bug where the animated computation graph on `/v1/learn/graph` had its leftmost nodes clipped off the canvas because the x-position calculation placed depth-0 node centers at x=40 (left edge at -10, 10px off-screen).

## What Was Done

- Diagnosed the clipping: `x = depth * 150 + 40` with `nodeW = 100` puts the first column's left edge at x=-10
- Changed base offset from `40` to `60`, giving depth-0 nodes a 10px inset from the canvas left edge
- Verified math at all depth levels fits within the section-card content area
- Wrote discovery note in `docs/vault/Discoveries/graph-canvas-node-left-clipping.md`

## Session Artifacts

- `anvil/api/static/js/graph-view.js` — modified: line 81 `40` → `60`
- `docs/vault/Discoveries/graph-canvas-node-left-clipping.md` — new discovery note

## Related

- [[Discoveries/graph-canvas-node-left-clipping|Graph Canvas Node Left-Edge Clipping]] — discovery note from this session
- [[Discoveries/graph-scrubber-ignored-by-draw|Graph Scrubber Ignored by Draw]] — related graph fix discovery
- [[Design/Design|Design]] — UI design system for canvas renderer layout
