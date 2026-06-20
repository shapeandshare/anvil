---
description: "Task list for Theme Engine (Behavioral Themes)"
---

# Tasks: Theme Engine (Behavioral Themes)

**Input**: Design documents from `/specs/015-theme-engine/`
**Prerequisites**: plan.md ✓, spec.md ✓, research.md ✓, data-model.md ✓, contracts/ ✓ (theme-registry.md, signal-stream.md, theme-tokens.md), quickstart.md ✓

**Tests**: Constitution Article IV mandates TDD. Backend signal-instrumentation tasks have **pytest tests written first** (Red→Green). The frontend is vanilla JS with **no test runner in the repo**, so JS/visual/a11y acceptance is verified via the manual checks in `quickstart.md` (referenced per task).

**Organization**: Tasks are grouped by user story (US1–US4) to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: US1, US2, US3, US4 (maps to spec.md user stories)

## Path Conventions

Web application (existing layout). Backend: `anvil/...`. Frontend static: `anvil/api/static/...`. Templates: `anvil/api/templates/...`. Tests: `tests/...`. All paths absolute from repo root.

**Launch theme set (FR-028)**: `default` (dual-mode, unchanged), `forge` (dark), `oldgrowth` (single-mode CRT), `aurora` (new, dual-mode behavioral — chosen as the ≥1 additional theme and as the dual-mode behavioral exemplar for FR-023).

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create the data-only directories and scaffolding the engine needs. Per Article VI these static dirs get NO `__init__.py`.

- [X] T001 Create data-only static directories `anvil/api/static/js/theme/`, `anvil/api/static/js/themes/`, and `anvil/api/static/css/themes/` (no `__init__.py` — not Python packages, per Constitution Article VI)
- [X] T002 [P] Create ADR stub `docs/vault/Decisions/ADR-024-behavioral-theme-engine.md` capturing the neutral-signal + theme-owns-mapping architecture (from research.md R1–R8), with required frontmatter (title, type, tags from `docs/vault/_meta/tags.md`, created, updated) and status `draft`
- [X] T003 [P] Create empty pytest module skeletons `tests/services/training/test_step_metrics.py` and `tests/api/test_training_sse_signals.py` with module docstrings (NumPy style) and a `pytest` import, so later TDD tasks fill them

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The theme engine core every user story depends on: registry, manager, signal bus, effect-level skeleton, FOUC guard, default theme. **No user story can begin until this phase completes.**

**⚠️ CRITICAL**: US1–US4 all build on these.

- [X] T004 [P] Implement `ThemeRegistry` (register/get/list/has/`defaultId`) in `anvil/api/static/js/theme/theme-registry.js` per contracts/theme-registry.md (idempotent register by id; `default` always present; unknown id → defaultId)
- [X] T005 [P] Implement `EffectLevelState` resolver skeleton in `anvil/api/static/js/theme/effect-level.js` exposing `{reducedMotion, reducedEffects, reducedTransparency, audioOptIn, visible}` and a `level()` returning Full/Muted/Legible/Paused (data-model.md EffectLevelState); full behavior wired in US3
- [X] T006 [P] Implement `signal-bus.js` skeleton in `anvil/api/static/js/theme/signal-bus.js`: `on(eventName, cb)→unsub`, subscribes to a provided `SSESession`, re-publishes neutral signals; no theme coupling (R6). Event wiring for `divergence` completed in US2
- [X] T007 Implement `ThemeManager` (`init/apply/current/reset`) in `anvil/api/static/js/theme/theme-manager.js` per contracts/theme-registry.md lifecycle: resolve id (fallback default), teardown prior mapping, set `data-theme`/`data-mode`, swap CSS-layer `<link>`, persist+migrate `localStorage['theme']` (legacy `'dark'|'light'` → `{themeId:'default',mode}`), bind mapping to bus when signals present (depends on T004, T005, T006)
- [X] T008 Extend `anvil/api/templates/base.html`: (a) replace the inline `<head>` FOUC script to read `{themeId,mode}` (with legacy-string migration), set `data-theme`/`data-mode`, and inject the active theme's CSS-layer `<link>` before first paint; (b) add a theme-CSS-layer `<link>` slot; (c) add `<script>` includes for `theme/*.js` then `themes/*.js`; (d) add a picker mount point in the nav bar (outside `<main>` so it survives client-side nav)
- [X] T009 Rewire `anvil/api/static/js/core.js` to initialize via `ThemeManager.init()` and delegate the existing light/dark toggle to the manager (preserve `updateThemeUI` sun/moon for the default theme) (depends on T007)
- [X] T010 [P] Create default theme module `anvil/api/static/js/themes/default.js` registering `{id:'default', displayName:'Default', previewHint:'Clean iOS-modern', modes:['light','dark'], cssLayer:null, mapping:null}` (cosmetic; uses base tokens.css) (depends on T004)
- [X] T011 [P] Update `anvil/api/static/css/tokens.css`: keep `:root` dark default + `[data-theme="light"]` exactly as today; add documentation comment block describing the theme-layer override contract (theme-tokens.md) — no behavioral change to default
- [X] T011a Add cross-tab reconciliation in `anvil/api/static/js/theme/theme-manager.js`: listen for the `localStorage` `storage` event (key `theme`) and, on focus/next navigation, re-apply the new `{themeId, mode}` so other open tabs reflect a theme change; MUST NOT desync or break if the value is unknown/legacy (falls back per T007/T022) (spec Edge Case "Theme changed in another browser tab/window") (depends on T007)

