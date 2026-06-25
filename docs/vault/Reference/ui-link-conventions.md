---
title: UI Link and Button Conventions
type: reference
tags:
  - type/reference
  - domain/ui
created: '2026-06-14'
updated: '2026-06-14'
---
# UI Link & Button Conventions

**Established**: 2026-06-14  
**Context**: Audit and fix of bare text links across the app

## Rule

No bare `<a>` tags or `action-link` styled text for standalone navigation prompts. Standalone navigational elements must use button-styled elements:

| Context | Class | Example |
|---------|-------|---------|
| Primary action in action-buttons bar | `action-btn` | "view all experiments" (training.html) |
| Secondary/external link | `btn btn-secondary` | "mlflow →" external link (training.html) |
| Compact button in metric/value area | `btn btn-secondary btn-sm` | "open in MLflow" (experiment.html detail) |
| Link in card footer area | `btn btn-secondary btn-sm` | "Open in MLflow", "View Experiment" (playground.html) |

## Allowed `action-link` usage

Inline text links within prose sentences and table cells are fine — e.g. "No models registered yet — [register one from a finished experiment]". These are semantically correct as text links.

## Files audited

- `training.html` — fixed 2 bare links
- `experiment.html` — fixed 1 bare link
- `playground.html` — already correct (used `btn btn-secondary btn-sm`)

## See Also

- [[Reference/ArchitectureOverview|Architecture Overview]]
