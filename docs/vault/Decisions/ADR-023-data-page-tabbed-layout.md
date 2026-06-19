# ADR-008: Data Page Unified Tabbed Layout

## Status

Accepted

## Context

The datasets page (`/v1/datasets-page`) previously had two separate `section-card` components — "Dataset Manager" and "Corpora Wizard" — each managing its own entity type with independent lists. Users had to scroll between sections to see all their data sources, and there was no documentation explaining when to use datasets vs corpora.

The "Import" functionality existed only as a backend API (`POST /v1/datasets/{id}/import-corpus`) with no frontend UI, forcing users to use curl or the API directly.

Three problems needed solving:
1. New users had no guidance on choosing between datasets and corpora
2. Managing data sources required scrolling between two independent card sections
3. The corpus-to-dataset import pipeline had no UI

## Decision

Restructure the datasets page into three stacked `section-card` components:

1. **Documentation card** (collapsible) — explains datasets vs corpora with pros, cons, when-to-use, and best practices. Uses `.section-card__header--clickable` + `.section-card__content-collapsible` pattern for progressive disclosure.

2. **Data Manager card** (tabbed) — single card with `wizard-tabs` navigation:
   - "Datasets" tab: upload form, create dataset form, per-tab dataset list
   - "Corpora" tab: full wizard (path analysis, recommendations, create & ingest), per-tab corpus list
   - "Imports" tab: new corpus-select + dataset-select + import button

3. **All Data card** (combined table) — fetches both APIs in parallel, merges, sorts by `created_at` descending, renders with type badge column

Key constraints:
- All 33 existing DOM IDs preserved for JS compatibility
- All existing JS functions and event handlers preserved verbatim
- Per-tab lists kept alongside combined table so users can work within a context and still see everything at a glance
- Tab switching uses existing `wizard-tab--active` / `wizard-panel--active` CSS classes

## Consequences

**Easier:**
- New users can learn the dataset/corpus distinction immediately via the docs card
- Users see all data sources in one combined table with type badges
- Importing corpus documents into a dataset is now a UI operation, not just an API call
- Tabbed layout reduces vertical scrolling for the management tools
- Progressive disclosure (collapsible docs) keeps default view clean

**Harder:**
- Combined table has 7 columns which may be tight on narrow screens
- Event delegation must work for both per-tab lists and combined table rows simultaneously (same class names required)
- Two levels of list rendering (per-tab + combined) means 3 API fetches on page load (datasets + corpora + combined)
- Future additions to either entity type need updates in both renderers

## Compliance

- All 33 original DOM IDs verified via grep
- All event handlers tested via click delegation on combined table rows
- Import endpoint verified against backend route (`/v1/datasets/{id}/import-corpus`)
- Tab switching tested for correct `wizard-tab--active` / `wizard-panel--active` class toggle