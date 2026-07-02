---
title: 2026-07-01 training pit-of-success UX fixes
type: session-log
tags:
  - type/session-log
  - domain/ui
  - domain/training
status: draft
source: agent
created: '2026-07-01'
updated: '2026-07-01'
aliases: 2026-07-01-training-pit-of-success
code-refs: anvil/api/templates/archetypes/training.html
---
# Session: Training page pit-of-success UX fixes

## Summary

Fixed the training page's finetuning error UX. When a LoRA/QLoRA training request failed (e.g., "base_model_ref required"), `apiFetch` didn't throw on HTTP 422, the code saved `runId: undefined` to sessionStorage as "connecting", and users saw a stale "Active Training Runs" entry with 0 steps forever.

## Key Decisions

- **Pre-flight validation** runs in `showTrainConfirmModal()` *before* the confirmation modal appears, not after. Catches missing base model before the user confirms.
- **Defense-in-depth**: `startTraining()` also validates, and checks `resp.ok` after `apiFetch` to surface HTTP errors.
- **Stale run cleanup**: `reconnectToRun()` now guards against invalid/undefined run IDs; `_staleRun()` removes orphaned entries from sessionStorage instead of keeping them as "errored".
- **Error display**: Inline error banner in the "Forge" section with `role="alert"`, guidance text, and action links (e.g., "Go to Models"). Replaces the prior pattern of only logging to the output pane.
- **LoRA inline warning**: A visible callout in the Configure tab when LoRA/QLoRA is selected without a base model URL parameter.

## Files Changed

- `anvil/api/templates/archetypes/training.html` — Added error banner HTML, `showTrainingError()`/`dismissError()` functions, `validateConfig()` pre-flight check, `resp.ok` check in `startTraining()`, invalid runId guard in `reconnectToRun()`, auto-dismiss in `_staleRun()`, LoRA base-model inline warning, pre-flight in `showTrainConfirmModal()`.

## Compliance

- **JS syntax**: node --check passes
- **Jinja parse**: env.get_template() passes
- **UX lint gate**: `1 files · S4:0 · GATE: PASS`
- **Prior art**: Follows the existing `degraded-banner` pattern in base.html

## Related

- [[Discoveries/api-fetch-does-not-throw-on-http-errors]]
