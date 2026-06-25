---
title: 'Implementation Plan: Non-Educational Help Guide'
type: spec
tags:
  - type/spec
  - domain/vault
status: draft
created: '2026-06-22'
updated: '2026-06-22'
---
# Implementation Plan: Non-Educational Help Guide

**Branch**: `opencode/lucky-canyon` | **Date**: 2026-06-22 | **Spec**: `specs/001-non-educational-help-guide/spec.md`
**Input**: Feature specification from `specs/001-non-educational-help-guide/spec.md`

## Summary

Add a top-level Help page (`/v1/help`) to the anvil web UI using a single-page anchor-index layout. The page provides operational/reference help for non-educational workspace pages (Data, Train, Experiments, Models, Playground, Operations, Content Library). No new API routes or data persistence required — just a Jinja2 template, a nav bar link, and structured help content data.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: FastAPI + Jinja2 (existing project stack — no new deps)
**Storage**: N/A — static content defined as structured data in a Python module
**Testing**: pytest (existing); e2e HTTP test via client fixture in `tests/e2e/`
**Target Platform**: Web (any browser that supports CSS anchor links)
**Project Type**: Web application (FastAPI + Jinja2)
**Performance Goals**: N/A — static rendered page, no dynamic queries
**Constraints**: Single page, no per-section routes (anchor-index only); must comply with `docs/ux-rules.md` S4/S3; must follow existing design tokens
**Scale/Scope**: One route `/v1/help`, one Jinja2 template, ~7 help sections, structured data in a Python module

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Article | Rule | Assessment |
|---------|------|------------|
| Article V | Async-First | PASS — FastAPI page handler is async by default |
| Article VI | `__init__.py` Ownership | PASS — no new packages needed; `anvil/api/v1/__init__.py` already exists |
| Article VII | Layered Architecture | PASS — page route goes in existing `pages.py`; no service/repo layer needed |
| Article VIII | iOS-Grade Polish | **CAUTION** — template must use `docs/ux-rules.md` and existing design tokens |
| Article IX | Pit of Success | PASS — help page works out of box, no config needed |
| Article X | Domain-Driven Decomposition | N/A — no new service packages |
| Additional | Pydantic BaseModel | PASS — help entry entities will use `BaseModel` |
| Additional | UI compliance (ux-rules.md) | **CAUTION** — S4/S3 findings must be resolved in template/CSS |
| Additional | One class per file | PASS — help entry model in its own file; route handler in existing `pages.py` |

**Gate verdict**: PASS — no violations. Will re-check after Phase 1 for UI compliance.

## Project Structure

### Documentation (this feature)

```text
specs/001-non-educational-help-guide/
├── spec.md              # Feature specification
├── plan.md              # This file (plan)
├── research.md          # Phase 0 — research findings
├── data-model.md        # Phase 1 — entity design
├── quickstart.md        # Phase 1 — developer onboarding
├── contracts/           # Phase 1 — interface contracts
└── tasks.md             # Phase 2 — task breakdown (created by /speckit.tasks)
```

### Source Code (repository)

```text
anvil/api/
├── v1/
│   ├── pages.py                 # ← Add GET /v1/help route handler
│   ├── learning.py              # Reference: data pattern for help entries
│   └── help_content.py          # NEW — structured help entry data (py dict/BaseModel)
├── templates/
│   ├── base.html                # ← Add "Help" nav bar tab
│   └── archetypes/
│       ├── learn-index.html     # Reference: index page pattern
│       └── help.html            # NEW — help page template (anchor-index single page)
├── static/
│   └── css/
│       ├── components.css       # May need .help-section styles
│       └── archetypes.css       # May need help archetype class

tests/
├── e2e/
│   └── test_endpoints.py        # ← Add e2e test for /v1/help endpoint
└── unit/
    └── api/
        └── test_help_content.py # NEW — unit test for help content model
```

**Structure Decision**: Single project web application. Follows existing page-rendering pattern: route in `pages.py`, template in `archetypes/`, data in a new `help_content.py` module (following `learning.py`'s data pattern).

## Phase 0: Research

**Status**: No critical unknowns. All technical decisions were made during clarify:
- **Layout**: Anchor-index single page (confirmed)
- **Route**: `/v1/help` (no per-section sub-routes)
- **Data structure**: Structured dict/list in Python module, following `LEARNING_ARC` pattern from `learning.py`
- **Help content authorship**: Content authored inline in the data module (part of implementation)

See `research.md` for the full consolidation.

## Phase 1: Design

**Output artifacts**:
- `data-model.md` — HelpPageEntry entity with Pydantic BaseModel
- `contracts/` — Route contract, template interface
- `quickstart.md` — Developer quickstart

## Phase 2: Tasks

Phase 2 artifacts (tasks.md) will be generated by `/speckit.tasks`.

## Complexity Tracking

No constitution violations to justify. Feature is low complexity — single route, single template, structured data, no new services or dependencies.