**Checkpoint**: Engine core exists; default theme works exactly as before; nothing user-visible changed yet.

---

## Phase 3: User Story 1 - Choose a behavioral theme (Priority: P1) 🎯 MVP

**Goal**: A discoverable picker lets users select among ≥4 named themes; selection applies app-wide without reload, persists across reload with no flash, and can be reset to default. (At this phase themes are cosmetic identities; live expression arrives in US2.)

**Independent Test**: From any page, open the picker, switch between Default/Forge/Old Growth/Aurora, navigate + reload — selection persists, no FOUC; reset returns to default; an unknown saved id falls back to default. (quickstart.md §1, steps 1–3, 9.)

### Implementation for User Story 1

- [X] T012 [P] [US1] Create theme picker partial `anvil/api/templates/components/theme_picker.html` listing registry themes with `displayName` + `previewHint` and a current-selection indicator (FR-001)
- [X] T013 [US1] Mount the picker into the nav bar in `anvil/api/templates/base.html` at the T008 mount point; ensure it renders on every page (depends on T012, T008)
- [X] T014 [US1] Implement picker interactions in `anvil/api/static/js/theme/theme-manager.js` (+ wire-up in `core.js`): select theme → `apply()`; "Default"/reset action from any page (FR-007); render light/dark control state, disabling/labeling it for single-mode themes (FR-023 display only) (depends on T007, T013)
- [X] T015 [P] [US1] Create `anvil/api/static/css/themes/forge.css` cosmetic layer: `[data-theme="forge"]` warm palette/ember accents/type overrides + theme-private vars `--heat`,`--prog` declared (no JS yet) per theme-tokens.md
- [X] T016 [P] [US1] Create `anvil/api/static/css/themes/oldgrowth.css` cosmetic layer: `[data-theme="oldgrowth"]` single-mode phosphor-green palette + theme-private `--disturbance` declared per theme-tokens.md
- [X] T017 [P] [US1] Create `anvil/api/static/css/themes/aurora.css` cosmetic layer: `[data-theme="aurora"]` dual-mode palette (`[data-theme="aurora"][data-mode="light"]` variant) + `--flow`,`--calm` declared per theme-tokens.md (dual-mode exemplar for FR-023)
- [X] T018 [P] [US1] Create `anvil/api/static/js/themes/forge.js` registering `{id:'forge', displayName:'Forge', previewHint:'Loss as cooling metal', modes:['dark'], cssLayer:'/static/css/themes/forge.css', mapping:null}`
- [X] T019 [P] [US1] Create `anvil/api/static/js/themes/oldgrowth.js` registering `{id:'oldgrowth', displayName:'Old Growth', previewHint:'Signal degrades with instability', modes:['single'], cssLayer:'/static/css/themes/oldgrowth.css', mapping:null}`
- [X] T020 [P] [US1] Create `anvil/api/static/js/themes/aurora.js` registering `{id:'aurora', displayName:'Aurora', previewHint:'Loss as northern lights', modes:['light','dark'], cssLayer:'/static/css/themes/aurora.css', mapping:null}`
- [X] T021 [US1] Verify persistence + legacy migration + no-FOUC across reload and client-side nav per quickstart.md §1 (manual); confirm picker survives `<main>` swaps (FR-004, FR-006, SC-010)
- [X] T022 [US1] Confirm unknown/removed saved theme id falls back to default and rewrites preference in `theme-manager.js` (FR-024, SC-008)

