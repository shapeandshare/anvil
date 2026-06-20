---
title: Graph Canvas Node Left-Edge Clipping
type: discovery
tags:
  - type/discovery
  - domain/ui
  - status/draft
created: '2026-06-20'
updated: '2026-06-20'
code-refs:
  - anvil/api/static/js/graph-view.js
source: agent
aliases:
  - Graph Canvas Clipping
  - Learn Graph Left Edge Clip
---
# Graph Canvas Node Left-Edge Clipping

## Discovery

The computation graph on `/v1/learn/graph` rendered nodes with their left edge clipped off the canvas when using narrow viewports or when only depth-0 nodes were visible (early scrubber steps). The root cause was insufficient left margin in the x-position calculation:

```js
var x = depth * 150 + 40;  // before
```

With `nodeW = 100`, a depth-0 node is centered at x=40, placing its left edge at `40 - 50 = -10` — 10px off the canvas.

## Fix

Changed the base offset from `40` to `60`:

```js
var x = depth * 150 + 60;  // after
```

This shifts all nodes 20px right. Depth-0 nodes now have left edge at `60 - 50 = 10`, giving 10px of breathing room. Rightmost nodes (depth 3) end at `510 + 50 = 560`, well within typical section-card content widths (~700px+).

## Impact

No more clipped left-edge nodes at any scrubber step. The layout remains comfortably within the section-card bounds at all depth levels.

## Related

- `anvil/api/static/js/graph-view.js` line 81
