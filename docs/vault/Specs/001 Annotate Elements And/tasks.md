# Tasks: Visual Feedback Annotation

**Input**: Design documents from `docs/vault/Specs/001 Annotate Elements And/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/feedback-api.md, quickstart.md

**Tests**: Included per Constitution Article IV (TDD Mandatory) — each feature requires tests written before implementation.

**Organization**: Tasks grouped by user story for independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Web app**: `anvil/` (backend: Python + FastAPI), `anvil/api/static/` (frontend: vanilla JS)
- **Tests**: `tests/unit/`, `tests/e2e/`
- Paths follow the existing project structure

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure for the feedback annotation feature

- [ ] T001 [P] Create `anvil/services/feedback/` package with bare `__init__.py` (docstring-only)
- [ ] T002 [P] Create `anvil/db/models/feedback_report.py` with `FeedbackReport` and `FeedbackAnnotation` ORM models (use `TimestampMixin`, `Base`, `mapped_column`, `StrEnum`)
- [ ] T003 [P] Create `FeedbackStatus` and `AnnotationType` `StrEnum` classes in `anvil/services/feedback/`
- [ ] T004 [P] Add `feedback_dir` property to `anvil/workspace/workspace_paths.py` returning `Path` for `data/feedback/`
- [ ] T005 [P] Create `anvil/db/repositories/feedback_repository.py` with `FeedbackRepository` class (CRUD methods for both `FeedbackReport` and `FeedbackAnnotation`)
- [ ] T006 Generate Alembic migration for `feedback_reports` and `feedback_annotations` tables
- [ ] T007 [P] Create `anvil/api/v1/feedback.py` with route stubs for all feedback endpoints
- [ ] T008 [P] Create `anvil/api/static/css/feedback.css` with annotation overlay styles (using existing design tokens)
- [ ] T009 [P] Create `anvil/api/static/js/annotation.js` with `AnnotationCanvas` class skeleton (IIFE pattern, following `chart.js` conventions)
- [ ] T010 [P] Create `anvil/api/templates/partials/annotation-toolbar.html` with toolbar HTML structure
- [ ] T011 [P] Create `anvil/api/templates/feedback.html` extending `base.html` (following `operations.html` pattern)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [ ] T012 [P] Run Alembic migration (`make db-revision`) to apply `feedback_reports` and `feedback_annotations` tables to the database
- [ ] T013 [P] Implement `FeedbackRepository` CRUD methods: `create_report`, `get_report`, `list_reports`, `update_status`, `delete_report`, `batch_delete`, `add_annotation`, `get_annotations`
- [ ] T014 [P] Create `anvil/services/feedback/feedback_service.py` with `FeedbackService` class signature (constructor takes `FeedbackRepository`, `LocalFileStore`, `WorkspacePaths`)
- [ ] T015 [P] Add `FeedbackService` to the `AnvilWorkbench` god class
- [ ] T016 [P] Register feedback API routes in the FastAPI router
- [ ] T017 [P] Add `post /v1/feedback` endpoint stub in `anvil/api/v1/feedback.py` (accepts multipart form data with screenshot files)
- [ ] T018 [P] Add `get /v1/feedback-page` route handler in `anvil/api/v1/pages.py` (renders `feedback.html` template)
- [ ] T019 [P] Add "Feedback" nav tab to `anvil/api/templates/base.html` after the "Ops" tab
- [ ] T020 [P] Load `html-to-image` CDN script and `annotation.js` in `anvil/api/templates/base.html` (before `</body>`)
- [ ] T020a [P] Include `annotation-toolbar.html` partial in `anvil/api/templates/base.html` via `{% include "partials/annotation-toolbar.html" %}` (inside the app shell, before the modals container)

**Checkpoint**: Foundation ready — user story implementation can now begin in parallel

---

## Phase 3: User Story 1 — Annotate a Broken Element (Priority: P1) 🎯 MVP

**Goal**: Users can enter annotation mode, click on a broken UI element, leave a text note, and submit a feedback report.

**Independent Test**: Enter annotation mode, click on any visible UI element, attach a text note, and submit — confirm the annotation is saved and retrievable via the API.

### Tests for User Story 1 (TDD — write first, confirm fail)

- [ ] T021 [P] [US1] Unit test: `FeedbackService.create_report` stores screenshot and creates DB record in `tests/unit/services/test_feedback_service.py`
- [ ] T022 [P] [US1] Unit test: `FeedbackService.submit` with element annotation stores correct coordinates and note in `tests/unit/services/test_feedback_service.py`
- [ ] T023 [P] [US1] E2E test: POST `/v1/feedback` with element annotation multipart form data returns 201 in `tests/e2e/test_feedback.py`
- [ ] T024 [P] [US1] E2E test: GET `/v1/feedback/{id}` returns the submitted report with annotations in `tests/e2e/test_feedback.py`

### Implementation for User Story 1

- [ ] T025 [US1] Implement `AnnotationCanvas._captureScreenshot` in `anvil/api/static/js/annotation.js` — capture viewport using `html-to-image` `toPng()` and store as data URL
- [ ] T026 [US1] Implement `AnnotationCanvas._initCanvas` in `anvil/api/static/js/annotation.js` — create canvas with DPR-correct sizing (following `chart.js` pattern)
- [ ] T027 [US1] Implement annotation mode toggle in `anvil/api/static/js/annotation.js` — floating button triggers mode, shows toolbar, captures screenshot
- [ ] T028 [US1] Implement element click detection in `anvil/api/static/js/annotation.js` — on click, highlight the element under cursor, show note input popup
- [ ] T029 [US1] Implement note input UI in `anvil/api/static/js/annotation.js` — inline text input with 2000 char limit, confirm/cancel buttons
- [ ] T030 [US1] Implement annotation marker rendering in `anvil/api/static/js/annotation.js` — draw a small circle/badge at the element position on the canvas
- [ ] T031 [US1] Implement `FeedbackService.submit_report` in `anvil/services/feedback/feedback_service.py` — store screenshots via `LocalFileStore`, create `FeedbackReport` + `FeedbackAnnotation` records
- [ ] T032 [US1] Implement `POST /v1/feedback` endpoint in `anvil/api/v1/feedback.py` — accept multipart form with `screenshot`, `annotated`, `page_url`, `viewport_width`, `viewport_height`, `annotations` JSON
- [ ] T033 [US1] Implement annotation submission flow in `anvil/api/static/js/annotation.js` — serialize annotations as JSON, POST to `/v1/feedback` with screenshot files, handle success/error
- [ ] T034 [US1] Implement navigation away warning in `anvil/api/static/js/annotation.js` — `beforeunload` event when unsaved annotations exist
- [ ] T035 [US1] Implement toast notifications for errors in `anvil/api/static/js/annotation.js` — capture failure, empty submission, network error (using existing `toast-container` pattern)
- [ ] T036 [US1] Implement `GET /v1/feedback/{id}` endpoint in `anvil/api/v1/feedback.py` — return report with annotations

**Checkpoint**: At this point, User Story 1 should be fully functional — users can annotate elements and submit reports

---

## Phase 4: User Story 2 — Circle an Area and Leave Notes (Priority: P1)

**Goal**: Users can draw circles and freehand strokes on the viewport screenshot, attach notes, and submit alongside element annotations.

**Independent Test**: Enter annotation mode, draw a circle and freehand stroke on the page, attach notes, and submit — confirm circle and freehand annotations are saved.

### Tests for User Story 2 (TDD — write first, confirm fail)

- [ ] T037 [P] [US2] Unit test: `FeedbackService.submit` with circle annotation stores correct center/radius in `tests/unit/services/test_feedback_service.py`
- [ ] T038 [P] [US2] Unit test: `FeedbackService.submit` with freehand annotation stores correct path data in `tests/unit/services/test_feedback_service.py`
- [ ] T039 [P] [US2] E2E test: POST `/v1/feedback` with circle + freehand annotations returns 201 in `tests/e2e/test_feedback.py`

### Implementation for User Story 2

- [ ] T040 [US2] Implement tool selection UI in `anvil/api/static/js/annotation.js` — toolbar buttons for element/circle/freehand tools with active state
- [ ] T041 [US2] Implement circle drawing in `anvil/api/static/js/annotation.js` — mousedown starts circle, mousemove draws preview, mouseup finalizes with center + radius
- [ ] T042 [US2] Implement freehand drawing in `anvil/api/static/js/annotation.js` — mousedown starts path, mousemove records points, mouseup finalizes path data
- [ ] T043 [US2] Implement annotation preview rendering in `anvil/api/static/js/annotation.js` — draw circles (stroke) and freehand paths (stroke) on the canvas overlay
- [ ] T044 [US2] Implement annotation editing in `anvil/api/static/js/annotation.js` — click on existing annotation marker to edit or delete it
- [ ] T045 [US2] Implement annotation review panel in `anvil/api/static/js/annotation.js` — list of all annotations with type, note preview, edit/delete controls
- [ ] T046 [US2] Update `FeedbackService.submit_report` to handle all annotation types (element, circle, freehand) — no changes needed if data model is already generic
- [ ] T047 [US2] Update `POST /v1/feedback` to accept all annotation types — validation for each type's data schema

**Checkpoint**: At this point, User Stories 1 AND 2 should both work — full annotation toolkit operational

---

## Phase 5: User Story 3 — Review Submitted Feedback (Priority: P2)

**Goal**: Administrators can view, filter, search, export, and manage feedback reports through a dedicated dashboard.

**Independent Test**: Submit a feedback report with annotations, then navigate to the feedback dashboard and verify the report appears with all annotations intact.

### Tests for User Story 3 (TDD — write first, confirm fail)

- [ ] T048 [P] [US3] Unit test: `FeedbackService.list_reports` returns paginated results with status filter in `tests/unit/services/test_feedback_service.py`
- [ ] T049 [P] [US3] Unit test: `FeedbackService.update_status` transitions between valid states in `tests/unit/services/test_feedback_service.py`
- [ ] T050 [P] [US3] Unit test: `FeedbackService.delete_report` removes files from LocalFileStore and DB record in `tests/unit/services/test_feedback_service.py`
- [ ] T051 [P] [US3] Unit test: `FeedbackService.export_report` returns structured JSON with all annotations in `tests/unit/services/test_feedback_service.py`
- [ ] T052 [P] [US3] E2E test: GET `/v1/feedback` with status filter returns paginated list in `tests/e2e/test_feedback.py`
- [ ] T053 [P] [US3] E2E test: PATCH `/v1/feedback/{id}/status` updates report status in `tests/e2e/test_feedback.py`
- [ ] T054 [P] [US3] E2E test: DELETE `/v1/feedback/{id}` removes report in `tests/e2e/test_feedback.py`
- [ ] T055 [P] [US3] E2E test: GET `/v1/feedback/{id}/export` returns machine-readable JSON in `tests/e2e/test_feedback.py`

### Implementation for User Story 3

- [ ] T056 [US3] Implement `FeedbackService.list_reports` in `anvil/services/feedback/feedback_service.py` — paginated, filterable by status
- [ ] T057 [US3] Implement `FeedbackService.get_report` in `anvil/services/feedback/feedback_service.py` — single report with all annotations
- [ ] T058 [US3] Implement `FeedbackService.update_status` in `anvil/services/feedback/feedback_service.py` — validate state transitions (open → in_progress → resolved → open)
- [ ] T059 [US3] Implement `FeedbackService.delete_report` in `anvil/services/feedback/feedback_service.py` — remove screenshot files from LocalFileStore, delete DB record
- [ ] T060 [US3] Implement `FeedbackService.batch_delete` in `anvil/services/feedback/feedback_service.py` — delete multiple reports efficiently
- [ ] T061 [US3] Implement `FeedbackService.export_report` in `anvil/services/feedback/feedback_service.py` — return structured JSON with all metadata, annotations, screenshot URLs
- [ ] T062 [US3] Implement `GET /v1/feedback` endpoint in `anvil/api/v1/feedback.py` — paginated list with status filter
- [ ] T063 [US3] Implement `GET /v1/feedback/{id}/screenshot` endpoint in `anvil/api/v1/feedback.py` — serve annotated screenshot as `image/png`
- [ ] T064 [US3] Implement `GET /v1/feedback/{id}/export` endpoint in `anvil/api/v1/feedback.py` — return full JSON export
- [ ] T065 [US3] Implement `PATCH /v1/feedback/{id}/status` endpoint in `anvil/api/v1/feedback.py` — update report status
- [ ] T066 [US3] Implement `DELETE /v1/feedback/{id}` endpoint in `anvil/api/v1/feedback.py` — delete single report
- [ ] T067 [US3] Implement `POST /v1/feedback/batch-delete` endpoint in `anvil/api/v1/feedback.py` — delete multiple reports
- [ ] T068 [US3] Build feedback dashboard list view in `anvil/api/templates/feedback.html` — report table with status filter, pagination, stagger animation
- [ ] T069 [US3] Build feedback dashboard detail view in `anvil/api/templates/feedback.html` — report detail with annotations overlay, screenshot, notes
- [ ] T070 [US3] Implement report status update UI in `anvil/api/static/js/annotation.js` — status dropdown/buttons with PATCH call
- [ ] T071 [US3] Implement report delete confirmation modal in `anvil/api/static/js/annotation.js` — using existing `.modal-overlay` + `.modal-dialog` pattern
- [ ] T072 [US3] Implement batch delete UI in `anvil/api/templates/feedback.html` — checkbox selection, bulk delete button with confirmation
- [ ] T073 [US3] Implement report export button in `anvil/api/templates/feedback.html` — download JSON button per report row
- [ ] T074 [US3] Implement status filter UI in `anvil/api/templates/feedback.html` — filter tabs/buttons with active state
- [ ] T075 [US3] Add `GET /v1/feedback-page` route handler in `anvil/api/v1/pages.py` — render `feedback.html` template with context

**Checkpoint**: All user stories should now be independently functional

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [ ] T076 [P] **UX compliance gate**: Run `make ux-lint` on all changed UI/template/CSS files — must pass GATE: PASS before merge
- [ ] T077 [P] **AI UX review**: Run `make ux-review FILES=anvil/api/templates/feedback.html,anvil/api/templates/partials/annotation-toolbar.html,anvil/api/static/css/feedback.css,anvil/api/static/js/annotation.js` with `UX_API_KEY` set
- [ ] T078 [P] Add `prefers-reduced-motion` support for annotation overlay animations in `anvil/api/static/css/feedback.css`
- [ ] T078a [P] Add Playwright e2e test for annotation pixel accuracy — place annotations at known screen coordinates, submit, and verify coordinates are preserved within 1px tolerance in `tests/e2e/test_feedback.py`
- [ ] T078b [P] Add Playwright e2e test for annotation overlay non-blocking performance — verify annotation mode does not drop below 30fps during drawing operations on a mid-complexity page in `tests/e2e/test_feedback.py`
- [ ] T079 [P] Add `:focus-visible` styles for all annotation toolbar buttons in `anvil/api/static/css/feedback.css`
- [ ] T080 [P] Test annotation mode in both dark and light mode themes
- [ ] T081 [P] Add loading states for screenshot capture and submission in `anvil/api/static/js/annotation.js`
- [ ] T082 [P] Add empty state for feedback dashboard (no reports yet) in `anvil/api/templates/feedback.html`
- [ ] T083 [P] Run `make test` — full test suite must pass
- [ ] T084 [P] Run `make typecheck` — mypy strict must pass
- [ ] T085 [P] Run `make lint` — ruff, black, isort must pass
- [ ] T086 [P] Run `make vault-audit` — 0 errors required

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion — BLOCKS all user stories
- **US1 — Annotate Element (Phase 3)**: Depends on Foundational — No dependencies on other stories
- **US2 — Circle/Freehand (Phase 4)**: Depends on Foundational — Can proceed independently of US1 (though shares UI infrastructure)
- **US3 — Admin Review (Phase 5)**: Depends on Foundational + US1/US2 (needs reports to exist to review)
- **Polish (Phase 6)**: Depends on all user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: 🎯 MVP — Can start after Phase 2 — No dependencies on other stories
- **User Story 2 (P1)**: Can start after Phase 2 — Shared annotation canvas with US1, but independently testable
- **User Story 3 (P2)**: Depends on US1/US2 (reports to review) + Phase 2

### Within Each User Story

- Tests MUST be written and FAIL before implementation
- Models before services
- Services before endpoints
- Core implementation before integration
- Story complete before moving to next priority

### Parallel Opportunities

- All Setup tasks marked [P] can run in parallel (11 parallel tasks)
- All Foundational tasks marked [P] can run in parallel (9 parallel tasks)
- Once Foundational completes, US1 and US2 can start in parallel
- US3 can start once US1/US2 have created at least one report each
- All tests within a story marked [P] can run in parallel
- Polish tasks marked [P] can run in parallel

---

## Parallel Example: User Story 1 (MVP)

```bash
# Launch all tests for User Story 1 together:
pytest tests/unit/services/test_feedback_service.py -k "test_create_report or test_submit" -x
pytest tests/e2e/test_feedback.py -k "test_submit_feedback or test_get_feedback" -x

# Launch all independent implementation tasks for User Story 1 together:
# (assumes annotation.js is a single file — tasks within it are sequential)
# Task: Implement captureScreenshot in annotation.js
# Task: Implement initCanvas in annotation.js
# Task: Implement element click detection in annotation.js
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (11 parallel tasks)
2. Complete Phase 2: Foundational (9 parallel tasks)
3. Complete Phase 3: User Story 1 (16 tasks — tests first)
4. **STOP and VALIDATE**: Test User Story 1 independently
5. Deploy/demo if ready

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. Add User Story 1 (element annotation) → Test independently → Deploy/Demo (MVP!)
3. Add User Story 2 (circle/freehand) → Test independently → Deploy/Demo
4. Add User Story 3 (admin dashboard) → Test independently → Deploy/Demo
5. Each story adds value without breaking previous stories

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together
2. Once Foundational is done:
   - Developer A: User Story 1 (element annotation + submission)
   - Developer B: User Story 2 (circle/freehand drawing tools)
   - Developer C: Starts on User Story 3 after US1/US2 produce first reports
3. Stories complete and integrate independently

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Verify tests fail before implementing
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Total tasks: 89 (11 Setup + 10 Foundational + 16 US1 + 11 US2 + 28 US3 + 13 Polish)