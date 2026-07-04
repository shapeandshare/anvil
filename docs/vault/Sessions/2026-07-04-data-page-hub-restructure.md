---
title: 2026-07-04-data-page-hub-restructure
type: session-log
aliases:
  - data-page-hub-restructure
tags:
  - type/session-log
  - domain/ui
status: draft
source: agent
created: '2026-07-04'
updated: '2026-07-04'
---

# Session: Data Page Hub Restructure — From 1,850-line wall to data-first hub + drill-in flows

## Summary

Restructured the overwhelming `datasets.html` page (1,850 lines, 4 always-visible "tabs", 8+ forms, 3 redundant tables) into a **data-first hub** at `/v1/datasets-page` with two focused **drill-in flow pages**:

### Hub (`datasets.html`, 1850→~600 lines)
- Single unified dataset+corpora table with client-side search + type filter (All/Datasets/Corpora)
- Filter state persisted in URL query params (`?q=&type=`)
- Two primary action links: **Add Data** → `/v1/data-add-page`, **Scan Folder** → `/v1/data-sources-page`
- All row actions preserved (edit, curate, fork, delete, ingest, warning badge)
- Proper empty state with links to both flows; confirm guard added for corpus delete (was missing)
- Removed: fake wizard-step legend, scroll-only tab nav, 3 redundant tables, ~1,200 lines dead JS

### Add Data flow (`/v1/data-add-page`, new)
- Upload file form with provenance & governance (declared source, license select from catalog, no-harm affirmation)
- Create empty dataset form
- Back-link to hub

### Data Sources flow (`/v1/data-sources-page`, new)
- Corpus wizard: path scan, glob patterns (include/exclude chips), analysis stats, recommendation cards, corpus creation with strategy/block-size/overlap
- Import corpus as new dataset (with custom chunking)
- Combine & Curate: import corpus into existing dataset
- Back-link to hub

### UX cleanup (S4/S3 violations remediated)
- Glob pattern chips converted from `<span>` to `<button>` with `aria-pressed`
- 7 status elements gained `aria-live="polite"` + `role="status"`
- Submit buttons now disable + spinner during requests (finally-style cleanup)
- Validation errors focus the offending field
- Corpus delete got confirm guard
- Locale-aware date/number formatting, Unicode ellipsis `…`, `tabular-nums` on numeric columns

## Files Changed

| File | Change |
|------|--------|
| `anvil/api/templates/datasets.html` | Rewritten hub (1850→~600 lines) |
| `anvil/api/templates/data_add.html` | **New** — Add Data flow page |
| `anvil/api/templates/data_sources.html` | **New** — Data Sources flow page |
| `anvil/api/v1/pages.py` | +2 routes (`/data-add-page`, `/data-sources-page`); removed `licenses` from hub route; updated docstrings |
| `anvil/api/static/css/components.css` | `.tag` button reset + `aria-pressed` selectors; `.cell-numeric` tabular-nums |
| `tests/e2e/api/test_pages.py` | +2 page tests (red→green TDD); updated hub content marker |
| `tests/browser/test_dataset_upload_wiring.py` | Updated goto URLs to `/v1/data-add-page` |
| `tests/browser/test_navigation_smoke.py` | Added new page URLs |

## Pre-Existing Failures

Two test failures confirmed on clean HEAD (stash-verified): `test_learn_cloud_compute` (content marker mismatch on cloud-compute lesson) and `test_training_page_renders_related_lessons_row` (303 redirect on training-page without DB init). Unrelated to this change.

## Key Architectural Observations

- Fake tabs (`wizard-tabs` + `wizard-panel` — all panels always visible, tabs just scroll-nav) contributed significantly to the overwhelming feel. The existing CSS infrastructure supported true show/hide, but the JS only scrolled.
- The combined All Data table (`loadCombinedData` + `_createCombinedRow`) was already the most useful view — everything else was duplication or set-up scaffolding. Making it the primary view was the right call.
- Pre-existing S4 `ux-lint:allow` suppressions in `components.css` (3 `outline: none` with `:focus-visible` replacements) — acceptable annotations, not new violations.