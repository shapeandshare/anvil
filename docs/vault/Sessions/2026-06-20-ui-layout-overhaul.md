---
created: '2026-06-20T00:00:00.000Z'
source: agent
tags:
  - type/session-log
  - domain/ui
  - domain/database
title: 'Session: UI Layout Overhaul — Footer Removal & Nav-Bar Scrolls with Content'
type: session-log
updated: '2026-06-20T00:00:00.000Z'
aliases:
  - 'Session: UI Layout Overhaul'
  - UI Layout Overhaul
---
# Session: UI Layout Overhaul — Footer Removal & Nav-Bar Scrolls with Content

**Date**: 2026-06-20
**Status**: Completed

## Summary

Overhauled the app shell layout: removed the version footer entirely, converted the nav-bar from `position: fixed` to a scrollable panel within the page flow, and fixed a stale-database migration issue uncovered during testing.

## Changes

### Footer Removed
- `anvil/api/templates/base.html` — removed `<footer class="site-footer">` element
- `anvil/api/static/css/base.css` — removed `.site-footer` CSS rule entirely

After multiple iterations (glass overlay, fixed-position blur, mask-image dissolve, gradient fade), the user preferred the cleanest approach: no footer at all. The version info was removed from every page.

### Nav-Bar: Fixed → Scrollable Page Panel
- **File**: `anvil/api/static/css/base.css`
- `.nav-bar` — removed `position: fixed; top/left/right/z-index`. Now a standard flex child
- Styled as a card: `background: var(--surface)`, `border: var(--border-width) solid var(--glass-border)`, `border-radius: var(--radius-lg)`, with margin to sit on the `--bg` background color
- `.app-shell` — changed from `overflow: hidden` to `overflow-y: auto` (now the scroll container)
- `.app-main` — removed `overflow-y: auto` (scroll handled by parent); removed top padding that compensated for fixed nav-bar; removed radial-gradient background (moved to `.app-shell`)
- The entire shell scrolls together now, nav-bar scrolls with content naturally

### DB Migration Fix
- Discovered that `data/anvil-state.db` was stamped at Alembic revision 014 but the actual `license_catalog` and `audit_events` tables didn't exist
- Clearing the stamp and rerunning `upgrade()` failed because the `run_id_seq` table already existed (created by ORM `create_all` at startup, then migration 013 tries to create it)
- Fix: deleted the stale database and ran all migrations from scratch (`upgrade  -> 014`)
- All pages load correctly after the fix

### Cache-Busting
- `anvil/api/templates/base.html` — added `?v={{ version }}` query param to `base.css` stylesheet link to prevent stale cached CSS during development

## References
- `anvil/api/static/css/base.css` — nav-bar, app-shell, app-main rules
- `anvil/api/templates/base.html` — removed footer, cache-busting query param
- `anvil/_resources/migrations/versions/014_add_governance.py` — the migration that was stamped but not executed

---

## Session Addendum: Section-Card Icon Convention (same day)

Applied unique header emblems to every `section-card` across the UI for visual consistency and scannability.

### Changes
- Added `<span class="section-card__icon">` as first child of every `.section-card__header` across 27 cards in 12 template files
- Used distinct symbols per card matching the section content (★ highlights, ⚙ config, 📊 metrics, etc.)
- The about page served as the design model — already had icons on all 5 cards
- No CSS changes needed; `.section-card__icon` was already defined in `archetypes.css`
- Also fixed the about page left-heavy layout by adding `margin-inline: auto` to `.section-card__content`

### Files Modified
- `anvil/api/static/css/archetypes.css` — added `margin-inline: auto` to `.section-card__content`
- 12 template files — added icon spans to all section-card headers

### Discoveries
- `docs/vault/Discoveries/section-card-icon-convention.md`
