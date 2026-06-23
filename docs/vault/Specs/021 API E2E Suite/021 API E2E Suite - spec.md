---
title: 021 API E2E Suite - spec
type: spec
tags:
  - type/spec
spec-refs:
  - docs/vault/Specs/021 API E2E Suite/
related:
  - '[[021 API E2E Suite]]'
created: ~
updated: ~
---
# Feature Specification: Whole-API E2E Test Suite

**Feature Branch**: `021-api-e2e-suite`
**Created**: 2026-06-21
**Status**: Draft
**Input**: User description: `docs/functional-api-e2e-suite.md`

## User Scenarios & Testing

### User Story 1 — Developer self-verifies all APIs before pushing (Priority: P1)

A developer working on any part of the application needs to know their changes haven't broken existing API behavior. They run a single command and get a clear pass/fail signal for every API router in the system — the 14 mounted routers: training, experiments, datasets, corpora, registry, eval, eval-datasets, inference, compute, governance, health-ops, pages (HTML), learning, and content.

**Why this priority**: This is the core value of the suite. Without comprehensive coverage, developers ship regressions. Every other capability depends on this foundation.

**Independent Test**: Can be tested by running the full suite and observing that all 14 routers are exercised and each test executes and reports a clear pass or fail. Delivers confidence that the entire API surface is verified.

**Acceptance Scenarios**:

1. **Given** a freshly initialized application, **When** the full test suite runs, **Then** every API endpoint test executes and reports a clear pass or fail without requiring external services or network access (a failing test indicates a real API contract violation to investigate, not a suite defect).
2. **Given** a developer introduces a breaking change to a leaf (non-shared) endpoint, **When** the suite runs, **Then** the tests for that endpoint fail with a message identifying the broken contract. (Note: breaking a foundational endpoint used by shared factories — e.g., training start — may cascade failures across modules that depend on it; this is expected.)
3. **Given** the suite has been run once, **When** it runs again immediately, **Then** results are deterministic (identical pass/fail outcome).

---

### User Story 2 — CI pipeline catches API regressions automatically (Priority: P1)

The CI pipeline runs the full API test suite on every pull request. If a PR breaks an API contract — changes a response format, removes an endpoint, or introduces a validation error — the pipeline fails and blocks the merge.

**Why this priority**: Preventing regressions from reaching production is the primary ROI of investing in e2e tests. This story gates all developer contributions on passing API contract verification.

**Independent Test**: Can be tested by committing a change that breaks an API response field and verifying the pipeline reports a failure with the specific broken route. Delivers a hard merge block on API regressions.

**Acceptance Scenarios**:

1. **Given** a pull request that modifies an API handler incorrectly, **When** the CI pipeline runs the test suite, **Then** the pipeline fails with a clear indication of which endpoint and which contract was violated.
2. **Given** a pull request that adds a new endpoint with proper test coverage, **When** the CI pipeline runs, **Then** the new endpoint's tests pass alongside all existing tests.

---

### User Story 3 — Developer debugs failures with clear, isolated test output (Priority: P2)

When a test fails, the developer needs to immediately understand which router, which endpoint, and which aspect of the contract is broken. Each test module is independently runnable, and each test case is self-seeding and isolated.

**Why this priority**: Debugging productivity depends on test isolation and clear failure messages. Without it, developers spend hours reproducing failures.

**Independent Test**: Can be tested by running a single test module in isolation and observing it self-seeds its data, runs its cases, and reports pass/fail without depending on other tests having run first. Delivers debuggable, independent test execution.

**Acceptance Scenarios**:

1. **Given** a developer wants to verify only dataset-related APIs, **When** they run just the dataset test module, **Then** it creates its own test data, runs all dataset endpoint tests, and cleans up — with no dependency on other modules.
2. **Given** a test failure for an endpoint, **When** the developer reads the failure message, **Then** it identifies the specific endpoint path, the expected vs actual response shape, and any validation errors.

---

### User Story 4 — Cross-router integration verified end-to-end (Priority: P2)

The most critical user workflow — upload corpus, build dataset, train model, register, export, run inference — composes correctly across all the routers involved. A lifecycle integration test proves the routers wire together in sequence, not just in isolation.

**Why this priority**: Isolated router tests can pass even when the routers don't compose correctly. The lifecycle test catches integration bugs no single-router test can find.

**Independent Test**: Can be tested by running just the lifecycle journey test module and observing it completes a full train-to-inference pipeline within a reasonable time using minimal compute resources. Delivers integration confidence across the entire API stack.

**Acceptance Scenarios**:

1. **Given** a fresh application state, **When** the lifecycle test runs, **Then** it successfully completes a full pipeline: prepare data, train a model, verify the experiment recorded results, register the model, and produce non-empty inference output.
2. **Given** any intermediate step in the lifecycle fails, **When** the test encounters the failure, **Then** it reports which step failed and does not silently skip subsequent steps.

---

### Edge Cases

- What happens when an endpoint receives a request for a resource that doesn't exist (e.g., unknown dataset, unknown training run)? The system must return a proper error response.
- What happens when a user submits incomplete or invalid input to a creation endpoint? The system must return a validation error with sufficient detail for the caller to fix the input.
- What happens when stateful operations are applied in an invalid order (e.g., accepting a content session with no staged files, or freezing an already-frozen version)? The system must handle these gracefully with appropriate conflict or error responses.
- What happens when SSE streams are accessed for completed or unknown resources? The system must handle these without hanging or crashing. Note: a stream opened against an already-completed run may yield zero or only terminal events — tests that need to observe in-progress events MUST read the stream concurrently with an active run, and stream-reading helpers MUST enforce a bounded timeout so a silent/empty stream never hangs the suite.
- What happens when service-control endpoints (start, stop, restart, kill-port) are called in the test environment? The system must guard against destabilizing the test process — responses should be safe status-only assertions.

