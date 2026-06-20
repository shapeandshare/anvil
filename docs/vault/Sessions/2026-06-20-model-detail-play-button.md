---
created: '2026-06-20T00:00:00.000Z'
source: agent
aliases:
  - 'Session: Model Detail Page Play Button'
tags:
  - type/session-log
  - domain/ui
title: 'Session: Model Detail Page Play Button'
type: session-log
updated: '2026-06-20T00:00:00.000Z'
---
# Session: Model Detail Page Play Button

**Date**: 2026-06-20
**Status**: Completed

## Summary

Added a "Play" button to the model detail page (`model_detail.html`) so users can jump directly to the inference playground when inspecting a model, without navigating back to the models table.

## Change

- `anvil/api/templates/archetypes/model_detail.html:63` — added `<a href="/v1/inference-page?model_id={{ model_id }}" class="btn btn-primary btn-sm">Play</a>` in the model header, below the name and description. Uses the same query-param pre-selection pattern as the models table.

## References

- [[Discovery/models-page-single-click-play-navigation]] — updated to include this change
