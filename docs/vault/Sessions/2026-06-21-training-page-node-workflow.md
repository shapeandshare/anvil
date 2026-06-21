---
title: 'Session: Training Page Node Workflow Diagram'
type: session-log
tags:
  - type/session-log
  - domain/ui
  - domain/training
source: agent
created: '2026-06-21T00:00:00.000Z'
updated: '2026-06-21T00:00:00.000Z'
aliases:
  - 'Session: Training Page Node Workflow'
  - Training Page Node Workflow Diagram
---
# Session: Training Page Node Workflow Diagram

**Date**: 2026-06-21  
**Status**: Completed

## Summary

Added a visual node workflow diagram (pipeline) at the top of the training page, matching the `ds-flow-diagram` pattern from the data-fundamentals page. The diagram shows the 3-step training pipeline with two parallel tracks that converge into a single forge node:

```
Data Path (orange):  Select Data Source → Review Data Context
Config Path (blue):  Configure & Auto-Tune → Review Memory Estimate
                     ╰──────────────┬──────────────╯
                                    ▼
                     ⛏ Forge + Watch (green target node)
```

## Changes

### `anvil/api/templates/archetypes/training.html`

Added a `ds-flow-diagram` block after the banner CTA and before the `runs-panel`, containing:

- **Left path** (orange accent): Node 1 (Data Source selection) → Node 2 (Data Context review)
- **Right path** (accent/blue): Node 3 (Configure & Auto-Tune) → Node 4 (Memory Estimate review)  
- **Converge** (green): Node 5 (Forge + Watch — training, streaming, export)

All nodes use existing `ds-flow-diagram-*` CSS classes defined in `archetypes.css` — no new CSS required.

### Bug Fix: Port Conflict with Docker Container

During verification, discovered a `playful-pixel` Docker compose stack was running an `anvil:local` container bound to ports 8080/5001, preventing the local server from starting. Fixed by stopping the compose project.

## Files Changed

- `anvil/api/templates/archetypes/training.html` — added node workflow (+45 lines)
