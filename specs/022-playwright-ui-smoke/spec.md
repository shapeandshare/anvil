# Feature Specification: Playwright UI Smoke Harness

**Feature Branch**: `022-playwright-ui-smoke`  
**Created**: 2026-06-21  
**Status**: Draft  
**Input**: Playwright UI Smoke Harness Implementation Plan — a thin browser-based smoke test suite to verify that the application's polished frontend UI is correctly wired to the working backend.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Verify that all primary UI pages load without errors (Priority: P1)

A developer or CI system needs confidence that every primary page in the application renders correctly — no blank pages, no broken layouts, no JavaScript console errors. This is the most basic integrity check: if pages don't load, nothing else can be verified.

**Why this priority**: P1 — this is the foundational smoke check. All other UI interactions depend on pages loading correctly. It also provides the fastest feedback on deployment issues.

**Independent Test**: Can be fully tested by loading each primary route and verifying a known landmark element is visible with no console errors. Delivers immediate confidence that the frontend serves without critical failures.

**Acceptance Scenarios**:

1. **Given** the application is running, **When** a browser navigates to the dashboard route, **Then** the page loads with a visible dashboard component and zero console errors.
2. **Given** the application is running, **When** a browser navigates to each of the remaining primary routes (datasets, training, experiments, models, inference, operations, learn), **Then** each page loads with a visible page-specific landmark and zero console errors.
3. **Given** the user is on any page, **When** they click a navigation link to another primary page, **Then** the target page loads with the correct content.

---

### User Story 2 — Verify that training can be started through the UI and live progress is displayed (Priority: P1)

A developer needs to confirm that the most complex frontend-backend interaction — starting a training run and watching live progress updates — actually works end-to-end. This is the single highest-value verification because it exercises the entire pipeline: form submission, backend training orchestration, real-time event streaming, and chart rendering.

**Why this priority**: P1 — the live training chart with real-time streaming is the most technically complex UI feature and the application's primary differentiator. If this breaks, the core value proposition is lost.

**Independent Test**: Can be fully tested by configuring minimal training parameters through the UI, starting the run, and observing that at least one live data point appears in the training progress display.

**Acceptance Scenarios**:

1. **Given** a dataset exists in the system, **When** a user configures training parameters (tiny model config) and clicks the start button on the training page, **Then** the training begins and live progress updates appear within a reasonable time.
2. **Given** training is running, **When** a live data point is emitted by the backend, **Then** the training progress display (chart or metrics readout) updates to show the new point.
3. **Given** training reaches completion, **When** the backend signals the run is finished, **Then** the UI displays a terminal/completed state.

---

### User Story 3 — Verify that dataset upload works through the UI (Priority: P2)

A developer needs to confirm that the dataset upload form is wired to the backend — a file selected through the browser's file picker reaches the server and the results appear in the on-page listing.

**Why this priority**: P2 — dataset upload is a primary workflow but can be verified via API independently. The UI wiring check ensures the form-component chain works end-to-end.

**Independent Test**: Can be fully tested by uploading a small text file through the upload control and asserting the dataset appears in the visible list.

**Acceptance Scenarios**:

1. **Given** a user is on the datasets page, **When** they select a small text file using the file picker and submit, **Then** the new dataset appears in the on-page list or table within a reasonable time.
2. **Given** a dataset upload is submitted through the UI, **When** the operation completes, **Then** no uncaught JavaScript errors occur.

---

### User Story 4 — Verify that completed training runs appear in the experiment history (Priority: P2)

After a training run completes through the UI, a developer needs to confirm that the run is surfaced in the experiment listing with its final metrics (e.g., final loss). This proves the experiment tracking page correctly reads from the backend.

**Why this priority**: P2 — run history is important for comparing experiments but can be verified via API. The UI wiring check ensures the listing page renders real data from the backend.

**Independent Test**: Can be tested independently by navigating to the experiments page after a completed run and confirming the run is listed with its final loss value.

**Acceptance Scenarios**:

1. **Given** a training run has completed, **When** a user navigates to the experiments page, **Then** the completed run appears in the list.
2. **Given** a completed run appears in the list, **Then** the final loss value is rendered as visible text in the run's entry.