**Checkpoint**: MVP — users can pick among 4 themes, persisted, no flash, reset works. Themes are cosmetic; no live expression yet.

---

## Phase 4: User Story 2 - Themes express live application state (Priority: P1)

**Goal**: Widen the backend to emit neutral signals (`grad_norm`, `tokens_per_sec`, a `divergence` event), pipe them through a single signal bus, and give Forge/Old Growth/Aurora their signal→expression mappings (FR-027). The backend stays theme-agnostic; themes own their mapping.

**Independent Test**: Start a run with Forge → loss cools the curve + sample resolves from noise + throughput drives core/sparks; trigger NaN → sample shatters + alarm. Switch to Old Growth mid-run → disturbance (instability) drives CRT effects, no connection drop. Backend pytest contract tests pass. (quickstart.md §1 steps 4–6, §3.)

### Tests for User Story 2 (TDD — write FIRST, ensure they FAIL) ⚠️

- [X] T023 [P] [US2] Write failing unit tests in `tests/services/training/test_step_metrics.py`: `StepMetrics` validates types/nullable `grad_norm`/`tokens_per_sec`; **`tokens_per_sec` is derived from a rolling sum of per-step `tokens` ÷ window-elapsed** (NOT `batch_size × context_len`; assert correctness for variable per-step `tokens` and `null` when no rate yet); divergence detection returns the correct `DivergenceReason` for `nan`/`inf`; **a diverged run's persisted status is reconciled to a terminal `diverged`/`failed` state** (FR-030, via the service/repository path) (contracts/signal-stream.md test list)
- [X] T024 [P] [US2] Write failing contract tests in `tests/api/test_training_sse_signals.py`: `metrics` SSE payload includes `grad_norm` + `tokens_per_sec` and retains existing keys (back-compat); `loss=NaN` emits `event: divergence` `{reason:'loss_nan'}`, **halts the run (no further `metrics`)**, and NO subsequent `complete`; the stream **breaks on `divergence`** (route break tuple); a `milestone` cadence marker `{step}` is emitted at the configured interval; stdlib-engine run emits `grad_norm: null` without error (contracts/signal-stream.md)

### Implementation for User Story 2

