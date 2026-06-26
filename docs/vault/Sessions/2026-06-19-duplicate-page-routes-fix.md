---
title: 'Session: Duplicate Page Route Cleanup'
type: session-log
tags:
  - type/session-log
  - domain/architecture
aliases:
  - 'Session: Duplicate Page Route Cleanup'
  - route-duplication-cleanup
created: '2026-06-19'
updated: '2026-06-19'
source: agent
status: draft
---
# Session: Fix Duplicate Page Route Definitions

**Date**: 2026-06-19
**Trigger**: User reported that Data and About pages do not load from the menu bar.

## What was done

### 1. Diagnosed duplicate route definitions

Found that `anvil/api/v1/router.py` defined **identical duplicate routes** for all page-rendering routes that already existed in `anvil/api/v1/pages.py` and `anvil/api/v1/learning.py`. When sub-routers were included via `router.include_router()`, Starlette silently allowed duplicates — the first-registered (router.py) handler won for each shadowed path. This caused:

- The `/about` route (unique to `pages.py`) was the only page route not shadowed, creating routing inconsistency
- The router.py `/datasets-page` handler passed `_ACCEPTABLE_LICENSES` (a list of **strings**) but `datasets.html` expected objects with `.identifier`/`.display_name` — Jinja2 silently rendered blank license options
- All `/learn/*` routes, `/models-page`, `/model-detail/{model_id}`, `/inference/models`, and `/inference/sample` were duplicated in both `router.py` and `learning.py`

### 2. Removed all duplicate route definitions from router.py

| Removed from `router.py` | Owner |
|---|---|
| `/training-page`, `/experiments-page`, `/learn/graph`, `/datasets-page`, `/operations-page`, `/inference-page` | `pages.py` |
| All `/learn/*` routes (12 routes) | `learning.py` |
| `/models-page`, `/model-detail/{model_id}`, `/inference/models`, `/inference/sample` | `learning.py` |
| Orphaned data: `LEARNING_ARC` + 15 step arrays + `_arc_context` + `_ACCEPTABLE_LICENSES` (~1100 lines) | `learning.py` |

Also cleaned up unused imports (`random`, `HTTPException`, `Sequence`) and fixed the missing `softmax` import in the `/inference/sample` handler that remained.

### 3. Result

`router.py` went from **1624 → 75 lines**. Each page route is now registered exactly once in its correct sub-router. No route shadowing, no duplicate handlers, no broken template context.

## Architecture decisions

- **Single source of truth for routes**: Each sub-router (`pages.py`, `learning.py`) now exclusively owns its route definitions. `router.py` is a thin aggregator that includes sub-routers and defines only routes that cannot live in sub-routers (`""`/`"/"` root, `/acceptable-use`).
- **No ADR warranted** — cleanup of pre-existing decomposition residue from the DDD services restructure (ADR-022) where page routes were moved to sub-routers but originals left behind.

## Files changed

| File | Change |
|------|--------|
| `anvil/api/v1/router.py` | Removed 11 page route definitions, 14 learn-related route definitions, ~1100 lines of orphaned learning content data, 4 unused route handlers (models-page, model-detail, inference/models, inference/sample), and unused imports |

## References

- `anvil/api/v1/router.py` — cleaned aggregator
- `anvil/api/v1/pages.py` — page route owner (7 routes)
- `anvil/api/v1/learning.py` — learn route owner (19 routes including models)
- `anvil/api/static/js/core.js` — client-side navigation (`loadContent` function)

## Related

- [[Decisions/ADR-022-domain-driven-package-decomposition|ADR-022: Domain-Driven Package Decomposition]] — architecture decision record (routing restructuring context)
- [[Design/Design|Design]] — UI design system for page routes
- [[Reference/ArchitectureOverview|Architecture]] — API routing architecture context
