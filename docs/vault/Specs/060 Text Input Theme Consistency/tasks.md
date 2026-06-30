# Tasks: Text Input Theme Consistency

**Input**: Design documents from `docs/vault/Specs/060 Text Input Theme Consistency/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, quickstart.md

**Tests**: Not requested — this is a visual CSS refactor. Verification via `make ux-lint` (S4 gate) and manual visual audit.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **CSS root**: `anvil/api/static/css/`
- **Template root**: `anvil/api/templates/`
- **Theme root**: `anvil/api/static/css/themes/`
- All paths are relative to repository root.

---

## Phase 1: Setup (Knowledge Acquisition)

**Purpose**: Load all design documents and understand the full scope before editing

- [X] T001 Read `docs/vault/Specs/060 Text Input Theme Consistency/plan.md` to understand technical approach and project structure
- [X] T002 Read `docs/vault/Specs/060 Text Input Theme Consistency/quickstart.md` for the ordered implementation guide
- [X] T003 Read `docs/vault/Specs/060 Text Input Theme Consistency/research.md` for key decisions (border strategy, focus pattern, widget handling, disabled/readonly)
- [X] T004 Run `make ux-lint` on current state to establish S4 baseline (no regressions expected on unchanged CSS)

---

## Phase 2: Foundational (Core CSS Class Changes)

**Purpose**: Update the canonical `.form-input` class in components.css — this is the single blocking prerequisite for all three user stories.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T005 [P] Add `border: 1px solid var(--separator)` to `.form-input`, `.form-select`, `.widget-input` in `anvil/api/static/css/components.css` (was `border: none`)
- [X] T006 [P] Change `border-radius` on `.form-input`, `.form-select`, `.widget-input` from `var(--radius)` (13px) to `var(--radius-sm)` (8px) in `anvil/api/static/css/components.css`
- [X] T007 [P] Add `min-height: var(--touch-min)` to `.form-input`, `.form-select` in `anvil/api/static/css/components.css`
- [X] T008 [P] Migrate focus ring from `:focus` to `:focus-visible` with `:focus` fallback on `.form-input`, `.form-select`, `.widget-input` in `anvil/api/static/css/components.css`
- [X] T009 [P] Add `.form-input:disabled` and `.form-input[readonly]` state rules in `anvil/api/static/css/components.css`
- [X] T010 [P] Add `.form-input:hover:not(:disabled)` with subtle border color change (`var(--text-tertiary)`) in `anvil/api/static/css/components.css`

**Checkpoint**: Core input class updated — all inputs using `.form-input` now have consistent border, radius, focus, hover, disabled, and readonly styling.

---

## Phase 3: User Story 1 — Consistent Input Appearance (Priority: P1) 🎯 MVP

**Goal**: Every text-editing input across every page shares the same visual style — same background, border, radius, padding, font, placeholder, and focus indicator.

**Independent Test**: Open any two pages with text inputs and compare them side by side — they should be visually indistinguishable in structure.

### Implementation for User Story 1

- [X] T011 [US1] Migrate `class="input"` to `class="form-input"` on config modal in `anvil/api/templates/config.html` line 307
- [X] T012 [US1] Add `class="form-input"` to all 7 bare `<input type="number">` elements in `anvil/api/templates/archetypes/training.html` (lines 116, 122, 128, 135, 142, 148, 154)
- [X] T013 [US1] Simplify `.param-block input` in `anvil/api/static/css/archetypes.css` — remove redundant visual properties (background, border, border-radius, color, font-family, font-size, outline, transition) — let `.form-input` handle them. Keep only `width: 100%` and `box-sizing: border-box`.
- [X] T014 [US1] Migrate `class="login-card__input"` to `class="form-input"` in `anvil/api/templates/login.html` line 24
- [X] T015 [US1] Remove `.login-card__input` rule block (lines 72-91) from `anvil/api/static/css/login.css` — `.form-input` now covers all visual properties
- [X] T016 [US1] Remove `.terminal-input` selectors from `anvil/api/static/css/components.css` — consolidate into `.form-input` (they share identical rules). Ensure `input[type="file"]::file-selector-button` styling (lines 65-71) is preserved under `.form-input`
- [X] T017 [P] [US1] Remove `border: none` from `.widget-input` in `anvil/api/static/css/components.css` — let it inherit the new border from shared tokens (keep its mono font and width:100%)
- [X] T018 [US1] Fix compute backend `<select>` inline styles in `anvil/api/templates/archetypes/training.html` line 161 — remove inline background, border, color, border-radius, font-size; apply `class="form-input"`

**Checkpoint**: All inputs across all templates now use `.form-input` or `.widget-input` (aligned tokens) — consistent appearance achieved in default theme.

---

## Phase 4: User Story 2 — Themed Inputs Adapt to Behavioral Themes (Priority: P1)

**Goal**: Inputs automatically adopt behavioral theme colors when any of the 23 themes is active — background, border, focus ring, and placeholder all shift with theme tokens.

**Independent Test**: Activate any 3 contrasting themes (e.g., Tide, Old Growth, Hyperspace) and verify inputs use each theme's color palette. Re-enable default theme — inputs return to standard appearance.

### Implementation for User Story 2

- [X] T019 [US2] Verify base token coverage — confirm `.form-input` uses only `--surface-2`, `--separator`, `--accent`, `--text-tertiary`, `--radius-sm`, `--touch-min`, `--text` — all tokens that themes override. Search `anvil/api/static/css/components.css` lines 44-52 and 190-191 for any hardcoded values.
- [X] T020 [US2] Audit all 23 theme CSS files in `anvil/api/static/css/themes/` for input legibility — activate each theme in a browser, navigate to the training page, and visually confirm inputs are readable (text visible, boundary clear, focus ring visible)
- [X] T021 [US2] If any themes produce unreadable inputs (invisible boundaries, illegible text, invisible focus ring), add theme-specific input overrides in the respective `themes/<id>.css` file (document each override in research.md)

**Checkpoint**: All 23 themes produce readable, visually distinct inputs that adopt the theme's color palette.

---

## Phase 5: User Story 3 — Touch-Friendly Input Targets (Priority: P2)

**Goal**: All text inputs meet 44px minimum touch-target height on mobile viewports, matching iOS HIG.

**Independent Test**: On a ≤480px viewport (phone width), measure every distinct input type — all must be ≥44px tall.

### Implementation for User Story 3

- [X] T022 [US3] Verify `.form-input` and `.form-select` have `min-height: var(--touch-min)` — already added in T007. Confirm in `anvil/api/static/css/components.css`
- [X] T023 [US3] Verify `.widget-input` also has `min-height: var(--touch-min)` — add if missing in `anvil/api/static/css/components.css` line 190
- [X] T024 [US3] Verify login page — since login input now uses `.form-input`, it should inherit `min-height` automatically. Confirm in `anvil/api/templates/login.html`
- [X] T025 [US3] On mobile viewport (≤480px), verify 8px vertical gap between adjacent inputs — check forms on training, datasets, and config pages at phone width

**Checkpoint**: All inputs meet iOS HIG 44px touch target on mobile viewports.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Validation, visual QA, and cleanup

- [X] T026 [P] Run `make ux-lint` on all changed CSS/template files — must pass GATE: PASS
- [X] T027 [P] Run `make lint` to verify no Python/style regressions
- [X] T028 Visual audit checklist — open each page and verify:
  - Training page (all 7 param inputs + compute backend select) in dark and light mode
  - Datasets page (search, create, corpus wizard, inline-edit inputs)
  - Config page (modal edit input)
  - Login page
  - Playground page (prompt, temperature, num-samples)
  - HF Browser (search bar)
  - Concept widgets (tokenization, loss, embedding, attention — verify `widget-input` renders correctly)
  - Activate Tide theme (light/dark capable) — verify inputs adapt
  - Activate Old Growth theme (dark-only, high saturation) — verify legibility
  - Activate Forge theme (dark-only) — verify focus ring visible
  - Set viewport to 480px — verify 44px touch target on at least 3 pages
- [X] T029 Run `make ux-lint` final pass — must pass GATE: PASS
- [X] T030 Verify inputs under "Reduce effects" mode — enable the "Reduce effects" toggle in the theme picker, confirm inputs display with solid backgrounds, visible borders, and no decorative/animating effects
- [X] T031 Update `docs/vault/Sessions/` with a session log noting all files modified and key decisions

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — load knowledge first
- **Foundational (Phase 2)**: Depends on Setup — **BLOCKS** all user stories (core class change affects everything)
- **US1 (Phase 3)**: Depends on Foundational — template migrations require the fixed core class
- **US2 (Phase 4)**: Depends on Foundational — can run in parallel with US3 (different concerns: themes vs mobile)
- **US3 (Phase 5)**: Depends on Foundational — can run in parallel with US2
- **Polish (Phase 6)**: Depends on all user stories complete

### Within Each User Story

- Tasks within US1 labeled [P] can run in parallel (different files)
- US2 and US3 depend on Foundational but NOT on each other — they can execute in parallel

### Parallel Opportunities

- T005–T010 (Foundational): All marked [P] — independent CSS property changes in the same file, but on different CSS rules/selectors so no conflicts
- T011–T018 (US1): T017 is [P] — widget-input change is independent of template migrations
- US2 (Phase 4) can start as soon as Phase 2 (Foundational) completes — does not wait for US1
- US3 (Phase 5) can start as soon as Phase 2 (Foundational) completes — does not wait for US1 or US2
- T026–T027 (Polish): [P] — lint and ux-lint can run simultaneously

---

## Parallel Example: User Story 1

```bash
# Launch all independent template migrations together:
Task: "Fix config modal class in anvil/api/templates/config.html"
Task: "Add form-input class to 7 param inputs in anvil/api/templates/archetypes/training.html"
Task: "Fix login page class in anvil/api/templates/login.html"
Task: "Fix compute_backend select in anvil/api/templates/archetypes/training.html"
```

---

## Implementation Strategy

### MVP First (User Story 1 + 3)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (core CSS — prerequisite)
3. Complete Phase 3: User Story 1 (all inputs look consistent)
   - This also achieves SC-004 (light mode boundary) and SC-005 (touch target from T007)
4. **STOP and VALIDATE**: Visual audit across all pages in dark and light mode
5. Deploy/demo MVP: consistent inputs, visible boundaries, touch-friendly sizing

### Incremental Delivery

1. Setup + Foundational → Core `.form-input` class is fixed
2. User Story 1 → All input orphans migrated, consistent look across pages (MVP)
3. User Story 2 → Theme adaptation verified (can run in parallel with US3)
4. User Story 3 → Touch targets verified (can run in parallel with US2)
5. Polish → Lint and final validation

---

## Notes

- [P] tasks = different files or independent property changes
- [Story] label maps task to specific user story for traceability
- Each user story is independently completable and testable
- No test tasks generated (no backend changes, no test framework for visual CSS)
- Verification is via `make ux-lint` (S4 gate) and manual visual audit per T028
- Stop at any checkpoint to validate story independently
