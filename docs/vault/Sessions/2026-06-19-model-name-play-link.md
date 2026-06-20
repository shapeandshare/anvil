---
aliases:
  - 'Session: Model Name Links Directly to Play Page'
created: '2026-06-19'
source: agent
status: draft
tags:
  - type/session-log
  - domain/ui
  - domain/inference
title: 'Session: Model Name Links Directly to Play Page'
type: session-log
updated: '2026-06-19'
---
# Session: Model Name Links Directly to Play Page

**Date**: 2026-06-19
**Trigger**: User requested that a single click on a model in the models page should load it in the play page.

## What was done

Changed the model name link in `models.html` from `/v1/model-detail/{id}` to `/v1/inference-page?model_id={id}`. This means:

- Clicking a model name now navigates directly to the Play page with that model pre-selected
- The "View" button (detail page) and "Play" button remain as secondary actions
- No backend changes needed — the playground's existing URL param pre-selection logic (`playground.html:113-125`) handles the `model_id` query param

## Files changed

- `anvil/api/templates/archetypes/models.html:67` — changed name link target

## Discoveries

- The Play page already supports `model_id` URL param pre-selection from a previous session
- The model key convention (`m.id`) is consistent between the registry listing and the inference models endpoint
- No tests exist for the models-page template (it's a JS-rendered table)

## Related vault notes

- [[Discovery/models-page-single-click-play-navigation]]
- [[Sessions/2026-06-19-model-play-button]] — prior session that added the Play button and URL param support
