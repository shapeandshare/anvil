# Tasks: Teach Page Onboarding & CTA Remediation

**Input**: Design documents from `docs/vault/Specs/081 Teach Page CTA/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md

**Tests**: Playwright e2e tests added for all 4 user stories following Constitution Article IV (TDD). Written before implementation.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Web app (this project)**: All frontend template/CSS/JS changes are in `anvil/api/templates/teach.html` and its inline `<style>`/`<script>` blocks

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: No project initialization needed — all existing infrastructure is reused.

No setup tasks required. Project structure, dependencies, and tooling are already configured.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Add the `completedRounds` tracking variable that all user stories depend on for state management.

- [x] T001 Add `completedRounds` variable (initialized to 0) alongside existing state vars at `anvil/api/templates/teach.html` lines 195-198, and add logic to increment it in the SSE `complete` event handler (line 361-368) and to reset it in `selectSession()` (line 220-224)

**Checkpoint**: Foundation ready — user story implementation can now begin

---

## Phase 3: User Story 1 — First visit: empty state guidance (Priority: P1) 🎯 MVP

**Goal**: A first-time user with no sessions sees a centered guidance card with welcome message, step list, and "Create Session" button instead of a blank main area.

**Independent Test**: Navigate to `/v1/teach` with no sessions. Main content area displays a centered guidance card with icon, welcome message, numbered steps (Create → Train → Inspect), and a "Create Session" button. Clicking it creates a session and transitions to active state.

### Implementation for User Story 1

- [x] T002 [US1] Add empty-state guidance card HTML to the main content area (`teach-layout` div) in `anvil/api/templates/teach.html` — a `section-card` with icon, welcome heading explaining the Teaching Loop, a numbered step list (Create Session → Train Round → Inspect Results), and a "Create Session" button that calls the existing `createSession()` function; visible when no session is active (use `id="empty-state-card"` with inline `display:none` initially)
- [x] T003 [US1] Add CSS for the empty-state guidance card in the existing `<style>` block at `anvil/api/templates/teach.html` (after line 191) — centered max-width container, step list with accent-colored numbered circles matching the `learn-arc-item` counter pattern from `anvil/api/templates/archetypes/learn-index.html`, and styled "Create Session" button
- [x] T004 [US1] Wire the empty-state card into the JS state machine: show it in `loadSessions()` (line 201-217) when `data.sessions.length === 0`, hide it when a session is selected or created; add `showEmptyState()` and `hideEmptyState()` helper functions; ensure the card's "Create Session" button calls the existing `createSession()` function (line 239-261)

**Checkpoint**: At this point, User Story 1 should be fully functional — blank main area is replaced with guidance on first visit.

---

## Phase 4: User Story 2 — Active session: flow continuity (Priority: P1)

**Goal**: A user with an active session sees CTAs at each workflow stage: "Start New Round" in the active session panel, and a post-training "Inspect This Round →" button that auto-fills the Inspect panel.

**Independent Test**: Select an existing session. See "Start New Round" button. Start a round, wait for completion → see "Inspect This Round →" button. Clicking it reveals the Inspect panel with the experiment ID pre-filled.

### Implementation for User Story 2

- [x] T005 [US2] Add "Start New Round" CTA button to the active session panel at `anvil/api/templates/teach.html` — insert a `<button>` with class `btn btn-primary` and id `start-round-cta` inside the `active-session-panel` div (around line 52-60), styled with `margin-top:var(--space-3)`; clicking it scrolls to and focuses the round form
- [x] T005a [US2] Add "Delete Session" button with confirmation dialog to the active session panel at `anvil/api/templates/teach.html` — insert a `<button>` with class `btn btn-secondary` and id `delete-session-cta` inside the `active-session-panel` div, styled with `color:var(--accent-red)` and `margin-top:var(--space-2)`; clicking it calls `deleteSession(activeSessionId)` after a `confirm()` dialog ("Delete this session? This does not delete MLflow runs.")
- [x] T005b [US2] Add "View Rounds" button to the active session panel at `anvil/api/templates/teach.html` — insert a `<button>` with class `btn btn-secondary` and id `view-rounds-cta` that calls `listRounds(activeSessionId)` and renders a collapsible round history list below the panel; add a `round-history` div (initially hidden) that populates from the `/v1/teach/sessions/{id}/rounds` GET endpoint
- [x] T006 [US2] Add post-training "Inspect This Round" CTA in the SSE `complete` event handler at `anvil/api/templates/teach.html` lines 361-368 — after the "Training finished successfully" text, insert a `<button id="inspect-cta" class="btn btn-primary">` with text "Inspect This Round →" that calls a new `showInspectWithRound(experimentId)` function
- [x] T007 [US2] Add the `showInspectWithRound(experimentId)` JS function at `anvil/api/templates/teach.html` — reveals the Inspect panel (`inspect-panel`), sets `inspect-experiment` input to the provided experiment ID, focuses the Inspect panel, and scrolls it into view; add corresponding CSS for the CTA button (margin, alignment) in the `<style>` block

**Checkpoint**: At this point, User Stories 1 AND 2 should both work independently — empty state guidance + flow continuity CTAs.

---

## Phase 5: User Story 3 — Progressive disclosure of panels (Priority: P2)

**Goal**: The Compare panel is hidden (or shows placeholder guidance) until 2+ completed rounds exist in the active session.

**Independent Test**: With < 2 rounds → Compare panel hidden or shows "Complete 2 rounds to compare". After 2+ rounds → Compare panel visible with experiment ID fields ready.

### Implementation for User Story 3

- [x] T008 [US3] Add conditional display logic for the Compare panel at `anvil/api/templates/teach.html` — add a `updateComparePanelVisibility()` JS function called from `loadSessionDetails()` and the SSE `complete` handler that checks `completedRounds >= 2` and sets `compare-panel` display accordingly; if `completedRounds < 2`, add placeholder text inside the panel (e.g., "Complete at least 2 rounds to compare models side-by-side.")

**Checkpoint**: User Story 3 functional — progressive disclosure eliminates unusable Compare panel from initial load.

---

## Phase 6: User Story 4 — Educational context and cross-references (Priority: P3)

**Goal**: The teach page matches visual consistency of other pages: "Did You Know?" banner, staggered entrance animations, learning-lesson CTA, and distinct "Create Session" button.

**Independent Test**: Load the page. Section cards animate in with staggered timing. Scroll to bottom → "Did You Know?" banner visible. Banner can be dismissed. Learning-lesson CTA present.

### Implementation for User Story 4

- [x] T009 [US4] Add `didyouknow_banner` block to `anvil/api/templates/teach.html` — add `{% block didyouknow_banner %}...{% endblock %}` before the final `{% endblock %}` at the end of the file, following the exact pattern from `anvil/api/templates/archetypes/playground.html` lines 484-492 (with the diamond icon, label, dismiss button, and JS-driven text)
- [x] T010 [US4] Add `--stagger-i` custom properties to all `section-card` divs in `anvil/api/templates/teach.html` — add `style="--stagger-i: N"` (incrementing from 0) on each visible card container, matching the pattern from `anvil/api/templates/archetypes/playground.html` lines 33, 82, 112
- [x] T011 [US4] Add a learning-lesson banner CTA to `anvil/api/templates/teach.html` — insert a `section-card section-card--banner` at the top of the `teach-main` div (following `anvil/api/templates/archetypes/playground.html` lines 14-30 pattern) with a link to the relevant concept lesson about iterative training, including an icon, title text, description, and a "Learn More →" button
- [x] T012 [US4] Make the sidebar "Create Session" button visually distinct in `anvil/api/templates/teach.html` — add inline style or CSS class to the submit button at line 44 to make it more prominent (e.g., `btn-accent` gradient class from `archetypes.css` line 30, or a subtle glow/pulse animation)

**Checkpoint**: All user stories functional — visual consistency with the rest of the application achieved.

---

## Phase 7: Tests (Constitution Article IV — TDD Compliance)

**Purpose**: Playwright e2e tests for the teach page UX remediation, written before implementation (Red-Green-Refactor). These tests cover the user-facing teach page rendered by the FastAPI app, using the existing Playwright browser test infrastructure (`make test-browser`).

> **Write these tests FIRST, ensure they FAIL (Red phase), then implement the corresponding tasks above (Green phase).**

- [x] T013 [P] Add Playwright e2e test for empty state guidance (US1) in `tests/browser/test_teach_ux.py` — navigates to `/v1/teach` with no sessions, asserts the guidance card is visible with welcome message, step list, and "Create Session" button; creates a session and asserts transition to active state
- [x] T014 [P] Add Playwright e2e test for flow continuity (US2) in `tests/browser/test_teach_ux.py` — selects a session, asserts "Start New Round" button is visible; starts a round with examples, waits for SSE completion, asserts "Inspect This Round" CTA appears; clicks it and asserts Inspect panel is visible with experiment ID pre-filled
- [x] T015 [P] Add Playwright e2e test for progressive disclosure (US3) in `tests/browser/test_teach_ux.py` — asserts Compare panel is hidden with fewer than 2 rounds; after completing 2 training runs, asserts Compare panel becomes visible with experiment ID fields
- [x] T016 [P] Add Playwright e2e test for visual polish (US4) in `tests/browser/test_teach_ux.py` — asserts section cards have `--stagger-i` attribute; asserts "Did You Know?" banner is present; asserts learning-lesson banner CTA is present; asserts sidebar "Create Session" button has distinct styling

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Verification gates and final validation after implementation

- [x] T017 Run `make ux-lint` on the changed template — must pass the deterministic S4 gate with zero findings before merge
- [x] T018 Run `make test-browser` — all Playwright e2e tests for the teach page must pass
- [x] T019 Manual verification against quickstart.md test scenarios — verify all 5 scenarios pass (empty state, active session CTAs, post-training flow, progressive disclosure, visual polish)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Foundational (Phase 2)**: No dependencies — can start immediately
- **User Story 1 (Phase 3)**: Depends on T001 (completedRounds tracking) for guidance card visibility
- **User Story 2 (Phase 4)**: Depends on US1 completion — uses active session panel that US1's guidance card transitions into
- **User Story 3 (Phase 5)**: Depends on completedRounds tracking (T001) and the SSE complete handler (T006) — can proceed after T001 + T006
- **User Story 4 (Phase 6)**: No dependencies on other user stories — pure visual polish additions
- **Tests (Phase 7)**: Written BEFORE implementation (TDD Red phase) — run test suite to confirm failures before implementing corresponding US tasks
- **Polish (Phase 8)**: Depends on all user stories and tests passing

### User Story Dependencies

- **User Story 1 (P1) MVP**: Can start after T001 — No dependencies on other stories
- **User Story 2 (P1)**: Depends on US1 — active session panel is the entry point
- **User Story 3 (P2)**: Depends on T001 + T006 — can be implemented in parallel with US2's remaining tasks
- **User Story 4 (P3)**: No dependencies on other stories — can start immediately after T001
- **Tests (Phase 7)**: Written before implementation (TDD Red phase) — must be written first, before the US tasks they test

### Within Each User Story

- Template HTML before inline CSS (content first, then styling)
- CSS before JS wiring (visible elements before behavior)
- All tasks for a given story must complete before that story is testable

### Parallel Opportunities

- All implementation tasks modify `anvil/api/templates/teach.html` — sequential execution is required within a file to avoid conflicts
- Test tasks (T013-T016) are all `[P]` — they create separate test files and can be written in parallel
- US3 (T008) and US4 (T009-T012) can be implemented in parallel if staffed to different team members, since they modify independent sections of the file (JS state logic vs. template blocks vs. inline CSS)
- US1 (T002-T004) must complete before US2 (T005-T007) due to dependency chain

---

## Parallel Example: User Stories 3 & 4

```bash
# US3 and US4 can run in parallel (independent sections of teach.html):
Task: "T008 - Add conditional display logic for Compare panel in teach.html JS"
Task: "T009 - Add didyouknow_banner block to teach.html"
Task: "T010 - Add --stagger-i entrance animations to section-card containers in teach.html"
Task: "T011 - Add learning-lesson banner CTA to teach.html"
Task: "T012 - Make sidebar Create Session button visually distinct in teach.html"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. **TDD Red phase**: Write Playwright e2e tests for US1 (T013) — confirm they fail
2. Complete Phase 2: T001 (completedRounds tracking)
3. Complete Phase 3: User Story 1 (Empty State Guidance)
4. **TDD Green phase**: Run Playwright tests — confirm US1 tests pass
5. **STOP and VALIDATE**: Test US1 independently — navigate to `/v1/teach` with no sessions, verify guidance card appears, verify "Create Session" creates a session
6. Already delivers the highest-impact fix: eliminating the dead initial state

### Incremental Delivery

1. Complete Phase 2 → Foundation ready
2. Add User Story 1 → Test independently → **MVP achieved** (dead initial state eliminated)
3. Add User Story 2 → Test independently → Full workflow with CTAs
4. Add User Story 3 → Test independently → Progressive disclosure
5. Add User Story 4 → Test independently → Visual parity with other pages

### Single-Developer Strategy

Sequential execution by phase order (Phase 2 → Phase 3 → Phase 4 → Phase 5 → Phase 6 → Phase 7) is the natural approach since all changes are in one file. Each task builds on the previous one without merge conflict risk.

---

## Notes

- [P] tasks = different sections of same file possible only if no overlap — most tasks here are sequential
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- All tasks target a single file: `anvil/api/templates/teach.html`
- No new files, no new dependencies, no backend changes required
- Reference patterns confirmed in: `anvil/api/templates/archetypes/playground.html`, `anvil/api/templates/archetypes/learn-index.html`, `anvil/api/templates/base.html`
- UX gate verification: `make ux-lint` must pass (S4 gate); optionally `make ux-review` for full AI UX audit