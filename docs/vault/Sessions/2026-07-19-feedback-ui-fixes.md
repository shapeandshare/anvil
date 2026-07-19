---
title: Feedback-Driven UI Fixes — Related Lessons Placement and Chip Styling
type: session-log
tags:
  - type/session-log
  - domain/ui
created: '2026-07-19'
updated: '2026-07-19'
status: draft
aliases: Feedback-Driven UI Fixes — Related Lessons Placement and Chip Styling
source: agent
---

# Feedback-Driven UI Fixes — Related Lessons Placement and Chip Styling

**Session**: Addressed two outstanding feedback items from the running main instance (`~/Workbench/Repositories/anvil`): reordering Related Lessons above the dataset table and restyling the `.related-lessons__chip` from muted outlined pills to filled accent buttons.

## What was done

### Item 1 — Reorder Related Lessons
- **PR #406** — Moved `{% include "partials/related-lessons.html" %}` from below the data table section-card to between the filter bar and the data table on `datasets.html`.
- Single template reorder, no CSS changes.

### Item 2 — Button Styling Fix
- **PR #407** — Restyled `.related-lessons__chip` in `archetypes.css` from an **outlined secondary chip** (muted `--text-secondary`, `--surface-2` background, 1px border, 30px pill radius) to a **filled accent button** (`background: var(--accent)`, `color: #fff`, `border: none`, `min-height: 32px`, `font-weight: 500`).
- Added button press animation (`:active { transform: scale(0.97) }`) per DESIGN.md conventions.
- Hover uses `filter: brightness(1.15)` matching `.btn-primary:hover`.
- Applied to all 11 pages that include the related-lessons partial.

## Key observations

- The `.related-lessons__chip` is semantically an `<a>` for navigation (correct per UX rule `[S4]`), but needed visual button weight to match user expectations.
- The broader pattern of muted chip/pill elements (`.tag`, `.example-prompt`, `.sampling-hero-chip`) shares the same `--text-secondary` default + hover-fill pattern and may benefit from similar treatment.

## References
- PR #406: `fix: move Related Lessons above dataset table on datasets page`
- PR #407: `fix: style related-lessons chips as filled accent buttons`
- `anvil/api/templates/datasets.html` — template reorder
- `anvil/api/static/css/archetypes.css` — chip CSS rules (lines 2226–2254)
- `anvil/api/templates/partials/related-lessons.html` — shared partial