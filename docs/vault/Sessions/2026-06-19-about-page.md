---
title: "Session: About Page with Governance & Licensing"
type: session-log
tags:
  - type/session-log
  - domain/ui
  - domain/governance
created: "2026-06-19"
updated: "2026-06-19"
aliases:
  - "Session: About Page with Governance & Licensing"
  - about-page
source: agent
status: draft
---

# Session: About Page with Governance & Licensing

**Date**: 2026-06-19
**Trigger**: User requested an about page including acceptable use terms and related governance information.

## What was done

### 1. Explored codebase architecture

Ran 4 parallel explore agents to map:
- **API v1 routes**: Identified `pages.py` as the dedicated module for page-rendering routes, with `get_workbench` dep injection pattern for governance data.
- **Jinja2 templates**: Mapped the `base.html` layout, nav bar structure (9 tab items), `acceptable_use.html` as the ideal template pattern (`section-card`, `help-box`, `param-block`).
- **Governance services**: Located `GovernanceService.list_licenses()`, `AuditService.verify_chain()`, the license seed data (10 OSI/CC entries), and `provenance.json` manifest.
- **Design system**: Mapped CSS tokens (`--text-*`, `--space-*`, `--accent-*`), archetypes (`section-card`, `param-block`, `help-box`), and `archetypes.css` import pattern.

### 2. Implemented about page

3 files changed:

| File | Change |
|------|--------|
| `anvil/api/templates/about.html` | New 220-line template with 5 sections: About anvil, Technology Stack, Architecture Overview, Governance & Licensing (live license catalog from DB, acceptable-use link, provenance docs), Resources |
| `anvil/api/v1/pages.py` | Added `GET /about` route with `Depends(get_workbench)` to fetch live license catalog via `GovernanceService.list_licenses()` |
| `anvil/api/templates/base.html` | Added "About" nav tab (ⓘ icon) as the last item in the nav bar |

### 3. Content included on the about page

- Project overview with version (from Jinja2 global)
- Technology stack breakdown (engine, web, frontend, distribution)
- Architecture layers (Core → Services → API → Storage → Governance)
- **Acceptable Use Policy** prominently linked
- Live license catalog iterating `LicenseEntry` objects from the governance service
- Data provenance documentation referencing `provenance.json`
- Resource links to Datasets, Learn, Ops, and Dashboard

## Architecture decisions

- **Page route location**: Added to `pages.py` rather than `router.py` — follows the decomposed pattern where pages.py is the designated module for page-rendering routes. The `acceptable-use` route (in `router.py`) is likely a remnant yet to be migrated.
- **Live catalog vs static copy**: Chose to fetch licenses via `GovernanceService.list_licenses()` so the page always reflects the current DB state (new seeds added later will appear automatically).
- **No ADR warranted** — straightforward page addition following established patterns (same route structure as `datasets_page`, same template pattern as `acceptable_use.html`, same design tokens as all other pages).

## References

- `anvil/api/v1/pages.py` — `about_page()` handler
- `anvil/api/templates/about.html` — about page template
- `anvil/api/templates/acceptable_use.html` — acceptable use policy template (linked)
- `anvil/services/governance/governance_service.py` — `GovernanceService.list_licenses()`
- `anvil/api/static/css/tokens.css` — design system tokens