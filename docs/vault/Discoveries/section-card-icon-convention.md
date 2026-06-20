---
created: '2026-06-20T00:00:00.000Z'
tags:
  - type/discovery
  - domain/ui
  - status/draft
title: Section-Card Icon Convention
type: discovery
updated: '2026-06-20T00:00:00.000Z'
aliases:
  - Section-Card Icon Convention
source: agent
code-refs:
  - anvil/api/static/css/archetypes.css
  - anvil/api/templates/about.html
---
# Discovery: Section-Card Icon Convention

**Date**: 2026-06-20

Section cards (`section-card`) now have a standardized visual header convention: every `.section-card__header` should include a `<span class="section-card__icon">` as the first child, containing a unique Unicode symbol or emoji that visually identifies the section's content.

## Pattern

```html
<div class="section-card__header">
  <span class="section-card__icon">&#9733;</span>
  <h2 class="section-card__title">Section Title</h2>
  ...
</div>
```

## Symbol Selection Guidelines

- Use simple Unicode dingbat symbols (U+2600–U+27BF range) for a clean, consistent look
- Emoji (U+1F300+) are acceptable for more expressive sections but may render differently by platform
- Each card in a page should have a unique icon — reuse only if the semantic meaning is identical
- Match the icon to the section content (★ for highlights, ⚙ for configuration, 📊 for metrics, etc.)

## Scope

Applied to all 27 section-card headers across 12 template files:
- `about.html` (5 cards — already had icons, served as the model)
- `acceptable_use.html` (1 card — already had icon)
- `dataset_curation.html` (5 cards)
- `datasets.html` (3 cards)
- `learn-index.html` (1 card)
- `models.html` (1 card)
- `model_detail.html` (1 card)
- `playground.html` (3 cards)
- `training.html` (5 cards)
- `experiment.html` (2 cards)
- `graph.html` (2 cards)
- `operations.html` (4 cards)

## Rationale

The about page's use of header emblems made sections feel more distinct and visually anchored. Extending the pattern universally creates visual consistency and improves scannability across all pages. No new CSS was needed — `.section-card__icon` was already defined in `archetypes.css`.
