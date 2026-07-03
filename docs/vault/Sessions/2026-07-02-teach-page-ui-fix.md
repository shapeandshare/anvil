---
title: 2026-07-02-teach-page-ui-fix
type: session-log
aliases:
  - teach-page-ui-fix
tags:
  - type/session-log
  - domain/ui
status: draft
source: agent
created: '2026-07-02'
updated: '2026-07-02'
---

# Session: Teach page UI fixes — nav emblem + page styling

## Summary

Fixed two UI issues on the Teach feature:

1. **Nav bar emblem**: Replaced bare diagonal-line SVG in the Teach tab with a proper graduation cap (mortarboard) icon, matching the 24×24 viewBox and visual style of other nav icons.

2. **Page styling**: The teach.html template was using non-existent CSS classes (`input`, `input-label`, `button--primary`, `button--ghost`) and pervasive inline styles. Fixed by:
   - Added `archetypes.css` include via `{% block extra_css %}`
   - Replaced `.input` → `.form-input` (defined in `components.css`)
   - Replaced `.input-label` → `.ds-label` (defined in `archetypes.css`)
   - Replaced `.button--*` → `.btn-*` (defined in `archetypes.css`)
   - Added Teach-specific CSS rules to `archetypes.css` (layout grid, sidebar, section titles, progress bar, compare grid, field groups, mobile responsive)
   - Moved session list items from inline HTML + inline styles to class-based rendering
   - Fixed non-existent CSS var references (`--accent-danger` → `--accent-red`, `--accent-success` → `--accent-green`, `--accent-2` → `color-mix`)

## Files Changed

- `anvil/api/templates/base.html` — Teach nav icon SVG replacement
- `anvil/api/templates/teach.html` — Full template restyle
- `anvil/api/static/css/archetypes.css` — Added Teach page layout CSS (~100 lines)