---
title: 'Quickstart: Non-Educational Help Guide'
type: spec
tags:
  - type/spec
  - domain/vault
status: draft
created: '2026-06-22'
updated: '2026-06-22'
---

Back to [[Specs/001 Non-Educational Help Guide/spec]].

# Quickstart: Non-Educational Help Guide

**Phase**: 1 | **Date**: 2026-06-22

## What are we building?

A single-page `/v1/help` route that renders operational help for all non-educational
workspace pages in the anvil web UI.

## Files to create

| File | Purpose |
|------|---------|
| `anvil/api/v1/help_content.py` | `HelpSection` model + `HELP_SECTIONS` data list |
| `anvil/api/templates/archetypes/help.html` | Single-page anchor-index template |

## Files to modify

| File | Change |
|------|--------|
| `anvil/api/v1/pages.py` | Add `@router.get("/help")` route handler |
| `anvil/api/templates/base.html` | Add "Help" tab to nav bar between "Play" and "Learn" (or before "About") |
| `tests/e2e/test_endpoints.py` | Add `test_help_page` e2e test |

## Implementation steps

1. **Create `help_content.py`** — Define `HelpSection(BaseModel)` and
   `HELP_SECTIONS` with content for each workspace page. Follow the
   `LEARNING_ARC` pattern from `learning.py`.

2. **Create `help.html`** — Single-page template extending `base.html`.
   Use `section-card` layout for each help section. Include an index/nav
   area at the top with anchor links. Render `{{ section.content | safe }}`
   for the body of each section.

3. **Add route in `pages.py`** — Import `HELP_SECTIONS`, add:
   ```python
   @router.get("/help", response_class=HTMLResponse)
   async def help_page(request: Request):
       return request.app.state.templates.TemplateResponse(
           request,
           "archetypes/help.html",
           {"sections": HELP_SECTIONS},
       )
   ```

4. **Add nav tab in `base.html`** — Add a new `<a>` tab-item link to
   `/v1/help` in the nav bar. Suggested placement: after Play (between
   Play and Learn, or after Ops before About).

5. **Write tests**:
   - e2e: `test_help_page` → `GET /v1/help` returns 200 with section titles
   - unit: `test_help_content` → `HelpSection` model validation

## Key constraints

- No new API routes (no `/v1/help/training`, etc.)
- Single URL: `/v1/help`
- Must comply with `docs/ux-rules.md` S4/S3
- Use Pydantic `BaseModel` (not dataclass)
- Existing design tokens only (no new CSS custom properties unless justified)