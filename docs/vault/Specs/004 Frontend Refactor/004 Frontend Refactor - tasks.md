---
title: 004 Frontend Refactor - tasks
type: tasks
tags:
  - type/spec
spec-refs:
  - docs/vault/Specs/004 Frontend Refactor/
related:
  - '[[004 Frontend Refactor]]'
created: ~
updated: ~
---
# Tasks: Systemic Frontend Refactor — microGPT Learning Tool

**Input**: Design documents from `docs/vault/Specs/004 Frontend Refactor/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/
**Tests**: Not requested — frontend tasks are manual verification via browser

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Frontend files**: `anvil/api/static/css/`, `anvil/api/static/js/`, `anvil/api/templates/`
- **Backend files**: `anvil/api/v1/` (routes remain, minor additions)

---

## Phase 1: Setup (Project Structure)

**Purpose**: Create the new frontend directory structure with empty files ready for implementation

- [x] T001 Create CSS directory structure at `anvil/api/static/css/` (tokens.css, base.css, archetypes.css, components.css, utilities.css, code.css)
- [x] T002 [P] Create JS directory structure at `anvil/api/static/js/` (core.js, sse.js, chart.js, scroll-scene.js, graph-view.js, widgets/)
- [x] T003 [P] Create archetype template directory at `anvil/api/templates/archetypes/` (concept.html, training.html, experiment.html, playground.html)
- [x] T004 [P] Create partials template directory at `anvil/api/templates/partials/` with subdirectories for scroll-scene.html, streaming-chart.html, concept-widgets/, graph-view.html

---

## Phase 2: Foundational (Shared Shell + Design Tokens)

**Purpose**: Centralized design token system, app shell, and theme infrastructure that ALL user stories depend on

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T005 Create design token definitions in `anvil/api/static/css/tokens.css` with dual-mode color tokens (dark/light), type tokens (display/body/mono), spacing scale (--space-1 through --space-12), motion tokens (--ease, --dur-fast, --dur-slow), radius, and prefers-color-scheme OS detection. Reference: `contracts/design-tokens.md`
- [x] T006 [P] Create base styles in `anvil/api/static/css/base.css` — CSS reset, html/body base styles using token variables, shell layout (app-header, nav, page frame, status bar)
- [x] T007 [P] Create core.js in `anvil/api/static/js/core.js` — shell initialization, theme toggle (data-theme attribute + localStorage + prefers-color-scheme), nav highlighting, cross-page state store (URL params + sessionStorage). Reference: `data-model.md` (AppShell entity). **Before tokens.css loads**, include an inline `<script>` in base.html `<head>` that reads localStorage theme and sets data-theme immediately — prevents flash-of-wrong-theme (FOUC).
- [x] T008 Refactor `anvil/api/templates/base.html` — replace terminal theme markup with new token-driven design, integrate core.js, add theme-toggle button, restructure nav to follow learning arc order. Remove block-art titlebar system, remove ANSI toggle. Retain mono type for code/tensor rendering.
- [x] T009 [P] Create utility classes in `anvil/api/static/css/utilities.css` — spacing helpers, typography helpers, reduced-motion override (`@media (prefers-reduced-motion)`)
- [x] T010 [P] Create code rendering styles in `anvil/api/static/css/code.css` — mono type for code blocks, tensor values, loss numbers. Carried over from existing terminal theme but retokened

**Checkpoint**: Foundation ready — app shell renders with new design, theme toggle works, nav reflects learning arc. No user story content yet.

---

## Phase 3: User Story 1 — Live Training Dashboard (Priority: P1) 🎯 MVP

**Goal**: Real-time training dashboard with SSE streaming, 6-state connection lifecycle, canvas-based loss chart, start/stop controls

**Independent Test**: Start a training run, observe live loss curve building on canvas, verify all 6 connection states render distinctly, stop the run, verify final curve preserved

### Implementation for User Story 1

- [x] T011 [P] [US1] Create SSE connection manager in `anvil/api/static/js/sse.js` — SSESession class with 6-state lifecycle (idle → connecting → streaming → done → errored → reconnecting), capped exponential backoff (5 retries: 1s, 2s, 4s, 8s, 16s), EventSource cleanup on destroy. Reference: `contracts/sse-lifecycle.md`, `data-model.md` (ConnectionState machine)
- [x] T012 [P] [US1] Create canvas-based loss chart in `anvil/api/static/js/chart.js` — LossChart class with live mode (append-only, throttled at 50ms) and replay mode (full data render), LTTB downsampling at 2000 max points, canvas 2D rendering with token-driven colors. Reference: `contracts/chart-primitive.md`, `data-model.md` (DataPoint entity)
- [x] T013 [P] [US1] Create archetype B template at `anvil/api/templates/archetypes/training.html` — hyperparameter inputs (n_embd, n_layer, n_head, num_steps, lr, temp), start/stop controls, canvas element for chart, connection state indicator, step/loss/throughput display. Extends refactored base.html
- [x] T014 [P] [US1] Create streaming chart partial at `anvil/api/templates/partials/streaming-chart.html` — reusable canvas element with chart controls, shared by live training and replay modes
- [x] T015 [US1] Create live training CSS in `anvil/api/static/css/archetypes.css` — layout for training dashboard: config panel, chart area, metrics display, connection states. Reference token colors for each connection state
- [x] T016 [US1] Wire SSE + chart + template in archetypes/training.html — integrate sse.js and chart.js, connect start button → POST /v1/training/start → EventSource stream → LossChart.appendPoint → state transitions. Add stop/resume/retry controls
- [x] T017 [US1] Update route for training page in `anvil/api/v1/router.py` — point existing `/v1/` and `/v1/training-page` routes to the new archetype/training.html template
- [x] T018 [US1] Add loading indicator for chart area and "Scroll to begin" state for initial page load (empty/loading state per clarifications)

**Checkpoint**: Live training dashboard works — start training sees live loss curve, all 6 states render, stop/retry works, DOM stays responsive at 10k steps

---

## Phase 4: User Story 2 — Scroll-Driven Concept Explorer (Priority: P1)

**Goal**: Interactive scroll-driven concept pages with pinned visualization, narrative steps, and manipulable widgets. Attention page first (centerpiece), then remaining concepts.

**Independent Test**: Navigate to any concept page, scroll through steps, confirm pinned visualization updates at each step. Interact with widgets (type text, adjust sliders) and verify response.

### Implementation for User Story 2 (Part A: ScrollScene Primitive + Attention Page)

- [x] T019 [P] [US2] Create ScrollScene manager in `anvil/api/static/js/scroll-scene.js` — ScrollScene class with IntersectionObserver per step, onstepchange callback, render-prop pattern for pinned visual, destroy() cleanup. Reference: `contracts/scroll-scene.md`, `data-model.md` (ScrollScene, Step entities)
- [x] T020 [P] [US2] Create archetype A template at `anvil/api/templates/archetypes/concept.html` — ScrollScene layout with sticky pinned visual pane (left/right) + narrative column with ordered steps. Extends refactored base.html
- [x] T021 [P] [US2] Create ScrollScene partial at `anvil/api/templates/partials/scroll-scene.html` — reusable pinned-visual + steps container with data-step-key attributes
- [x] T022 [P] [US2] Create attention widget JS in `anvil/api/static/js/widgets/attention.js` — heatmap rendering (canvas), hover to highlight token attention patterns, keyboard navigation (tab through tokens, Enter to select)
- [x] T023 [P] [US2] Create attention widget partial at `anvil/api/templates/partials/concept-widgets/attention.html` — canvas element + token labels for the attention heatmap
- [x] T024 [US2] Create attention concept page: `anvil/api/templates/partials/concept-widgets/attention.html` integrated into a full ScrollScene with narrative steps (what is attention, query/key/value, multi-head, attended tokens). Allocate largest layout per FR-008 — attention page pinned visual pane occupies >50% of ScrollScene width, larger than any other concept page.
- [x] T025 [US2] Create concept archetype CSS additions in `anvil/api/static/css/archetypes.css` — ScrollScene layout (sticky pinned visual, scrolling narrative column), mobile collapse at 768px, reduced-motion instant transitions
- [x] T026 [US2] Add route for attention concept page in `anvil/api/v1/router.py` — GET /learn/attention → concept.html with attention widget context

### Implementation for User Story 2 (Part B: Remaining Concept Widgets)

- [x] T027 [P] [US2] Create tokenization widget JS in `anvil/api/static/js/widgets/tokenization.js` — text input → live token/ID split display (tokens in --font-mono), keyboard-operable
- [x] T028 [P] [US2] Create tokenization widget partial at `anvil/api/templates/partials/concept-widgets/tokenization.html`
- [x] T029 [P] [US2] Create embedding widget JS in `anvil/api/static/js/widgets/embedding.js` — 2D projection with rotate/zoom (tensor values in --font-mono), keyboard arrow-key rotation
- [x] T030 [P] [US2] Create embedding widget partial at `anvil/api/templates/partials/concept-widgets/embedding.html`
- [x] T031 [P] [US2] Create sampling widget JS in `anvil/api/static/js/widgets/sampling.js` — temperature/top-k sliders → re-rolled probability distribution (distribution labels in --font-mono), keyboard arrow-key on sliders
- [x] T032 [P] [US2] Create sampling widget partial at `anvil/api/templates/partials/concept-widgets/sampling.html`
- [x] T033 [US2] Create remaining concept pages — tokenization, embeddings, forward pass, sampling, training loop, payoff — each as a ScrollScene with narrative steps + embedded widget. Add routes in `anvil/api/v1/router.py`
- [x] T034 [US2] Add concept widgets CSS in `anvil/api/static/css/components.css` — widget container styles, slider styles, heatmap styles, keyboard focus indicators. All displayed tensor values, token IDs, and loss numbers must use `--font-mono` from tokens.css (FR-019).

**Checkpoint**: All concept pages render with ScrollScene, widgets respond to manipulation, mobile collapses inline, keyboard navigation works

---

## Phase 5: User Story 3 — Experiment History & Replay (Priority: P2)

**Goal**: Run history list with status indicators, run detail page with replayed loss curve (same chart component as live, replay mode). Runs addressable via URL.

**Independent Test**: Complete a training run, navigate to experiment list, select the run, confirm full final loss curve renders immediately using the same chart visual style as live training

### Implementation for User Story 3

- [x] T035 [P] [US3] Create archetype C template at `anvil/api/templates/archetypes/experiment.html` — runs list table with status badges (completed, failed, in-progress), selected run detail with metrics and replayed chart. Extends refactored base.html
- [x] T036 [P] [US3] Create experiment list CSS in `anvil/api/static/css/archetypes.css` — table layout, status badge colors (using token colors), run detail layout
- [x] T037 [US3] Integrate LossChart replay mode into experiment archetype — on run selection, fetch stored metrics via existing API, call chart.setData(metrics) for full immediate render (no animation per clarification). Same chart.js component used for live mode
- [x] T038 [US3] Wire URL state for run selection — read `?run_id=X` from URLSearchParams on page load, select that run automatically (shareable URL per SC-005). Update URL on run selection
- [x] T039 [US3] Add empty state for experiment list — "No runs yet — train your first model" with CTA linking to training page
- [x] T040 [US3] Add loading indicator for run detail metrics fetch — "Loading metrics…" in chart area while data loads
- [x] T041 [US3] Update route for experiments page in `anvil/api/v1/router.py` — point existing `/v1/experiments-page` route to the new archetype/experiment.html template

**Checkpoint**: Experiment list shows completed runs, selecting a run shows full loss curve immediately, shareable URL restores run context on direct load, empty and loading states render correctly

---

## Phase 6: User Story 4 — Computation Graph Exploration (Priority: P2)

**Goal**: Interactive computation graph view sourced from real autograd engine data. Scrub through forward-pass steps to see graph assemble. Degrade gracefully for large graphs.

**Test**: Load the graph view, scrub forward-pass steps, confirm ops add in correct order with real labels

### Implementation for User Story 4

- [x] T042 [P] [US4] Create computation graph renderer in `anvil/api/static/js/graph-view.js` — canvas DAG rendering with topological sort + layered layout, node rendering with real op labels and tensor values in --font-mono, forward-pass scrubbing control. Reference: `research.md` section 8
- [x] T043 [P] [US4] Create graph view partial at `anvil/api/templates/partials/graph-view.html` — canvas element + scrubber slider + step counter
- [x] T044 [P] [US4] Create graph view CSS in `anvil/api/static/css/components.css` — graph canvas layout, scrubber control styling, level-of-detail controls
- [x] T045 [P] [US4] Add lightweight computation graph API endpoint in `anvil/api/v1/training.py` — GET /v1/forward-pass/graph returning autograd value graph structure: `{nodes: [{id, op_type, tensor_value, label, parents: [parent_id]}], edges: [{from, to}]}`. Reference: clarification Q4, `data-model.md` (TrainingRun entity)
- [x] T046 [US4] Create computation graph page integrating graph-view.js into a ScrollScene or standalone page — narrative explains forward pass, scrubber drives graph assembly. Add route in `anvil/api/v1/router.py`
- [x] T047 [US4] Implement level-of-detail for large graphs — at configurable node count threshold, project to higher-level view (merge subgraphs, show only top-level ops). Graceful degradation per FR-014

**Checkpoint**: Graph view loads real engine data, forward-pass scrubbing works, large graphs degrade gracefully without freezing

---

## Phase 7: User Story 5 — Theme, Navigation & Cross-Page State (Priority: P3)

**Goal**: Light/dark mode toggle persists across navigation, active-run identity and model config survive page changes, shareable URLs encode run context

**Test**: Toggle dark mode → navigate to different page → reload → dark mode persists. Load URL with `?run_id=42&temp=0.8` → page shows that run's context

### Implementation for User Story 5

- [x] T048 [US5] Wire cross-page state store in `anvil/api/static/js/core.js` — on navigation, serialize active-run identity and model config to URLSearchParams. On page load, deserialize from URL params and restore state. Reference: `data-model.md` (state transitions, URL encoding)
- [x] T049 [P] [US5] Persist theme preference in localStorage in `core.js` — default follows OS (prefers-color-scheme), manual toggle saves to localStorage, applies data-theme attribute. Already partially implemented in existing base.html — migrate to core.js
- [x] T050 [US5] Add prefers-color-scheme OS detection in `tokens.css` — `@media (prefers-color-scheme: dark)` on `:root:not([data-theme])` so default follows OS before any manual toggle. Reference: `contracts/design-tokens.md`
- [x] T051 [P] [US5] Code cleanup — remove all remaining ANSI terminal theme artifacts from: `anvil/api/static/style.css` (legacy CSS to be deleted), inline JS in existing templates (once extracted to new modules), block-art titlebar JS in base.html
- [x] T052 [US5] Add playground archetype (Archetype D) at `anvil/api/templates/archetypes/playground.html` — widget composition page that composes existing concept widgets without scroll narrative. Route: `/v1/inference-page`

**Checkpoint**: Theme persists cross-page and cross-session, shareable URLs restore context, ANSI theme fully removed, playground page composes widgets

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Accessibility audit, reduced-motion verification, mobile collapse verification, performance validation, legacy cleanup

- [x] T053 [P] Accessibility audit — verify all interactive widgets: keyboard-operable (tab stops, Enter/Space activation, arrow key controls), visible focus indicators, WCAG AA contrast in both modes. Fix any failures
- [x] T054 [P] Reduced-motion audit — verify prefers-reduced-motion honored everywhere: CSS transitions disabled, no motion-only affordances, ScrollScene state changes still occur instantly. Fix any failures
- [x] T055 [P] Mobile responsiveness audit — verify all sticky/pinned layouts collapse inline at 768px, all pages render without horizontal scroll on mobile widths. Fix any failures
- [x] T056 [P] Performance audit — verify chart downsampling at 10k steps (no unbounded DOM growth), SSE EventSource cleanup on navigation, IntersectionObserver disconnect on unmount, no orphan connections. Fix any failures
- [x] T057 Delete legacy `anvil/api/static/style.css` — all styles migrated to new modular CSS files, legacy file no longer imported in base.html
- [x] T058 Update `anvil/api/v1/router.py` — ensure ALL existing route paths map to their appropriate archetype: `/v1/`, `/v1/training-page` → archetypes/training.html; `/v1/experiments-page` → archetypes/experiment.html; `/v1/inference-page` → archetypes/playground.html; `/v1/datasets-page` → archetypes/training.html (retrofit content); `/v1/operations-page` → archetypes/training.html (retrofit content); `/v1/models-page`, `/v1/model-detail/{id}` → archetypes/experiment.html (retrofit content); `/learn/*` → archetypes/concept.html. Redirect or 410 any routes that have no equivalent.
- [x] T059 Verify quickstart.md validation — run through quickstart instructions end-to-end, verify all steps work

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS all user stories (ALL stories need the shell + tokens)
- **US1 (Phase 3)**: Depends on Foundational — can proceed independently
- **US2 (Phase 4)**: Depends on Foundational — can proceed independently of US1
- **US3 (Phase 5)**: Depends on Foundational + US1 (reuses LossChart from US1)
- **US4 (Phase 6)**: Depends on Foundational — can proceed in parallel with others, needs new backend endpoint
- **US5 (Phase 7)**: Depends on Foundational — can proceed in parallel, integrates after other stories
- **Polish (Phase 8)**: Depends on all desired stories being deployed

### User Story Dependencies

- **US1 (P1)**: Blocks US3 (US3 reuses LossChart component)
- **US2 (P1)**: No dependencies on other stories
- **US3 (P2)**: Depends on US1 (LossChart component for replay mode)
- **US4 (P2)**: No dependencies on other stories (but needs new backend endpoint T045)
- **US5 (P3)**: No dependencies on other stories — can be done in parallel

### Parallel Opportunities

- All setup tasks T001-T004 can run in parallel
- All foundational tasks T005-T010 that are marked [P] can run in parallel
- Once Foundational completes, US1 and US2 can start in parallel (both P1)
- Within US2, widget tasks T027-T032 can all run in parallel
- US4 and US5 can run in parallel with US2/US3 once foundational is done
- All Polish tasks T053-T058 marked [P] can run in parallel

---

## Parallel Example: User Story 1

```bash
# Launch SSE manager and chart JS simultaneously:
Task: "Create SSESession in microgpt/api/static/js/sse.js"
Task: "Create LossChart in microgpt/api/static/js/chart.js"

# After both complete, wire them together:
Task: "Wire SSE + chart + template in archetypes/training.html"
```

## Parallel Example: User Story 2

```bash
# Launch ScrollScene + all widgets simultaneously:
Task: "Create ScrollScene in microgpt/api/static/js/scroll-scene.js"
Task: "Create attention widget in microgpt/api/static/js/widgets/attention.js"
Task: "Create tokenization widget in microgpt/api/static/js/widgets/tokenization.js"
Task: "Create sampling widget in microgpt/api/static/js/widgets/sampling.js"
Task: "Create embedding widget in microgpt/api/static/js/widgets/embedding.js"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (directory structure)
2. Complete Phase 2: Foundational (shell + tokens — blocks ALL stories)
3. Complete Phase 3: User Story 1 (live training dashboard)
4. **STOP and VALIDATE**: Train a model, watch live loss curve, test all 6 connection states
5. Deploy/demo if ready

### Incremental Delivery

1. Phase 1+2 → Foundation ready: new shell with tokens, theme toggle works
2. Add US1 (Live training) → **MVP**: real-time training dashboard with canvas chart
3. Add US2 (Concept explorer) → **Enhanced**: scroll-driven learning pages
4. Add US3 (Experiment history) → **Complete**: full training workflow with replay
5. Add US4 (Computation graph) → **Differentiated**: real engine graph visualization
6. Add US5 (Cross-page state) → **Polished**: shareable URLs, persistent theme
7. Polish → **Production ready**: a11y, perf, mobile, cleanup

### Parallel Team Strategy

1. Team completes Setup + Foundational together (Phase 1 + 2)
2. Once Foundational is done:
   - Developer A: US1 (Live training — highest priority, blocks US3)
   - Developer B: US2 Part A (ScrollScene + attention — parallel to US1)
   - Developer C: US2 Part B (remaining widgets — parallel after ScrollScene)
3. After US1 done:
   - Developer A: US3 (Experiment replay — depends on LossChart from US1)
   - Developer B: US4 (Computation graph — independent)
   - Developer C: US5 (Cross-page state — independent)
4. All stories verified independently before integration

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- All existing 9 routes must still work after refactor — routes point to new archetype templates
- Legacy `style.css` (1276 lines) is deleted only after all migrations verified (Phase 8)
- No JS test framework exists — all verification is manual via browser inspection
- Commit after each phase checkpoint for clean rollback points