---
title: Graph Scrubber Ignored by Draw
type: discovery
status: draft
source: agent
related: []
code-refs:
  - anvil/api/static/js/graph-view.js
  - anvil/api/templates/archetypes/graph.html
session: 2026-06-20-graph-scrubber-fix
created: '2026-06-20'
updated: '2026-06-20'
summary: >-
  GraphView.draw() ignored _currentStep — scrubber slider did not visually
  filter nodes/edges
tags:
  - type/discovery
  - domain/ui
  - status/draft
aliases:
  - Graph Scrubber Ignored by Draw
---
The `/v1/learn/graph` page's scrubber slider did not visually update the computation graph — the `GraphView.draw()` method in `graph-view.js` stored the step value via `setStep()` but never consulted `_currentStep` when rendering nodes and edges. All 8 nodes rendered at full opacity regardless of scrubber position; only the description text updated.

The fix filters `this._nodes` to only include nodes where `n.step <= this._currentStep` (defaulting to `Infinity` when no step is set so `setGraph()` still renders fully), builds a set of visible node IDs, and filters edges to only those where both endpoints are visible. The scrubber event listener in `graph.html` calls `view.setStep(step)` which triggers `draw()` with the filtered set.

Both `visibleNodes` and `visibleEdges` are used for layout and rendering instead of `this._nodes` and `this._edges`.

## References
- [[Discoveries/Discoveries|Discoveries]]

- `anvil/api/static/js/graph-view.js`
- `anvil/api/templates/archetypes/graph.html`
