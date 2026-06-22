---
aliases:
  - Models-Page Single-Click Play Navigation
code-refs:
  - anvil/api/templates/archetypes/models.html
  - anvil/api/templates/archetypes/playground.html
  - anvil/api/templates/archetypes/model_detail.html
created: '2026-06-19'
related: []
session: opencode/sunny-meadow
source: agent
status: draft
summary: >-
  Changed model name link from detail page to play page for single-click
  inference access; added Play button to model detail page
tags:
  - type/discovery
  - domain/ui
  - status/draft
title: Models-Page Single-Click Play Navigation
type: discovery
updated: '2026-06-20'
---
# Models-Page Single-Click Play Navigation

**Type**: discovery-note
**Tags**: ui, navigation, models, play
**Date**: 2026-06-19

## Problem

The Models page listed each registered model with its name linking to a detail page (`/v1/model-detail/{id}`) and a separate "Play" button linking to the inference playground (`/v1/inference-page?model_id={id}`). Users had to click the "Play" button specifically — a two-target interaction that made the primary action (loading a model to play with it) less discoverable.

## Solution

Changed the model name link in the models table to point directly to the inference playground with the model pre-selected via query param: `/v1/inference-page?model_id={id}`. This makes a single click on the model name the fastest path to playing with it.

## Key detail

The playground already supports URL-based pre-selection (`model_id` query param). When the page loads, `playground.html` reads `core.getUrlParams()` and auto-selects the matching model in the dropdown, triggering version selection and model info card rendering. No backend changes were needed.

The "View" (detail page) and "Play" buttons remain as secondary actions for users who need inspection or an explicit call to action.

## Extension: Model Detail Page Play Button

The same pattern was applied to the model detail page (`model_detail.html`). The page previously had no Play button at all — after inspecting a model's architecture and version history, users had to navigate back to the models table to reach the playground. Added a `btn-primary "Play"` link below the model name/description that links to `/v1/inference-page?model_id={id}`, giving a direct path from detail inspection to interaction.

## References

- `anvil/api/templates/archetypes/models.html:67` — model name link target changed
- `anvil/api/templates/archetypes/playground.html:113-125` — URL param pre-selection logic
- `anvil/api/templates/archetypes/model_detail.html:63` — Play button added below model header
