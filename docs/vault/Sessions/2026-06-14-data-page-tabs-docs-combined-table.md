---
title: Data Page Restructure — Tabs, Docs, Combined Table
type: session-log
tags:
  - type/session-log
  - domain/ui
created: '2026-06-14'
updated: '2026-06-14'
aliases:
  - 2026-06-14-data-page-tabs-docs-combined-table
source: agent
---
# 2026-06-14: Data Page Restructure — Tabs, Docs, Combined Table

**date**: 2026-06-14
**session**: Data page UI overhaul
**agents**: Sisyphus (orchestrator), Sisyphus-Junior/visual-engineering (implementation)

## Summary

Rewrote `anvil/api/templates/datasets.html` (930 → 1353 lines) to replace the previous two-section layout (Dataset Manager + Corpora Wizard) with a three-section information architecture:

### Section Card #1: Documentation (collapsible)
- Click-to-collapse `Understanding Datasets & Corpora` card using `section-card__header--clickable` + `section-card__content-collapsible` classes
- Four `help-box` entries: What are Datasets, What are Corpora, When to Use Which, Best Practices
- Pros/cons for each type, guidance on combining corpora imports into datasets

### Section Card #2: Data Manager (3 tabs)
- Single card using existing `wizard-tabs` / `wizard-tab` / `wizard-panel` CSS from `archetypes.css`
- **Datasets tab**: upload form + create dataset form + per-tab dataset list with search (all original DOM IDs preserved)
- **Corpora tab**: full wizard (path analysis, recommendations, create & ingest) + per-tab corpus list (all `wiz-*` IDs preserved)
- **Imports tab**: new form with corpus select + dataset select + import button, POSTs to `/v1/datasets/{id}/import-corpus`

### Section Card #3: All Data (combined table)
- Fetches `/v1/datasets` and `/v1/corpora` in parallel via `Promise.all`
- Merges, sorts by `created_at` descending
- Columns: Type (orange `ds-badge-dataset` / blue `ds-badge-corpus` badge), Name, Description/Path, Size, Status/Strategy, Created, Actions
- Action buttons match type (dataset: edit/curate/rm; corpus: ingest/rm)
- Event delegation via `e.target.closest()` ensures clicks from combined table trigger same handlers as per-tab lists

## Key Details

- All 33 original DOM IDs preserved (upload-form, file-input, wiz-root, wiz-analyze-btn, etc.)
- All original JS functions preserved verbatim (loadDatasets, loadCorpora, renderWizResults, updateWizParams, etc.)
- New JS: `switchTab(tabId)`, `loadCombinedData()`, `populateImportSelects()`, import button handler, docs toggle
- Import endpoint fixed from nonexistent `/import-from-corpus` to `/import-corpus`
- Tab switching uses `data-tab` attribute + `wizard-tab--active` / `wizard-panel--active` class toggle
- Design tokens used throughout (`--surface`, `--accent`, `--text-*`, `--space-*`, `--separator`, `--radius`)

## Files Changed

| File | Change |
|------|--------|
| `anvil/api/templates/datasets.html` | Full restructure (930 → 1353 lines) |

## Discoveries

- The `wizard-tabs` CSS pattern in `archetypes.css` is generic enough to reuse for any tabbed UI — uses `data-tab` attribute for click routing
- The import-corpus endpoint at `POST /v1/datasets/{id}/import-corpus` accepts `{"corpus_id": int}` and returns `{"data": {"import_source_id", "rows_imported", "errors"}}`
- Combined table pattern (parallel fetch + merge + sort) is reusable for any entity list where you want unified visibility

## See Also

- [[Glossary]] — add Dataset / Corpus definitions
- [[Reference/TrainingDataFlow]] — data sourcing pipeline