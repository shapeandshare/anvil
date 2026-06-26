---
title: 'Tasks: Non-Educational Help Guide'
type: spec
tags:
  - type/spec
  - domain/vault
status: draft
created: '2026-06-22'
updated: '2026-06-22'
---

Back to [[Specs/001 Non-Educational Help Guide/spec]].

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core data model that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T001 Create `HelpSection` Pydantic model in `anvil/api/v1/help_content.py`

**Checkpoint**: `HelpSection` base model ready — user story implementation can now begin

---

## Phase 3: User Story 1 — Browse workspace help from the nav bar (Priority: P1) 🎯 MVP

**Goal**: Users can click a "Help" nav tab and see a help index page listing all workspace pages with anchor links to detailed sections.

**Independent Test**: Navigate to any page, click "Help" in the nav bar, verify the index renders with entries for all workspace pages and anchor links work.

### Implementation for User Story 1

- [x] T002 [P] [US1] Create help page template at `anvil/api/templates/archetypes/help.html` — extends `base.html`, loads `archetypes.css`, includes index listing with anchor links
- [x] T003 [P] [US1] Add "Help" nav bar tab in `anvil/api/templates/base.html` — add `<a href="/v1/help">` tab-item between "Play" and "Learn"
- [x] T004 [US1] Add `/v1/help` route handler in `anvil/api/v1/pages.py` — import `HELP_SECTIONS`, add `@router.get("/help")` async handler returning `TemplateResponse("archetypes/help.html", {"sections": HELP_SECTIONS})`
- [x] T005 [US1] Write `test_help_page` e2e test in `tests/e2e/api/test_pages.py` — verify `GET /v1/help` returns 200 and contains expected section titles

**Checkpoint**: At this point, US1 should be fully functional and testable independently — nav bar link exists, help index renders with listings, anchors work.

---

## Phase 4: User Story 2 — Read detailed help for a workspace page (Priority: P1)

**Goal**: Each help section contains detailed content explaining the page's purpose, controls, workflows, and links to related learning lessons.

**Independent Test**: Navigate to the Help page, click any workspace section, verify detailed content renders including descriptions of controls and workflows.

### Implementation for User Story 2

- [x] T006 [P] [US2] Define `HELP_SECTIONS` data with authored content for all 7 workspace pages in `anvil/api/v1/help_content.py` — Training, Data, Experiments, Models, Playground, Operations, Content Library
- [x] T007 [US2] Render detailed help sections with anchor navigation in `anvil/api/templates/archetypes/help.html` — iterate `sections`, render `{{ section.content | safe }}`, add `id="{{ section.anchor_id }}"` to each section card, add related lessons resolution
- [x] T008 [P] [US2] Write unit test for `HelpSection` model validation in `tests/unit/api/test_help_content.py`

**Checkpoint**: At this point, US1 AND US2 should both work — clicking a section title scrolls to detailed content with meaningful help text and related lesson links.

---

## Phase 5: User Story 3 — Access help content without leaving the workspace (Priority: P2)

**Goal**: Each workspace page includes a contextual "Help guide" link pointing to its corresponding help section on the `/v1/help` page.

**Independent Test**: Open any workspace page, find the help link/icon, click it and verify it navigates to the correct anchor on `/v1/help`.

### Implementation for User Story 3

- [x] T009 [US3] Add contextual "Help guide" link to workspace page templates — extend the `related_lessons` section in each page's template context or template to include a link to `/v1/help#<anchor_id>`

**Checkpoint**: US3 adds cross-linking between workspace pages and help sections.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Quality assurance, type checking, UX compliance, and documentation.

- [x] T010 [P] Run `make ux-lint` on `anvil/api/templates/archetypes/help.html` and fix any S4/S3 findings — must comply with `docs/ux-rules.md`
- [x] T011 [P] Run `make typecheck` (`mypy --strict`) on `anvil/api/v1/help_content.py` and `anvil/api/v1/pages.py` — fix any type errors
- [x] T012 [P] Run `make lint` on all changed files — fix any ruff/pylint issues

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — skipped (project already initialized)
- **Foundational (Phase 2)**: No dependencies — can start immediately. BLOCKS all user stories
- **US1 (Phase 3)**: Depends on T001 (Foundational). Can start after T001
- **US2 (Phase 4)**: Depends on T002 (template), T004 (route), and T001 (HelpSection model). Can run in parallel with US1 tasks
- **US3 (Phase 5)**: Depends on US1 being complete (help page must exist before linking to it)
- **Polish (Phase 6)**: Depends on all implementation phases (US1, US2, US3)

### User Story Dependencies

- **US1 (P1)**: Can start after T001 — No dependencies on other stories
- **US2 (P1)**: Shares template with US1 but content tasks (T006, T008) are independent of US1's nav/tab tasks (T003, T005). T007 (detailed rendering) depends on T002 (template shell).
- **US3 (P2)**: Must wait for US1 completion (no help sections exist to link to)

### Within Each User Story

- Tests MUST be written and FAIL before implementation (TDD mandate)
- Models before services (T001 before everything)
- Templates before routes (template must exist for route to reference)
- Story complete before moving to next priority

### Parallel Opportunities

- **T002 and T003** [P]: Template creation and nav bar modification are independent
- **T006 and T008** [P]: Content authoring and unit tests are independent
- All Polish tasks marked [P] can run in parallel

---

## Parallel Example: User Story 1

```bash
# Launch template + nav bar simultaneously:
Task: "Create help.html template in anvil/api/templates/archetypes/help.html"
Task: "Add Help nav tab in anvil/api/templates/base.html"

# After both complete, add route:
Task: "Add /v1/help route handler in anvil/api/v1/pages.py"

# After route added, write e2e test:
Task: "Write test_help_page e2e test in tests/e2e/test_endpoints.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 2: Foundational (T001)
2. Complete Phase 3: US1 — Help index with nav bar, route, template, content model
3. **STOP and VALIDATE**: Test US1 independently (nav link → index page → anchor links)
4. Deploy/demo if ready

### Incremental Delivery

1. Complete Foundational (T001) → Foundation ready
2. Add US1 (T002-T005) → Help index + nav bar → **MVP!**
3. Add US2 (T006-T008) → Detailed help content for all pages
4. Add US3 (T009) → Contextual cross-links
5. Polish (T010-T012) → Quality gate pass
6. Each story adds value without breaking previous stories

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- TDD mandate: write tests first, verify they fail, then implement
- Stop at any checkpoint to validate story independently
- UX compliance (`docs/ux-rules.md` S4/S3) is mandatory for all template/CSS changes
- Avoid: vague tasks, same file conflicts, cross-story dependencies that break independence