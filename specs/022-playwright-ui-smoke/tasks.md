# Tasks: Playwright UI Smoke Harness

**Input**: Design documents from `specs/022-playwright-ui-smoke/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, quickstart.md

**Tests**: This feature IS a test suite — the implementation tasks ARE the tests. No separate test-generation phase is needed.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Test files**: `tests/browser/` (new, peer of `tests/system/`)
- **Config files**: `pyproject.toml`, `Makefile`, `.github/workflows/ci.yml` (existing, minimal edits)
- **ADR**: `docs/vault/Decisions/` (existing)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: ADR, dependency registration, and test harness scaffolding

- [x] T001 Write ADR at `docs/vault/Decisions/ADR-034-playwright-ui-smoke-harness.md` capturing Playwright rationale, scope boundary, coverage exclusion, CI isolation, Chromium-only v1, the **v1 non-blocking CI decision** (and the ≥10-run zero-flake promotion criteria), and the rationale (mirrors `tests/system` being kept out of the blocking path)
- [x] T002 [P] Add `pytest-playwright>=0.5,<1` to `pyproject.toml` under `[project.optional-dependencies].dev`
- [x] T003 [P] Extend pytest `addopts` with `--ignore=tests/browser` and extend `[tool.coverage.run].omit` with `"tests/browser/*"` in `pyproject.toml`
- [x] T004 [P] Add `test-browser` target to `Makefile` (mirror `test-system`: compose down -v → up -d --build --wait → pytest tests/browser -v --no-cov → compose down -v)

**Checkpoint**: Setup complete — ADR committed, dependency available, Makefile target ready

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared test infrastructure that ALL test files depend on

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T005 Create `tests/browser/conftest.py` with:
  - Session-scoped compose readiness wait (polls `GET /v1/health` at `http://localhost:8080`)
  - An MLflow-sidecar readiness check (or experiment-listing readiness probe) used by run-history tests — readiness covers all backing services a test depends on, not just the web server (FR-013)
  - `page` fixture configured for Chromium headless, 15s default timeout
  - `base_url` fixture returning `http://localhost:8080`
  - `assert_no_console_errors` helper that attaches `page.on("console")` and `page.on("pageerror")` listeners, failing ONLY on error-level signals (uncaught JS errors, unhandled rejections, failed asset loads). Warning-level console output is collected for diagnostics but does NOT fail the test (per the Console Error entity)
  - `dataset_seed` and `model_seed` convenience fixtures using an internal httpx client to seed test data via API. `model_seed` MUST produce an **inference-capable** (generation-ready) model — validate this; if API seeding cannot, fall back to reusing a tiny model trained during the suite (M1/FR-009)

**Checkpoint**: Foundation ready — conftest.py provides all shared fixtures; user story implementation can begin

---

## Phase 3: User Story 1 — Verify all primary UI pages load without errors (Priority: P1) 🎯 MVP

**Goal**: Every primary page renders correctly with a visible landmark element and zero JavaScript console errors. Nav bar links navigate to the correct target page.

**Independent Test**: Navigate to each of the 8 primary routes, verify a page-specific landmark is visible, and confirm no console/page errors were recorded.

### Implementation for User Story 1

- [x] T006 [US1] Implement `tests/browser/test_navigation_smoke.py`:
  - For each primary route (Dashboard, Datasets, Training, Experiments, Models, Inference, Operations, Learn):
    - `page.goto(url)`
    - Assert a known landmark element is visible (selectors derived by reading actual Jinja2 templates)
    - Assert zero console errors via `assert_no_console_errors` helper
  - Assert nav bar is present on dashboard page
  - Assert clicking a nav link (e.g., Datasets → Experiments) navigates to the correct page

**Checkpoint**: Navigation smoke test passes independently — all 8 routes verified

---

## Phase 4: User Story 3 — Verify dataset upload works through the UI (Priority: P2)

> **Note on ordering**: US3 (P2) appears before US2 (P1) in phase numbering because US4 (P2) depends on US2, making US2 a prerequisite for the P2 chain. This reorder maximizes parallel execution — US3 is fully independent and can be implemented in parallel with US2. US4 follows US2 completion.

**Goal**: A small text file uploaded through the browser's file picker reaches the backend and the dataset appears in the on-page listing.

**Independent Test**: Go to the datasets page, upload a small `.txt` file, and assert the dataset name becomes visible in the list within 10 seconds.

### Implementation for User Story 3

- [x] T007 [P] [US3] Implement `tests/browser/test_dataset_upload_wiring.py`:
  - Navigate to `/v1/datasets-page`
  - Create a small temp `.txt` file with sample content
  - Use `locator.set_input_files()` on the page's real upload control
  - Submit the form
  - Assert the uploaded dataset name appears in the on-page list/table using `expect(locator).to_be_visible()` (10s timeout)
  - Assert no uncaught JavaScript errors occurred