- [X] T025 [P] [US2] Create stdlib `CoreStepObservation` NamedTuple `{step:int, loss:float, tokens:int, grad_norm:float|None}` in `anvil/core/step_observation.py` — `tokens` is the actual token count processed at this step (`n = min(block_size, len(tokens)-1)`); REQUIRED because the engines are unbatched/variable-length (`core/torch_engine.py:474`, `core/engine.py:406`) and there is NO `batch_size` (zero third-party deps — Article I; one-class-per-file)
- [X] T026 [P] [US2] Create `DivergenceReason` StrEnum (`LOSS_NAN`/`LOSS_INF`/`GRAD_EXPLOSION`) in `anvil/services/training/divergence_reason.py`, and a `DivergenceError(Exception)` in `anvil/services/training/divergence_error.py` (mirrors the existing `StopRequested` raise-to-halt pattern at `training.py:280-281`) (enums-over-magic-strings; one-class-per-file)
- [X] T027 [US2] Create `StepMetrics` Pydantic `BaseModel` in `anvil/services/training/step_metrics.py` with fields per contracts/signal-stream.md (`grad_norm`,`tokens_per_sec` `float|None`); strict typing; forbid theme-specific extras (depends on T025)
- [X] T028 [US2] In `anvil/core/torch_engine.py`: (a) compute global `grad_norm = sqrt(Σ p.grad.norm()²)` over `model.parameters()` AFTER `loss.backward()` (`:493`) and before the next iteration's `optim.zero_grad()` — no clipping exists so there is a single norm; per-step sampling is fine because `loss.item()` (`:497`) already forces a device sync every step; (b) pass `CoreStepObservation(step, loss_val, tokens=n, grad_norm=...)` to the progress callback at `:500-501` (depends on T025)
- [X] T029 [US2] Update pure engine `anvil/core/engine.py` (`:430-431`) to emit `CoreStepObservation(step, loss.data, tokens=n, grad_norm=None)` (optional well-commented stdlib norm loop per research.md R2; default `None`) (depends on T025)
- [X] T030 [US2] Widen `ProgressCallback` type in `anvil/services/compute/protocol.py` (currently `Callable[[int, float], None]`) to `Callable[[CoreStepObservation], None]` (typed, mypy --strict, no suppression) (depends on T025)
- [X] T031 [P] [US2] Thread `CoreStepObservation` through `anvil/services/compute/local_torch_backend.py` (depends on T030)
- [X] T032 [P] [US2] Thread `CoreStepObservation` through `anvil/services/compute/local_stdlib_backend.py` (depends on T030)
- [X] T033 [US2] In `anvil/services/training/training.py` progress closure (`:278-322`): build `StepMetrics`; derive **exact** `tokens_per_sec` from a rolling sum of `obs.tokens` ÷ window-elapsed (NOT `batch_size × context_len` — no `batch_size` exists and tokens/step is variable); on `math.isnan(loss) or math.isinf(loss)` enqueue a `divergence` event `{step, reason}` and **raise `DivergenceError`** to halt the run (mirrors `StopRequested` at `:280-281`, since the engines do NOT break on NaN themselves); and enqueue a neutral `milestone` cadence marker `{step}` every N steps (configurable interval; no artifact write — R5) (R3, R4, R5) (depends on T026, T027, T030, T031, T032)
- [X] T034 [US2] In `anvil/api/v1/training.py`: (a) add an `except DivergenceError` block in the run path that emits the `divergence` event and does NOT emit `complete` (parallel to the `StopRequested`→`error` handling); (b) **add `"divergence"` to the stream break tuple at `:614`** (`if msg["event"] in ("complete","error","divergence"): break`); (c) emit the widened `metrics` payload and the neutral `milestone` marker (depends on T033)
- [X] T034a [US2] In `anvil/services/training/training.py` / God-Class path: on `DivergenceError`, reconcile the persisted run status to a terminal `diverged`/`failed` state via the service (Article VII — through the repository, not the route), so DB state is not left dangling (parallels how `on_complete` finalizes the success path at `:383`); covered by the status-persistence assertion in T023 (FR-025, FR-030, SC-012; depends on T026, T033)
- [X] T035 [US2] Add `ondivergence` AND `onmilestone` named-event handlers to `anvil/api/static/js/sse.js` (`addEventListener('divergence'|'milestone', …)`), mirroring the existing `onmetrics`/`oncomplete` pattern; tolerate null `grad_norm`/`tokens_per_sec`
- [X] T036 [US2] Complete `anvil/api/static/js/theme/signal-bus.js`: publish `metrics`/`divergence`/`milestone`/`complete` from the single `SSESession` to the active theme mapping; expose neutral signal names only (depends on T006, T035)
- [X] T037 [US2] Implement `mapping()` in `anvil/api/static/js/themes/forge.js` + effects in `anvil/api/static/css/themes/forge.css`: `loss`→cooling-metal curve color + sample resolve-from-noise via `--prog`; `tokens_per_sec`→`--heat` forge-core glow + spark canvas; `complete`/`milestone`→quench flash; `divergence`→shatter sample to noise + alarm color. MUST define a coherent **idle/at-rest** state when no run is active (FR-013) and **clamp/normalize** missing/null/out-of-range signal values rather than render nonsense (FR-025) (FR-027) (depends on T036)
- [X] T038 [US2] Implement `mapping()` in `anvil/api/static/js/themes/oldgrowth.js` + effects in `anvil/api/static/css/themes/oldgrowth.css`: client-derive `--disturbance` from normalized `grad_norm` + rolling loss-volatility (works when `grad_norm` null), driving scanline flicker + chromatic aberration + glyph corruption + inverse signal-lock meter; `divergence`→`--disturbance=1`. MUST define a calm **idle/at-rest** state when no run is active (FR-013) and **clamp** disturbance to [0,1] for missing/out-of-range inputs (FR-025) (FR-027, R6) (depends on T036)
- [X] T039 [US2] Implement a distinct `mapping()` in `anvil/api/static/js/themes/aurora.js` + effects in `anvil/api/static/css/themes/aurora.css`: `loss`→`--calm`, `tokens_per_sec`→`--flow`, `divergence`→calm=0 — must differ in behavior/feel from Forge/Old Growth (FR-008, FR-028). MUST define an **idle/at-rest** state (FR-013) and **clamp** out-of-range/missing values (FR-025) (depends on T036)
- [X] T040 [US2] Verify mid-run theme switch in `theme-manager.js` tears down the old mapping and rebinds the new one to the existing bus WITHOUT closing the `EventSource` (FR-026) (depends on T007, T037, T038, T039)
- [X] T041 [US2] Make T023/T024 pass; run `make test`, `make typecheck`, `make lint`; confirm coverage `fail_under` not lowered (Article IV)

