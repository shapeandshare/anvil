---
title: Data Page — Fake Tabs Pattern Was Multiple Always-Visible Sections
type: discovery
tags:
  - type/discovery
  - domain/ui
status: reviewed
source: agent
created: '2026-07-04'
updated: '2026-07-04'
aliases:
  - data-page-fake-tabs
code-refs:
  - anvil/api/static/css/archetypes.css:1193-1228
  - anvil/api/templates/datasets.html (pre-restructure)
  - anvil/api/templates/training.html (correct reference)
---

# Data Page — "Fake Tabs" Pattern Made 1,850-Line Page Feel Overwhelming

## What

The `datasets.html` (1,850 lines) used `wizard-tabs` + `wizard-panel` elements from `archetypes.css`, but the JS `switchTab()` only scrolled the target panel into view — all 4 panels remained **always visible** simultaneously. Combined with the wizard-steps progress legend (decorative only, also scroll-nav), this created the illusion of navigation without any actual content isolation.

## Code

- **CSS infrastructure**: `archetypes.css` lines 1193–1226 (`.wizard-tabs`/`.wizard-tab`) and lines 1228+ (`.wizard-panel`) — supports true show/hide with `.wizard-panel--active` class.
- **JS that only scrolled**: `datasets.html` line 1404 (old) — `element.scrollIntoView({ behavior: 'smooth' })`. Never toggled `display: none`.
- **Training page uses it correctly**: `training.html` uses the same CSS classes but with proper tab-panel show/hide and a separate `wizard-steps` for true sequential navigation.

## Why It Matters

The fake tabs contributed three specific UX problems:
1. **Cognitive overload**: All sections visible at once meant the user saw ~8 forms + 3 tables + 4 heading blocks on load.
2. **Wizard was misleading**: The 4-step progress indicator implied a guided flow, but no step depended on any other — they were independent sections.
3. **Redundant tables**: The "All Data" tab duplicated the dataset table (tab 1) and corpus table (tab 2), plus a third combined view. Three tables showing overlapping data.

## Fix

Replaced with a data-first hub: one unified combined table (the most useful view) with search + type filters, plus action links to dedicated flow pages for the setup workflows (upload/create dataset, corpus scan/combine). See [[Sessions/2026-07-04-data-page-hub-restructure]].

## Related

- [[Discoveries/tab-switched-wizard-to-section-cards]] — A different pattern (tab-switched wizard → always-visible section cards). This discovery is the inverse: always-visible tab panels → hidden flow pages.
- [[Decisions/ADR-001-architecture-decisions]]