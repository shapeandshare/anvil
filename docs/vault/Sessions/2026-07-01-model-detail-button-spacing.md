---
title: Model Detail Button Spacing Fix
type: session-log
tags:
  - type/session-log
  - domain/ui
created: '2026-07-01'
updated: '2026-07-01'
status: draft
source: agent
aliases: Model Detail Button Spacing Fix
---

# Model Detail Button Spacing Fix

**Session**: Fixed vertical spacing bugs on the Model Detail page — Play/Continue Training buttons intersecting the "Versions" metric label, and Delete Entire Model button crowding the LoRA Adapters heading below it.

## What was done

### Play / Continue Training buttons (`model_detail.html` + `archetypes.css`)

- Wrapped the two action buttons in a `.model-header__actions` flex container with `gap: var(--space-2)` for consistent spacing between them
- Removed inline `margin-top: var(--space-2)` from each button (previously applied individually but ineffective since `inline-flex` side-by-side layout meant the margin was shared)
- Added `.model-header { margin-bottom: var(--space-4) }` to archetypes.css to create visual separation from the `.metrics-grid` ("Versions", "Created") below

### Delete Entire Model button (`model_detail.html`)

- Changed inline style from `margin-top: var(--space-4)` to `margin: var(--space-4) 0` — the top-only margin meant zero bottom spacing when the LoRA Adapters merge section was visible below it

### Files modified (2 files)

| File | Change |
|------|--------|
| `anvil/api/templates/archetypes/model_detail.html` | Button wrapper + margin fix |
| `anvil/api/static/css/archetypes.css` | Added `.model-header` / `.model-header__actions` styles |

## Key decisions

- **`.model-header__actions` flex container** over individual `margin-top` — cleaner, more predictable spacing between paired action buttons
- **`var(--space-4)` (16px)** — matches the existing vertical rhythm established by other section separators on the page (e.g., versions table, delete section)
- Used the existing `archetypes.css` file rather than inline styles or a new CSS file — consistent with the archetype-level layout patterns in the codebase