## Requirements

### Functional Requirements

- **FR-001**: The test suite MUST cover all 14 routers mounted in the `/v1` namespace: training, experiments, datasets, corpora, registry, eval, eval-datasets, inference, compute, governance, health-ops, pages (HTML rendering), learning, and content. Coverage MAY be organized into test modules that group related routers — specifically, the `learning` router's data routes (model listing, sampling) MAY be exercised within the inference test module and its HTML lesson routes within the pages test module — provided every router's endpoints are exercised somewhere in the suite.
- **FR-002**: Each test module MUST cover both happy-path (success) and error-path (not-found, validation failure, conflict where applicable) scenarios for its router's endpoints.
- **FR-003**: A cross-router lifecycle integration test MUST chain the end-to-end user workflow — data preparation, training, experiment tracking, model registration, and inference — verifying routers compose correctly.
- **FR-004**: Every test MUST self-seed its own data and be independently runnable with no test-to-test data dependencies and no shared mutable state.
- **FR-005**: Shared factory helpers MUST be provided so that tests can concisely create seeded resources without duplicating setup logic.
- **FR-006**: Tests MUST use in-process request transport — no live server, no network, no external dependencies.
- **FR-007**: Training-involved tests MUST use the smallest viable model configuration and minimal compute steps to keep suite runtime bounded.
- **FR-008**: Tests MUST NOT assert exact values of non-deterministic outputs (loss values, perplexity scores, generated text). Assertions must be against finiteness, numeric range, or non-emptiness.
- **FR-009**: The test suite MUST be deterministic — three consecutive runs must produce identical pass/fail results with no flaky tests. Timing-sensitive surfaces (SSE streaming, training-completion polling) are the primary flake risk and MUST be made robust: stream readers and status pollers MUST use bounded timeouts and MUST NOT depend on a specific number of intermediate events arriving within a fixed wall-clock window. Where in-progress events are required, the stream MUST be read concurrently with an active run rather than after completion.
- **FR-010**: Service-control endpoints MUST be tested only for safe status responses — they must not destabilize the test process.
- **FR-011**: HTML page routes MUST be tested at the render-smoke level (successful HTTP response with expected content) — full UI interaction is out of scope for this suite.
- **FR-012**: Content repository endpoints MUST be tested through the full reproducibility lifecycle: create source, stage content, validate, accept changes, freeze a version, and verify the content resolves byte-identically. "Byte-identical" verification MUST compare the actual resolved content (or its content-addressed digest) against the originally staged content — a successful HTTP status alone is NOT sufficient to satisfy this requirement.
- **FR-013**: Test failures MUST clearly identify the specific endpoint, the contract violated, and expected versus actual behavior.
- **FR-014**: Tests MUST NOT introduce new dependencies beyond the project's existing testing toolchain.

### Key Entities

- **Test Module**: A test file covering one router or domain, containing test functions for that router's endpoints.
- **Seeding Factory**: A reusable helper that creates a specific resource (e.g., a seeded corpus, dataset, or trained model) for use across tests.
- **Lifecycle Integration Test**: A single end-to-end test that chains multiple routers together in a realistic user workflow to verify cross-router composition.
- **SSE Stream Reader**: A reusable helper that reads Server-Sent Events from a streaming endpoint.
- **Poll Helper**: A reusable helper that checks a status endpoint until a terminal state is reached, with a configurable timeout.

## Success Criteria

### Measurable Outcomes

- **SC-001**: All 14 mounted routers have test coverage with no uncovered routers — training, experiments, datasets, corpora, registry, eval, eval-datasets, inference, compute, governance, health-ops, pages, learning, and content. Every router's endpoints are exercised by at least one test (the `learning` router's routes may be exercised within the inference and pages modules).
- **SC-002**: The lifecycle integration test completes a full pipeline from data preparation through inference using standard compute resources (CPU) within a bounded time budget. An initial 90-second target applies; the actual budget MUST be validated by measuring a real run during implementation and the target adjusted to a value comfortably above the measured baseline (e.g., measured time plus headroom) so the threshold reflects reality rather than a guess.
- **SC-003**: A developer can run any single test module independently and observe it self-seeds, passes, and does not depend on other modules having run first.
- **SC-004**: Three consecutive full suite runs produce identical pass/fail results with no flaky tests.
- **SC-005**: The test suite runs as part of the standard project test command and fails the build on any broken API contract.
- **SC-006**: Developers adding new endpoints can follow established test patterns in the corresponding router's test module and get clear guidance on what to assert.
- **SC-007**: The overall project coverage metric reported after the suite is added does not regress below the existing coverage target.

## Assumptions

- The test suite targets the API layer only — browser and UI interaction testing is handled by a separate, complementary effort.
- Tests run in a local development environment with no authentication, no cloud services, and no external dependencies.
- The training engine can produce meaningful (numerically finite, non-degenerate) loss values with a minimal model configuration in very few steps.
- The application's demo data bootstrap is idempotent — calling it multiple times has no harmful side effects.
- Test data (corpora uploaded, datasets created, models trained) is ephemeral and recreated per test run with no persistent shared fixtures.
- The project's existing test command and continuous integration job are the integration point — no new CI jobs or build steps are required.
- Experiment tracking is NOT guaranteed to be fully operational during in-process tests — the experiment-tracking sidecar is not started in the test environment, so tracking may report a degraded state. Tests that verify experiment results MUST read from the local run state and MUST NOT require a live tracking server or assert that a tracking-server run identifier is present. Lifecycle and experiment-metrics assertions rely on the locally recorded run data, not the external tracking server.