**Checkpoint**: Dataset upload wiring test passes independently

---

## Phase 5: User Story 2 — Verify training can be started through UI with live progress (Priority: P1)

**Goal**: The most complex frontend-backend interaction — starting a training run and watching live SSE-streamed data points — works end-to-end.

**Independent Test**: Seed a dataset via API, configure minimal training parameters on the training page, start the run, and assert at least one live data point appears in the training progress display within 30 seconds.

### Implementation for User Story 2

- [x] T008 [US2] Implement `tests/browser/test_training_sse_wiring.py`:
  - Seed a dataset via API using the `dataset_seed` fixture from conftest
  - Navigate to `/v1/training-page`
  - Select the seeded dataset from the dataset selector
  - Set tiny model config (`n_embd=16`, `n_layer=1`, `num_steps≈20`, `local-stdlib` backend)
  - Click the Start button
  - Assert at least one live data point appears — target the `#metric-loss` / `#metric-step` text nodes (verified to exist in `training.html`). The loss assertion MUST poll for a **numeric value matching `/\d+\.\d{4}/`**, NOT merely non-empty text, because the element defaults to the `—` placeholder until the first real point arrives (C2)
  - Use `#connection-state` (`streaming` → `done`) and/or the `#loss-display` "FINAL loss:" banner to detect the terminal/completed state
  - Use a generous CI-tolerant timeout for the first data point (provisional 30s locally; widen for CI cold start)
  - Assert no error-level console signals occurred

**Checkpoint**: Training SSE wiring test passes independently — the highest-value assertion verified

---

## Phase 6: User Story 4 — Verify completed runs appear in experiment history (Priority: P2)

**Goal**: After a training run completes, it appears in the experiment listing with its final loss value rendered.

**Independent Test**: Navigate to the experiments page after a completed run and confirm the run is listed with its final loss value.

### Implementation for User Story 4

- [x] T009 [US4] Implement `tests/browser/test_experiment_listing_wiring.py`:
  - Ensure a completed training run exists (reuse the US2 run or seed a completed run via API)
  - Wait on the conftest MLflow/experiment-listing readiness probe before asserting — the run is surfaced by the tracking sidecar, which starts independently of the web server (C3/FR-008)
  - Navigate to `/v1/experiments-page`
  - **Poll** the listing (Playwright auto-wait/`expect`) for the run to appear — do NOT assert once and fail; the tracking service may surface the run slightly after page load
  - Assert the run appears with its label/name visible
  - Assert the final loss value is rendered as visible text in the run's entry
  - Assert no error-level console signals occurred

**Checkpoint**: Experiment listing test passes independently

---

## Phase 7: User Story 5 — Verify inference works through the UI (Priority: P3)

**Goal**: The inference playground — selecting a model, typing a prompt, and submitting for generation — is wired to the backend and renders non-empty generated output.

**Independent Test**: Select a registered model, enter a prompt, submit, and verify non-empty generated text appears in the output area.

### Implementation for User Story 5

- [x] T010 [US5] Implement `tests/browser/test_inference_wiring.py`:
  - Obtain an **inference-capable** model via the `model_seed` fixture (generation-ready checkpoint, not a metadata-only record — M1/FR-009). If API seeding cannot produce one, reuse a tiny model trained during the suite
  - Navigate to `/v1/inference-page`
  - Select the model from the model selector
  - Enter a short prompt (e.g., "hello") in the prompt input
  - Click the generate/submit button
  - Assert non-empty generated text is rendered in the visible output area within 30 seconds (CI-tolerant timeout)
  - Assert no error-level console signals occurred

**Checkpoint**: Inference wiring test passes independently

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: CI integration, validation, and documentation

- [x] T011 [P] Add Linux-only browser test CI job to `.github/workflows/ci.yml`:
  - Steps: checkout → setup uv → `make setup` → `uv run playwright install --with-deps chromium` → `make test-browser`
  - **NON-blocking for v1** (`continue-on-error: true`) — mirrors the existing heavy `tests/system` suite being kept out of the blocking CI path. Do NOT add to the `gate-status` job's `needs:` list / gate loop for v1 (a flaky heavy job must not stall all merges)
  - Gated behind `if: needs.bump-scope-guard.outputs.scope != 'version-only'`
  - Job runs on `ubuntu-latest`
  - Document in the ADR the promotion criteria: flip to `continue-on-error: false` and wire into `gate-status` only after ≥10 consecutive zero-flake CI runs
- [x] T012 [P] Update `AGENTS.md` Active Technologies section with new `tests/browser/` and `pytest-playwright` dev dependency entry
- [x] T013 Run `make test-browser` 3 consecutive times to validate zero-flake stability (all smoke tests must pass each run)
- [x] T014 [P] Add session log to `docs/vault/Sessions/` documenting the ADR decision and SSE-chart-update assertion technique
- [ ] T015 [P] Verify edge case: navigate to `/v1/datasets-page` with no datasets and assert empty state renders without error (no crash, no error-level console signals)