**Checkpoint**: Live training drives each expressive theme's distinct visual language; backend emits only neutral signals; tests green.

---

## Phase 5: User Story 3 - Expressive themes never block the work (accessibility & opt-out) (Priority: P2)

**Goal**: Centralized effect-level gating so every theme honors reduced-motion, a max-legibility/reduced-effects toggle, audio opt-in (off by default), and visibility throttling — preserving legibility and the default experience.

**Independent Test**: Enable OS reduce-motion → no continuous animation in any theme, content legible; enable max-legibility → glyph corruption/overlays suppressed; hide tab → continuous effects pause; audio stays off until opted in. (quickstart.md §1 step 8.)

### Implementation for User Story 3

- [X] T042 [US3] Complete `anvil/api/static/js/theme/effect-level.js`: live `matchMedia` listeners for `prefers-reduced-motion` + `prefers-reduced-transparency`, in-app reduced-effects + audio-opt-in state, and `visibilitychange`; emit changes so active mapping re-evaluates at runtime (FR-017, FR-020, FR-021) (depends on T005)
- [X] T043 [P] [US3] Add `@media (prefers-reduced-motion: reduce)` reset scoped to `[data-theme="forge"]` in `anvil/api/static/css/themes/forge.css` (FR-017, SC-005)
- [X] T044 [P] [US3] Add `@media (prefers-reduced-motion: reduce)` reset scoped to `[data-theme="oldgrowth"]` in `anvil/api/static/css/themes/oldgrowth.css` (FR-017, SC-005)
- [X] T045 [P] [US3] Add `@media (prefers-reduced-motion: reduce)` reset scoped to `[data-theme="aurora"]` in `anvil/api/static/css/themes/aurora.css` (FR-017, SC-005)
- [X] T046 [US3] Add in-app "Maximum legibility / reduce effects" toggle and "Enable theme audio" opt-in (default off) to the picker partial `anvil/api/templates/components/theme_picker.html` + wire to `effect-level.js` (FR-018, FR-020)
- [X] T047 [US3] Gate legibility-degrading effects (Old Growth glyph corruption/overlays; Forge re-noise) behind `effectLevel.legible`/`reducedEffects` in `themes/forge.js`, `themes/oldgrowth.js`, `themes/aurora.js` (FR-018) (depends on T042, T037, T038, T039)
- [X] T048 [US3] Implement visibility throttle/pause of continuous canvas/rAF effects in each theme mapping using `effectLevel.visible` (FR-021); additionally degrade effect intensity (e.g. reduce particle/spark counts, lower update cadence) before allowing any perceptible loss of control interactivity on baseline hardware, so expressive effects never impair the underlying tool (FR-031) (depends on T042)
- [X] T049 [US3] WCAG AA contrast audit of primary text/controls for every theme × mode; fix token values failing AA in the `css/themes/*.css` layers (FR-016, SC-006)
- [ ] T050 [US3] Reduced-motion audit: confirm no continuous/looping animation runs under `prefers-reduced-motion` in any theme (SC-005)

**Checkpoint**: All themes are accessible and gracefully degrade; default-experience guarantee intact.

---

## Phase 6: User Story 4 - Light/dark continues to work within themes (Priority: P3)

**Goal**: Light/dark behavior preserved for default; dual-mode themes respect the choice; single-mode themes behave predictably and communicate their nature.

**Independent Test**: Toggle light/dark on Default (identical to today, persists). Toggle on Aurora (switches its light/dark variant). View Old Growth — light/dark control reflects single-mode without breaking. (quickstart.md, FR-022/023.)

### Implementation for User Story 4

