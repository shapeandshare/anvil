---
title: "Session: One-Click Play — Model Registry to Inference"
type: session-log
tags:
  - type/session-log
  - domain/ui
  - domain/inference
  - domain/registry
created: "2026-06-19"
updated: "2026-06-19"
aliases:
  - "Session: One-Click Play — Model Registry to Inference"
  - model-play-button
source: agent
status: draft
---
# Session: One-Click Play — Model Registry to Inference

**Date**: 2026-06-19
**Trigger**: User requested an easy way to click a model in the models view and have it ready in the play window — a button or CTA.

## What was done

### 1. Explored frontend architecture

- Ran two parallel explore agents to map the SPA routing system (core.js), Jinja2 templates (models.html, playground.html), model data flow between `/v1/registry/models` and `/v1/inference/models`, and the design system (CSS tokens/components).
- Identified the existing URL param pattern (`?run_id=X` on experiments page) as the right approach.
- Mapped the model key convention: `modelKey(m) = m.id != null ? String(m.id) : m.name`.

### 2. Implemented Play button + URL param pre-selection

Two atomic changes:

| File | Change |
|------|--------|
| `anvil/api/templates/archetypes/models.html` | Added a primary "Play" button (`btn btn-primary btn-sm`) in the Actions column alongside the existing "View" button. Links to `/v1/inference-page?model_id=<id>`. |
| `anvil/api/templates/archetypes/playground.html` | Added URL param pre-selection in `loadModels()` success handler. After populating the model select dropdown, checks `core.getUrlParams().get('model_id')` and auto-selects the matching model, triggering all update handlers (version select, model info, model info card). |

### 3. Verified

- File diffs confirmed correct — Play button renders alongside View button; pre-selection logic iterates `modelSelect.options` to find matching key.
- Unused `matched` variable cleaned up from the pre-selection loop.
- Both changes committed in `a89b807` alongside governance integration work.

## Discoveries

- The SPA router (`core.js`) already supports URL params via `getUrlParams()`/`setUrlParams()` — used by the experiments page (`?run_id=`) but not by the playground. The pattern was trivially extensible.
- The playground's `modelKey()` function uses `String(m.id)` when available, which is compatible with numeric `model_id` URL params (they arrive as strings, matching the select option values).
- The inference models endpoint (`/v1/inference/models`) and registry models endpoint (`/v1/registry/models`) both expose `m.id`, so the same key works for linking and pre-selection.

## Architecture decisions

- **No ADR warranted** — this is a straightforward UI ergonomics enhancement following existing URL param patterns. No architectural impact.
- **Chose URL params over sessionStorage** — URL params are shareable (bookmarkable), work with browser back/forward, and match the existing `?run_id=` pattern. Session storage would be invisible and not shareable.

## Related

- [[Design/Design|Design]] — UI design system including model registry and inference page patterns
- [[Reference/MlflowIntegration|MLflow Tracking]] — model registry integration context
- [[Reference/ArchitectureOverview|Architecture]] — SPA routing and page linking context