**Checkpoint**: All smoke tests green across 3 consecutive runs; non-blocking CI job wired; vault enriched

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — T002/T003/T004 are parallel [P]
- **Foundational (Phase 2)**: Depends on T002 (pytest-playwright dep available) — BLOCKS all user stories
- **User Stories (Phases 3-7)**: All depend on Phase 2 (conftest.py)
  - US1 (T006), US3 (T007), US5 (T010) are fully independent — can proceed in parallel
  - US2 (T008) can proceed in parallel with US1/US3 — dataset seeded via API, not UI
  - US4 (T009) depends on US2 (T008) — needs a completed run to verify listing
- **Polish (Phase 8)**: Depends on Phase 2 (conftest.py) and conftest-based test infrastructure; CI job (T011) must run after test files exist

### User Story Dependencies

- **User Story 1 (P1)**: No test-level dependencies — fully independent
- **User Story 3 (P2)**: No test-level dependencies — fully independent
- **User Story 2 (P1)**: No test-level dependencies — dataset seeded via API
- **User Story 4 (P2)**: Depends on US2 — needs a completed training run to verify
- **User Story 5 (P3)**: No test-level dependencies — model seeded via API

### Parallel Opportunities

- T002/T003/T004 — all three Setup tasks can run in parallel (different files, no shared state)
- T006 (US1), T007 (US3), T008 (US2), T010 (US5) — all independent test files, can be implemented in parallel after Phase 2
- T009 (US4) must follow T008 (US2), but can proceed once US2 implementation exists
- T011/T012/T014/T015 — Polish tasks can run in parallel
- Within a single test file, helper fixtures and page interactions are sequential by nature

---

## Parallel Examples

```bash
# Phase 1 - Setup tasks (all parallel):
Task: "Write ADR at docs/vault/Decisions/ADR-034-playwright-ui-smoke-harness.md"
Task: "Add pytest-playwright dev dependency to pyproject.toml"
Task: "Extend pytest --ignore and coverage omit in pyproject.toml"
Task: "Add test-browser target to Makefile"

# Phase 3+ — Independent user stories (after Phase 2):
Task: "Implement test_navigation_smoke.py"         # US1
Task: "Implement test_training_sse_wiring.py"       # US2
Task: "Implement test_dataset_upload_wiring.py"     # US3
Task: "Implement test_inference_wiring.py"          # US5

# US4 follows US2:
Task: "Implement test_experiment_listing_wiring.py" # US4 (after US2)

# Polish phase (all parallel):
Task: "Add CI job to .github/workflows/ci.yml"
Task: "Update AGENTS.md Active Technologies"
Task: "Add session log to docs/vault/Sessions/"
Task: "Verify edge case: empty datasets page"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001-T004) — ADR + deps + config
2. Complete Phase 2: Foundational (T005) — conftest.py (CRITICAL — blocks all stories)
3. Complete Phase 3: US1 (T006) — navigation smoke test
4. **STOP and VALIDATE**: `make test-browser` — at minimum, navigation smoke should pass
5. This is the smallest deliverable: "pages load without errors" verified

### Incremental Delivery

1. Setup + Foundational → Harness scaffold ready
2. Add US1 (Navigation) → Deploy/Demo (smallest viable smoke check)
3. Add US3 (Dataset upload) → Deploy/Demo
4. Add US2 (Training SSE) → Deploy/Demo (highest-value test now active)
5. Add US4 (Experiment listing) → Deploy/Demo
6. Add US5 (Inference) → Deploy/Demo (complete suite)
7. Add non-blocking CI job + validation + vault enrichment + edge case verification → CI signal active

### Parallel Team Strategy

1. Team completes Phase 1 + Phase 2 together (shared infra)
2. Once Phase 2 is done:
   - Developer A: US1 (T006) + US4 (T009)
   - Developer B: US3 (T007) + US5 (T010)
   - Developer C: US2 (T008) — the most complex, highest-value test
3. Developer A picks up US4 after US2 is complete
4. Polish phase tasks (T011-T014) assigned to any free developer after all tests green

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story is independently testable (US4 depends on US2 completion but is independently verifiable)
- All selector values MUST be derived by reading actual Jinja2 templates and JS files — never guess element IDs
- ADR (T001) is a gating prerequisite per AGENTS.md Principle 4
- All test assertions use Playwright auto-waiting — zero fixed `sleep()` calls
- Chromium-only for v1; cross-browser and visual regression tests are explicitly out of scope
- Coverage gate (`fail_under`) is unaffected — `tests/browser/*` is omitted from coverage