- [X] T051 [US4] Implement light/dark `mode` handling in `anvil/api/static/js/theme/theme-manager.js`: persist `mode` in preference, set `data-mode`, and apply mode only for themes whose `modes` include it (depends on T007)
- [X] T052 [US4] Ensure Aurora dual-mode variants render correctly via `[data-theme="aurora"][data-mode="light"]` in `anvil/api/static/css/themes/aurora.css` (dual-mode behavioral exemplar, FR-023) (depends on T017, T051)
- [X] T053 [US4] Communicate single-mode for Old Growth in the light/dark control (disabled + explanatory label) in `theme_picker.html` + `theme-manager.js`; never render a broken state (FR-023) (depends on T014, T051)
- [X] T054 [US4] Verify Default light/dark parity is byte-for-byte unchanged from pre-feature behavior (SC-007, FR-022)

**Checkpoint**: Light/dark works within and across themes; single-mode handled gracefully.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Finalize docs, extensibility proof, and full gate run.

- [X] T055 [P] Finalize ADR `docs/vault/Decisions/ADR-024-behavioral-theme-engine.md` (status reviewed), add session log under `docs/vault/Sessions/`, ensure wikilinks resolve, run `make vault-audit` (0 errors)
- [X] T056 [P] Update `DESIGN.md` and `AGENTS.md` design-system notes to document the theme-layer override contract and `css/themes/` location
- [ ] T057 Run the quickstart.md §2 "add a theme end-to-end" proof to validate FR-015/SC-009 (a theme added with only new CSS+JS+`<script>` include, no engine edits)
- [ ] T058 Full gate run: `make lint`, `make typecheck` (strict), `make test` (coverage at `fail_under`); fix any failures
- [ ] T059 Execute the spec Success-Criteria QA matrix (SC-001…SC-012) across all 4 themes × modes per quickstart.md §4 done-criteria — including SC-011 (no input lag/stutter with the heaviest theme on the live dashboard; effects pause when hidden) and SC-012 (a non-finite-loss run stops and shows diverged/failed within one update cycle, every theme); record results in the session log
- [X] T060 Add an end-to-end system test under `tests/system/test_theme_engine.py` (run via `make test-system`) exercising the JS theme engine through the served app: select a non-default theme → assert `data-theme` applied app-wide + persisted across reload with no flash (SC-010), reset → default restored, and an unknown saved theme id falls back to default (FR-024, SC-008). Authored RED early in US1 per Article IV (closes the JS-coverage gap; the JS unit layer has no in-repo runner)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately.
- **Foundational (Phase 2)**: Depends on Setup — **BLOCKS all user stories**.
- **US1 (Phase 3)**: Depends on Foundational. MVP.
- **US2 (Phase 4)**: Depends on Foundational; reuses US1 theme modules (adds `mapping()`), but the backend signal slice (T023–T036) is independent of US1 and can proceed in parallel with US1 once Foundational is done.
- **US3 (Phase 5)**: Depends on Foundational + US2 mappings existing (gates them). 
- **US4 (Phase 6)**: Depends on Foundational (manager); light/dark logic largely independent of US2/US3.
- **Polish (Phase 7)**: After all targeted stories complete.

### User Story Dependencies

- **US1 (P1)**: Foundational only. Independently testable (cosmetic selection/persistence).
- **US2 (P1)**: Foundational. Backend slice independent of US1; theme `mapping()` tasks extend the US1 theme modules. Independently testable via live run + pytest.
- **US3 (P2)**: Builds on US2 mappings to gate them; effect-level skeleton is foundational.
- **US4 (P3)**: Foundational manager; independent of US2/US3.

### Within Each User Story

- US2 tests (T023, T024) MUST be written and FAIL before implementation (T025+).
- The e2e system test (T060) SHOULD be authored RED during US1 (before T014/T021) and turn green as US1 completes — it is the only automated coverage of the JS theme engine (Article IV).
- Models/value objects before services: `CoreStepObservation`/`StepMetrics` (T025–T027) before service closure (T033) before route emission (T034) before client consumption (T035–T039).
- CSS layer + registration (US1) before `mapping()` (US2) for the same theme.

### Parallel Opportunities

