---
title: 'Feature Specification: Non-Educational Help Guide'
type: spec
tags:
  - type/spec
  - domain/vault
status: draft
created: '2026-06-22'
updated: '2026-06-22'
---

Back to [[Specs/001 Non-Educational Help Guide/spec]].

### User Story 3 - Access help content without leaving the workspace (Priority: P2)

A user is on the Datasets page and wants quick clarification on what "chunking strategy" means. They click a help icon or link near the relevant UI section and are taken directly to the relevant part of the help page, or see a tooltip/explanation inline. This bridges the gap between the workspace page and the help content.

**Why this priority**: This enhances the basic help system with in-context access, reducing friction and back/forth navigation.

**Independent Test**: Can be tested by checking for help links or help icons on each workspace page that link to the relevant help section. The "Related lessons" row could be extended to point at help content.

**Acceptance Scenarios**:

1. **Given** the user is on a workspace page, **When** they view the page, **Then** they see a contextual help link (e.g. "How does this work?" or a help icon) that navigates to the corresponding help section.
2. **Given** the workspage page has a "Related lessons" section, **When** it renders, **Then** it may also include a "Help guide" link to the workspace help section for this page.

---

### Edge Cases

- What happens when new workspace pages are added in the future? The help page should be designed so that adding a new entry is a straightforward data change (e.g., adding an item to a structured list).
- How does the help page behave on very narrow viewports? Content sections should not overflow or become unreadable; the design system's responsive layout should handle this.
- What if a user navigates directly to a help anchor (e.g., `/v1/help#training`)? The page should scroll to the correct section.
- What happens when the help page is accessed without authentication? It follows the app's existing auth rules — requires login like other page routes.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide a top-level Help page accessible from the navigation bar, alongside existing tabs (Data, Train, Exps, Models, Play, Learn, Ops, About).
- **FR-002**: The Help index page MUST list all non-educational workspace pages with a title and short description for each.
- **FR-003**: Each workspace page entry on the Help index MUST link via anchor (e.g., `#training`) to the corresponding detailed help section on the same page.
- **FR-004**: The detailed help sections MUST describe: the page's purpose, key controls/fields/actions explained in plain language, common workflows, and links to relevant learning lessons where applicable.
- **FR-005**: The Help page MUST cover the following workspace pages: Dashboard/Training, Data (datasets + corpora), Experiments, Models, Playground/Inference, Operations, and Content Library.
- **FR-006**: System MUST NOT include learning-path lesson content (tokenization, embeddings, attention, etc.) in the Help page — those remain in the Learn section.
- **FR-007**: The Help page MUST be responsive and follow the existing design system (tokens, components, archetypes).
- **FR-008**: The Help page MUST be a single-page anchor-index layout — all sections stacked vertically on one URL (`/v1/help`), navigable via anchor links (`#training`, `#data`, `#experiments`, etc.). No per-section routes or separate pages.
- **FR-009**: When new workspace pages are added, adding help content for them SHOULD require only adding an entry to a structured data source (not rewriting the template).
- **FR-010**: Each workspace page MAY include a link or button pointing to its corresponding help section on the new Help page, increasing discoverability.

### Key Entities *(include if feature involves data)*

- **Help Page Entry**: A single indexed item representing one workspace page. Contains: page name, route path, short description, detailed help content (purpose, controls, workflows), related lesson keys, and a unique anchor ID.
- **Help Index**: The ordered collection of all Help Page Entries, rendered as the top-level listing with anchors for each detail section.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can navigate from any page in the app to the Help index in 1 click (via the nav bar link).
- **SC-002**: The Help page covers 100% of the non-educational workspace pages (Training/Dashboard, Data, Experiments, Models, Playground, Operations, Content Library).
- **SC-003**: A user can find the relevant help section for any workspace page within 2 clicks of reaching the Help index.
- **SC-004**: Adding help content for a new workspace page requires only a single data-format change (no template edits).
- **SC-005**: The Help page maintains the same design quality as existing pages — no layout breaks, consistent typography, proper responsive behavior.
- **SC-006**: 0% of learning-path lesson content appears on the Help page — strict separation between educational and operational help.

## Assumptions

- The Help page will be rendered via Jinja2 templates using the same archetypes and design system as existing pages.
- Help content for each workspace page will be authored as structured data (list/dict) in a Python module, similar to how `LEARNING_ARC` and lesson steps are defined in `learning.py`.
- The new nav bar tab ("Help") will use the single URL `/v1/help` and will be added to the nav bar in `base.html` alongside existing tabs.
- The existing "Related lessons" pattern in `pages.py` serves as a reference for connecting help sections to learning content where relevant.
- No new API routes or per-section endpoints are needed — the help page is a single static-rendered page with anchor navigation.
- Help content is expected to grow over time (SaaS docs, operational guides, etc.). The anchor-index layout naturally accommodates churn without routing changes.
- Per-page contextual links are desirable but not required for the initial version (P2).
- The design system tokens (CSS custom properties, components) have sufficient spacing and typography tokens to render help content without new component additions.