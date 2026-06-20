---
title: Router Decomposition Pattern
type: discovery
status: reviewed
source: agent
related: []
code-refs:
  - anvil/api/v1/router.py
  - anvil/api/v1/health_ops.py
  - anvil/api/v1/pages.py
  - anvil/api/v1/learning.py
session: 2026-06-19-dx-harness-hardening
created: '2026-06-19'
updated: '2026-06-19'
summary: >-
  Router decomposition pattern: router.py went from 1958→45 lines by extracting
  health_ops, pages, and learning modules. Sub-routers cannot have empty path
  prefixes.
tags:
  - type/discovery
  - domain/architecture
  - status/reviewed
---
# Router Decomposition Pattern

During the DX hardening feature, `anvil/api/v1/router.py` was decomposed from a 1958-line monolith into a 45-line thin aggregator plus three extracted modules:

| Module | Lines | Contents | 
|--------|-------|----------|
| `router.py` | 45 | Thin aggregator with 12 `include_router` calls + root page routes |
| `health_ops.py` | 319 | Health check + service management endpoints (stop/start/restart/kill-port) |
| `pages.py` | 177 | HTML page rendering routes (training, experiments, datasets, operations, inference) |
| `learning.py` | 1423 | Learning arc data structure (15 steps), learning content pages, sampling endpoints |

## Key Constraint

Sub-routers cannot define routes with an empty path (`@router.get("")`) because FastAPI raises `FastAPIError: Prefix and path cannot be both empty` when the sub-router is included via `include_router`. Root-level routes (`GET /`) must remain in the top-level aggregator router.

## Pre-existing Inline Content Structure

The original router.py had three inline sections interspersed with the `include_router` aggregate block:
- Lines ~53–409: health + service management
- Lines ~411–551: HTML page rendering 
- Lines ~553–1958: LEARNING_ARC data structure, learning content pages, inference/sampling routes

## References

- `anvil/api/v1/router.py`
- `anvil/api/v1/health_ops.py`
- `anvil/api/v1/pages.py`
- `anvil/api/v1/learning.py`