---

### User Story 5 — Verify that inference/text generation works through the UI (Priority: P3)

A developer needs to confirm that the inference playground — selecting a model, typing a prompt, and submitting for generation — is wired to the backend and renders non-empty output.

**Why this priority**: P3 — inference is important but relies on a completed training run (or seeded model), making it more dependent on prior steps. It provides a valuable end-to-end confidence check.

**Independent Test**: Can be tested independently by selecting a registered model, entering a prompt, submitting, and verifying that generated text appears in the output area.

**Acceptance Scenarios**:

1. **Given** a registered model exists, **When** a user selects that model on the inference page, enters a prompt, and submits, **Then** non-empty generated text is rendered in the output area within 30 seconds.
2. **Given** generation completes, **When** the output is rendered, **Then** no uncaught JavaScript errors occur.

---

### Edge Cases

- What happens when the backend is not fully ready (still starting up) and a page is loaded? — Should show a graceful loading or error state, not a blank page or infinite spinner.
- What happens when an API endpoint returns an error during a UI workflow? — The UI should display a user-visible error message, not silently fail.
- How does the training UI handle a run that errors immediately (e.g., invalid config)? — Should show an error state in the UI, not hang indefinitely.
- What happens when no datasets exist and the training page is configured? — Dropdowns/selectors should show empty states, not break.
- How does the inference page handle selecting a model that has no valid checkpoint? — Should show a meaningful message, not a broken output area.
- What happens when the experiment-tracking service (MLflow sidecar) is still initializing when the experiments page loads? — The completed run may not yet appear; the test must poll/wait for the tracking service to surface the run rather than asserting once and failing.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: All primary application pages MUST load without **uncaught JavaScript errors, unhandled promise rejections, or failed resource loads** when navigated to directly (via URL). Benign console *warnings* (e.g., favicon 404, third-party deprecation notices) MUST NOT fail the test — only error-level signals do (see the Console Error entity for the precise error/warning distinction).
- **FR-002**: Each primary page MUST display a page-specific landmark element (e.g., heading, hero section, primary control) when loaded.
- **FR-003**: The navigation bar MUST be present on every page and navigation links MUST navigate to the correct target page.
- **FR-004**: The dataset upload form MUST accept a file via the browser's file picker, submit it to the backend, and the uploaded dataset MUST appear in the on-page listing.
- **FR-005**: The training page MUST allow a user to configure training parameters, select a dataset, start a run, and observe live progress updates in the training display.
- **FR-006**: The training progress display MUST update within a reasonable time when the backend sends new progress data. The live-progress assertion MUST confirm a **numeric step/loss value is rendered** (not a placeholder/empty state) — i.e., the loss readout matches a real number, not the default "no data yet" glyph.
- **FR-007**: The training UI MUST display a terminal or completed state when the backend signals the run is finished.
- **FR-008**: The experiments page MUST list completed training runs and display the final loss value for each run. Because run history is backed by a separate experiment-tracking service (MLflow sidecar) that starts independently of the web server, the experiment-listing test MUST confirm the tracking service has surfaced the run (poll the listing) rather than asserting immediately after the web page loads.
- **FR-009**: The inference page MUST allow a user to select a registered model, enter a text prompt, submit for generation, and render non-empty generated output. The model used by this test MUST be **inference-capable** (a real, generation-ready checkpoint) — a metadata-only model record is insufficient. The seeding approach MUST be validated to produce a model that actually generates before this test is relied upon.
- **FR-010**: All UI operations that involve user interaction (upload, start training, submit inference) MUST complete without uncaught JavaScript errors.
- **FR-011**: The smoke test suite MUST be independently invocable and MUST NOT affect the standard unit test suite or code coverage metrics.
- **FR-012**: The smoke test suite MUST complete reliably without hard-coded delays that assume specific system performance characteristics.
- **FR-013**: The smoke test suite MUST verify the application is fully available and responsive before beginning tests. Readiness MUST cover **all backing services a given test depends on** — for tests that read run history, this includes the experiment-tracking service, not just the web server's health endpoint.

### Key Entities *(include if feature involves data)*

