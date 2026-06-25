---
title: 'Research: Non-Educational Help Guide'
type: spec
tags:
  - type/spec
  - domain/vault
status: draft
created: '2026-06-22'
updated: '2026-06-22'
---
# Research: Non-Educational Help Guide

**Phase**: 0 | **Date**: 2026-06-22
**Feature**: Non-Educational Help Guide (`specs/001-non-educational-help-guide/`)

## Overview

No critical unknowns were identified during the clarify pass. This research document
consolidates the design decisions, alternatives considered, and pattern references
needed to implement the feature.

## Decisions

### Decision 1: Layout — Anchor-Index Single Page

- **Decision**: Single `/v1/help` page with all help sections stacked vertically,
  navigable via anchor links (`#training`, `#data`, `#experiments`, etc.).
- **Rationale**: Simple and boring. No extra routes, no per-section endpoints.
  Easy to add/edit sections as content evolves (expected churn for SaaS docs,
  operational guides, etc.). Matches the user's directive to avoid API complexity.
- **Alternatives considered**:
  - *Separate detail pages per workspace*: More routing code, more URL management,
    harder to maintain as content grows.
  - *Accordion single page*: Requires JavaScript; less straightforward anchor linking.
  - *Hybrid*: Highest implementation cost, over-engineering for a documentation page.

### Decision 2: Route Placement

- **Decision**: Add help route to existing `anvil/api/v1/pages.py`.
- **Rationale**: `pages.py` already houses all non-learning page routes (`/training-page`,
  `/experiments-page`, `/datasets-page`, `/inference-page`, `/operations-page`, `/about`).
  The help page follows the same pattern: a simple `@router.get("/help")` that
  returns a `TemplateResponse`.
- **Alternatives considered**:
  - *New sub-module in `v1/`*: Unnecessary for a single route handler.

### Decision 3: Content Data Structure

- **Decision**: Define help sections as a list of `BaseModel` objects in a new
  `anvil/api/v1/help_content.py` module, following the `LEARNING_ARC` pattern from
  `learning.py`.
- **Rationale**: Using the existing structured-data pattern keeps help content
  type-safe, testable, and easy to extend. `BaseModel` is required by the
  constitution (Article X + Additional Constraints: Pydantic for all new structured data).
- **Alternatives considered**:
  - *Hardcoded in template*: Poor separation of concerns, not testable.
  - *JSON file on disk*: Adds file I/O, breaks the all-Python pattern.

### Decision 4: Template Location

- **Decision**: Create `anvil/api/templates/archetypes/help.html` following the
  learn-index template pattern.
- **Rationale**: All page templates live in `archetypes/` — the help page is a page
  layout, not a partial or component.

### Decision 5: Testing Approach

- **Decision**: Add an e2e test for `GET /v1/help` returning 200 with expected
  help section titles, plus a unit test for the `HelpPageEntry` model.
- **Rationale**: Follows existing testing patterns (`tests/e2e/test_endpoints.py`
  for HTTP tests, `tests/unit/` for model tests). TDD mandate requires tests before
  implementation.

## Existing Patterns (References)

| Pattern | File | Notes |
|---------|------|-------|
| Index page route | `learning.py` line 1568 (`@router.get("/learn")`) | Returns `TemplateResponse` with data context |
| Nav bar with tab | `base.html` line 61-69 | Links added as `<a href="..." class="tab-item">` |
| Page template | `archetypes/learn-index.html` | Extends `base.html`, uses `section-card` layout |
| Structured content data | `learning.py` lines 91-218 (`LEARNING_ARC`) | List of dicts with `key`, `title`, `path`, `desc` |
| E2E test pattern | `tests/e2e/test_endpoints.py` | `async test_<endpoint>(client)` |

## Open Questions

None. All material decisions were resolved in the clarify pass.