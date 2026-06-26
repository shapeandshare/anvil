---
created: '2026-06-20T00:00:00.000Z'
source: agent
tags:
  - type/session-log
  - domain/ui
title: 'Session: Page-Intro Visual Container & Training Page Intro Placement'
type: session-log
updated: '2026-06-20T00:00:00.000Z'
aliases:
  - 'Session: Page-Intro Visual Container'
---
# Session: Page-Intro Visual Container & Training Page Intro Placement

**Date**: 2026-06-20
**Status**: Completed

## Summary

Fixed free-floating intro text on the training page by styling `.page-intro` as a visual container (background, padding, border-radius) across the entire app, then moving the training page's intro text inside the **Training Setup** section-card per user preference.

## Changes

### CSS — `.page-intro` Container Styling
- `anvil/api/static/css/components.css` — Added `background: var(--surface)`, `border-radius: var(--radius)`, and `padding: var(--space-4) var(--space-5)` to `.page-intro`
- Reset those properties on `.page-intro--centered` (hero page) to keep the hero's distinct layout unaffected
- Previously `.page-intro` was only font/color/line-height styling — text appeared as bare floating content with no visual container

### Template — `model_detail.html` Restructure
- `anvil/api/templates/archetypes/model_detail.html` — Moved `.page-intro` out of the `.section-card` it was nested inside (the only page doing this)
- Removed the now-redundant inline `style="padding:0 var(--space-4) var(--space-3)"`
- Without this move, the new `.page-intro` background/padding would create a redundant double-container inside the section-card

### Template — Training Page Intro Placement
- `anvil/api/templates/archetypes/training.html` — Removed the standalone `.page-intro` div
- Placed the intro text as a `<p class="section-card__content">` inside the **Training Setup** section-card, immediately after the section header and before the wizard steps
- This puts the descriptive text in context with the controls it introduces

## Design Decisions

- **Shared component vs. page-specific**: Adding container styling to `.page-intro` (used across 11+ pages) was more maintainable than a training-page-only fix, since all other pages also benefit from a visually bounded intro
- **Hero page exemption**: `.page-intro--centered` resets the container styles because the hero/landing page has its own distinct visual language and layout
- **`section-card__content` class**: Used the existing design token for the text inside the Training Setup card, ensuring consistent font/size/color with other card content across the app

## Related

- [[Design/Design|Design]] — UI design system including page-intro and section-card components
- [[Reference/ArchitectureOverview|Architecture]] — template layout and page structure context