- **Smoke Test**: A single automated browser session that performs a sequence of interactions and assertions. Each test is self-contained, covers one user-facing workflow, and produces a pass/fail result.
- **Primary Route**: One of the application's main page URLs (dashboard, datasets, training, experiments, models, inference, operations, learn) that constitutes the core navigation surface.
- **Console Error**: An **error-level** browser signal — an uncaught JavaScript runtime error, an unhandled promise rejection, or a failed resource load (4xx/5xx for a page asset) — captured during page load or interaction. These FAIL the test. **Warning-level** console output (deprecation notices, favicon 404s, third-party noise) is captured for diagnostics but does NOT fail the test. This error/warning distinction is the canonical interpretation of "no console errors" used throughout this spec (FR-001, SC-001).
- **Live Data Point**: A single unit of real-time progress information (step number + loss value) emitted by the backend and rendered as a **numeric value** in the frontend training display during an active training run. A placeholder/empty-state glyph (e.g., the "no data yet" character) does NOT count as a live data point — the assertion requires a real number.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All primary application routes can be loaded sequentially in a single automated session without any JavaScript console error, page crash, or blank page.
- **SC-002**: A dataset can be uploaded through the browser UI and its name is visible in the dataset listing within 10 seconds of submission.
- **SC-003**: A training run can be started through the UI with a minimal model configuration, and at least one live data point (a numeric step/loss value) appears in the training progress display within 30 seconds of starting. (The 30-second bound is provisional for local runs; the CI environment MAY use a more generous timeout to absorb container cold-start and slower CPUs, as long as it remains bounded.)
- **SC-004**: After a training run completes, its entry appears in the experiment listing with a visible final loss value.
- **SC-005**: A text prompt submitted through the inference page produces non-empty generated output rendered in the visible output area within 30 seconds of submission.
- **SC-006**: The browser smoke test suite provides reliable pass/fail results that can serve as a deployment signal, with zero false passes on broken UI-to-backend wiring. **For v1, this signal runs as a NON-blocking CI job** (reporting status without blocking merge), mirroring the precedent that the existing heavy system suite is deliberately kept out of the blocking CI path. The gate MAY be promoted to blocking only after it has demonstrated zero flakes over a sustained period (see Assumptions).
- **SC-007**: The smoke test suite produces consistent results across 3 consecutive runs (zero flakiness) for the same application state.

## Assumptions

- The application is running and accessible at a known URL during test execution (tests do not start the application themselves).
- A companion API-level testing suite covers functional/backend correctness; the browser smoke suite only verifies UI-to-backend wiring.
- Tests use a minimal model configuration (tiny embedding size, single layer, few training steps) so training completes in seconds, not minutes.
- Test data (sample text files for upload, small prompts for inference) is bundled with or seeded by the test suite itself.
- The inference test requires an **inference-capable** model (a real generation-ready checkpoint). If API seeding cannot produce a generation-ready model, the inference test reuses a tiny model trained earlier in the suite rather than a metadata-only record.
- The application supervises a separate experiment-tracking service (MLflow) that starts independently of the web server. Tests that read run history account for this service's readiness, not just the web server's.
- The smoke test suite runs in a Linux environment with a supported browser engine for v1; cross-browser testing is out of scope.
- The smoke test suite is NOT part of the standard unit test coverage gate and does not contribute to line coverage metrics.
- No authentication or multi-user scenarios are required — all tests assume a single local user with full access.
- The feature is independent of the application's cloud/SaaS mode and only covers local operation.
- An Architecture Decision Record (ADR) is captured as a prerequisite before implementation begins, documenting the tool choice, scope boundary, and CI isolation strategy (including the v1 non-blocking decision and the promotion-to-blocking criteria).
- The CI job is **non-blocking for v1**. Promotion to a blocking merge gate requires a demonstrated zero-flake record across at least 10 consecutive CI runs (or an equivalent sustained period), recorded in the ADR. This mirrors the existing heavy system-test suite, which is intentionally kept out of the blocking CI path.
- Visual pixel regression testing and theme gallery screenshots are explicitly out of scope.
- Accessibility audits are out of scope for this feature.
