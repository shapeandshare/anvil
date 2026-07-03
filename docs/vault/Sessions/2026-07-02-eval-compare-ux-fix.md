---
title: "Session: Eval-Compare page UX fix — SSE connection bug, models page data source swap"
type: session-log
tags:
  - type/session-log
  - domain/ui
  - domain/inference
  - status/draft
created: '2026-07-02'
updated: '2026-07-02'
aliases:
  - eval-compare-ux-fix
status: draft
source: agent
---

# Session: Eval-Compare Page UX Fix

**Date**: 2026-07-02
**Trigger**: `/v1/eval-compare?model_id=1` page stuck on "Initializing..." — user reported the page never loads.

## Summary

Diagnosed and fixed three issues in the fine-tuned model evaluation workflow:

1. **SSE connection bug** — `eval_compare.html` called `sse.connect()` but the `SSESession` prototype method is `start()`. This threw a silent `TypeError`, the SSE stream never connected, and the page stayed on "Initializing..." forever.

2. **Models page broken Evaluate button** — The Evaluate button on `/v1/models-page` linked to `/v1/eval-compare?model_id=X` with an MLflow registered model ID, but the eval-compare route expects `run_id` (from a prior `POST /v1/eval/fine-tuned`), and the eval system requires ExternalModel IDs (not MLflow IDs). The page was swapped from the MLflow registry API (`/v1/registry/models`) to the ExternalModel API (`/v1/models/external`), and the Evaluate button now POSTs to create an eval run then navigates to the comparison page.

3. **Route handler hardening** — `eval_compare_page` now properly parses `run_id` as an int with try/except, defaulting to `0` on missing/invalid input. The template guards against `run_id=0` with a clear message.

## Files Changed

- `anvil/api/templates/eval_compare.html` — `sse.connect()` → `sse.start()`; added `run_id=0` guard
- `anvil/api/templates/archetypes/models.html` — Swapped data source from `/v1/registry/models` (MLflow) to `/v1/models/external` (ExternalModel); updated table columns; Evaluate button now POSTs to create eval run then navigates
- `anvil/api/v1/learning.py` — Safe int parsing for `run_id` query param

## Key Discoveries

- The models page (`/v1/models-page`) was showing MLflow registered model data, but the Evaluate button needed ExternalModel IDs. The two registries (MLflow vs ExternalModel) serve different purposes — MLflow for training experiment promotions, ExternalModel for HF/local imports. The models page now shows ExternalModel data, which is the correct context for the Evaluate flow.
- The `SSESession` JavaScript class has a `start()` method, not `connect()`. The `_connect()` private method is called internally by `start()`.