- Setup: T002, T003 in parallel.
- Foundational: T004, T005, T006 in parallel (T010, T011 also [P]); T007 after T004–T006; T008/T009 sequential on base/core.
- US1: CSS layers T015–T017 [P]; theme registrations T018–T020 [P]; picker partial T012 [P].
- US2: T023/T024 [P] (tests); T025/T026 [P]; backend threading T031/T032 [P]; theme mappings T037/T038/T039 touch separate files (parallelizable after T036).
- US3: reduced-motion resets T043/T044/T045 [P].
- **Cross-story**: once Foundational is done, the **US2 backend signal slice** (T023–T036) and **US1 picker/cosmetic themes** (T012–T022) can be built by separate developers in parallel.

---

## Parallel Example: User Story 2 (backend signal slice)

```bash
# Write failing tests together (TDD):
Task: "Unit tests for StepMetrics + divergence in tests/services/training/test_step_metrics.py"
Task: "Contract tests for widened metrics + divergence event in tests/api/test_training_sse_signals.py"

# Then value objects in parallel:
Task: "CoreStepObservation NamedTuple in anvil/core/step_observation.py"
Task: "DivergenceReason StrEnum in anvil/services/training/divergence_reason.py"

# Backend threading in parallel after protocol widening:
Task: "Thread CoreStepObservation through anvil/services/compute/local_torch_backend.py"
Task: "Thread CoreStepObservation through anvil/services/compute/local_stdlib_backend.py"

# Theme mappings in parallel after signal-bus:
Task: "forge.js mapping() + forge.css effects"
Task: "oldgrowth.js mapping() + oldgrowth.css effects"
Task: "aurora.js mapping() + aurora.css effects"
```

---

## Implementation Strategy

### MVP First (US1 only)

1. Phase 1 Setup → 2. Phase 2 Foundational → 3. Phase 3 US1.
4. **STOP & VALIDATE**: 4 themes selectable, persisted, no flash, reset works (cosmetic). Demo-able MVP.

### Incremental Delivery

1. Setup + Foundational → engine ready, default unchanged.
2. US1 → theme selection (MVP, cosmetic) → demo.
3. US2 → live expression (the "more than reskinning" payoff) → demo.
4. US3 → accessibility hardening → demo.
5. US4 → light/dark within themes → demo.
Each story adds value without breaking prior ones.

### Parallel Team Strategy

After Foundational: Dev A → US1 picker + cosmetic themes; Dev B → US2 backend signal slice (T023–T036); converge on theme `mapping()` (T037–T039); then US3/US4.

---

## Notes

- **Canonical terminology**: "**behavioral theme**" is the canonical term (synonym used loosely elsewhere: "expressive theme"). A theme with a live signal→expression `mapping()` is a *behavioral theme*; one with `mapping:null` is a *cosmetic theme*. Prefer the canonical terms in all new prose and code comments.
- [P] = different files, no incomplete dependencies. [Story] traces task → user story.
- Backend follows TDD (Article IV); the JS theme engine is covered by the e2e system test T060 (`make test-system`); finer JS/visual/a11y behavior is verified via quickstart.md (no JS unit runner in repo).
- Backend MUST emit only neutral signals (`metrics`, `divergence`, neutral `milestone` cadence marker); "disturbance" is derived client-side in Old Growth (FR-011, R6). The `milestone` marker writes NO artifact and does NOT imply a model checkpoint (R5).
- The engines are **unbatched, per-document, variable-length** (`core/torch_engine.py:469-501`, `core/engine.py:401-431`): there is NO `batch_size`, and tokens/step `= n = min(block_size, len-1)` varies. `tokens_per_sec` MUST be derived from per-step `tokens` carried on `CoreStepObservation`, not from config. No gradient clipping exists, so `grad_norm` is a single (un-clipped) norm sampled after `backward()`.
- Divergence HALTS the run by raising `DivergenceError` from the progress closure (engines do not break on NaN); the SSE route must add `divergence` to its terminal break tuple and reconcile persisted run status (T034a).
- `core/` stays zero-dep (Article I): stdlib `CoreStepObservation`; Pydantic `StepMetrics` lives in the service layer.
- Default theme MUST remain byte-for-byte unchanged for non-adopters (FR-019, SC-007).
- Commit per task or logical group; commit only when explicitly requested.
- The Oracle architecture review of the signal slice was unavailable at plan time (see research.md note) — consider re-validating via Oracle before/during implementation of the US2 backend slice.
