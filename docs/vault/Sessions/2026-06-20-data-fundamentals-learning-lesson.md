---
title: 'Session: Data Fundamentals Learning Lesson & Cross-Reference Banner Pattern'
type: session-log
tags:
  - type/session-log
  - domain/ui
  - domain/content
source: agent
created: '2026-06-20T00:00:00.000Z'
updated: '2026-06-20T00:00:00.000Z'
aliases:
  - 'Session: Data Fundamentals'
  - Learning Lesson Banner CTAs
---
# Session: Data Fundamentals Learning Lesson & Cross-Reference Banner Pattern

**Date**: 2026-06-20
**Status**: Completed

## Summary

Moved the "Understanding Datasets & Corpora" content from an inline collapsible section on `datasets.html` into a proper learning lesson (`/v1/learn/data-fundamentals`), placed as Lesson 1 in the learning arc. Then established a reusable `.section-card--banner` pattern for CTA cross-references between operational pages and learning content, and deployed banners across 6 pages.

## Changes

### Data Fundamentals Learning Lesson

- **`anvil/api/templates/archetypes/data-fundamentals.html`** (new) — Custom lesson template extending `base.html` with:
  - The full 2-column visual pipeline diagram (dataset path + corpus path → training engine) as a hero graphic
  - Quick-reference mini-help grid (Use Datasets when / Use Corpora when / Combine both / Pro tip)
  - Carousel with 5 text-only steps (no interactive widgets)
  - Arc navigation (prev/next through full learning arc) and keyboard/touch support
- **`anvil/api/v1/learning.py`** — Added `DATA_FUNDAMENTALS_STEPS` constant (5 steps), inserted `data-fundamentals` as the first entry in both `LEARNING_ARC` and `LEARNING_ARC_LESSONS`, added route `GET /learn/data-fundamentals`
- **`anvil/api/templates/datasets.html`** — Replaced the old 82-line collapsible section with a compact CTA banner linking to the new lesson

### Reusable `.section-card--banner` Pattern

- **`anvil/api/static/css/archetypes.css`** — Added `.section-card--banner`: `background: linear-gradient(135deg, color-mix(in srgb, var(--accent) 6%, var(--surface)), var(--surface) 70%)`, `box-shadow: none`, `padding: var(--space-3) var(--space-4)`
- Applied across 6 pages via the same compact pattern (icon + "Title" + one-line description + `btn-secondary btn-sm` → learning lesson):

| Page | Banner | Links to |
|------|--------|----------|
| Datasets | Understanding Datasets & Corpora | `/v1/learn/data-fundamentals` |
| Training | How Training Works | `/v1/learn/training-loop` |
| Playground | How Sampling Works | `/v1/learn/sampling` |
| Models | How Model Export Works | `/v1/learn/export` |
| Experiments | How Loss Curves Work | `/v1/learn/loss` |
| Operations | Training in the Cloud | `/v1/learn/cloud-compute` |

### Stagger Sequencing

Banners use `--stagger-i: 0` and existing section-cards below them are incremented by 1 to maintain animation cadence.

## References

- `anvil/api/static/css/archetypes.css` — `.section-card--banner` class
- `anvil/api/templates/archetypes/data-fundamentals.html` — new lesson template
- `anvil/api/v1/learning.py` — `DATA_FUNDAMENTALS_STEPS`, updated arcs, route
- `anvil/api/templates/datasets.html`, `training.html`, `playground.html`, `models.html`, `experiment.html`, `operations.html` — banner additions

## Related

- [[Design/Design|Design]] — UI design system including banner component pattern
- [[Reference/ProgressiveWalkthroughs|Progressive Walkthroughs]] — learning arc progression context
- [[Specs/007 Learning Content Enrichment/007 Learning Content Enrichment|007 Learning Content Enrichment]] — learning content feature specification
