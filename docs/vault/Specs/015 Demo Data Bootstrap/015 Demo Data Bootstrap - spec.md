---
title: 015 Demo Data Bootstrap - spec
type: spec
tags:
  - type/spec
spec-refs:
  - docs/vault/Specs/015 Demo Data Bootstrap/
related:
  - '[[015 Demo Data Bootstrap]]'
created: ~
updated: ~
---
# Feature Specification: Demo Data Bootstrap Guard

**Feature Branch**: `015-demo-data-bootstrap`
**Created**: 2026-06-19
**Status**: Draft
**Input**: User description: "ensure we only create the demo model data the first time we start up a new anvil environment. we can optionally support retriggering this from the ops menu"

## Clarifications

### Session 2026-06-19

- Q: How should the ops menu re-bootstrap button report results (success/error/summary) to the user? → A: Follow the existing ops page toast pattern (`showToast()`), consistent with all other ops action feedback. Brief green/red toast for success/error; button shows loading spinner during the API call; full result summary (created/skipped/error counts) logged to browser console for debugging.

### Session 2026-06-19 (Analysis Remediation)

- Q: How should FR-009 concurrency protection be implemented? → A: Two-layer approach: client-side button debouncing (button disable during request in T007) + server-side `asyncio.Lock` with HTTP 409 Conflict (T006). Resolves C1 ambiguity in original "or debouncing" phrasing.
- Q: How is FR-007 (warmup independence) verified? → A: T003 test includes assertion that when guard skips bootstrap, existing `origin="bundled"` entities satisfy warmup preconditions. T004 explicitly documents that the warmup runs in a separate daemon thread unaffected by the guard.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Fresh environment bootstraps demo data on first startup (Priority: P1)

A user starts anvil for the first time in a fresh environment (e.g., after `make setup`, a wiped Docker volume, or a brand-new installation). After the web UI loads, they see the demo dataset "Demo - medium/alice" and demo corpora available in the datasets and corpora lists without taking any manual action. On subsequent restarts of the application, the demo data is already present and the bootstrap process is skipped, resulting in faster startup times.

**Why this priority**: This is the core requirement — ensuring demo data exists for first-time users without imposing startup delay on repeat restarts. Without this, every startup pays the cost of re-checking or re-creating demo data.

**Independent Test**: Can be fully tested by (a) starting anvil in a clean environment and verifying demo data exists after startup, (b) restarting anvil and verifying startup completes faster with no duplicate demo data created, and (c) checking that exactly one set of demo entities exists, not duplicates.

**Acceptance Scenarios**:

1. **Given** a fresh environment with no existing demo data (no database or empty database), **When** the application starts up and completes its initialization, **Then** the demo corpora and datasets are created and visible in the application, and the startup duration is within normal bounds for data creation.
2. **Given** an environment where demo data was already created in a previous session, **When** the application starts up again, **Then** the bootstrap process is skipped, no duplicate demo entities are created, and startup completes faster than the initial bootstrap.
3. **Given** a user has manually deleted all demo-origin entities from the database, **When** the application restarts, **Then** the bootstrap process detects missing demo data and re-creates the bundled demo entities.

---

### User Story 2 - User re-triggers demo bootstrap from the ops menu (Priority: P2)

A user wants to restore missing demo data (e.g., after accidentally deleting it) or re-import demo data after upgrading to a new version of anvil that ships updated demo content. They navigate to the Operations page, find a "Re-bootstrap Demo Data" button in the System Actions section, and click it. The system re-runs the bootstrap process, creating any missing demo entities and reporting which were created and which already existed. Feedback follows the existing ops page toast pattern (`showToast()`): green toast on success with created/skipped counts, red toast on error, button shows loading spinner during the call.

**Why this priority**: Provides a self-service recovery mechanism without requiring CLI access or an application restart. Users don't need to know internal commands — they can fix missing demo data from the UI.

**Independent Test**: Can be fully tested by (a) loading the Operations page and verifying a "Re-bootstrap Demo Data" button exists in the System Actions section, (b) clicking the button and verifying demo entities are created or reported as already existing, (c) deleting one demo entity, clicking the button again, and verifying only the missing entity is re-created.

**Acceptance Scenarios**:

1. **Given** the application is running and demo data exists, **When** a user clicks the "Re-bootstrap Demo Data" button, **Then** the button shows a loading spinner, the API call completes, and a green toast appears showing "All demo entities already exist (6 skipped)".
2. **Given** some demo entities have been deleted from the database, **When** a user clicks the "Re-bootstrap Demo Data" button, **Then** the missing entities are re-created, and a green toast appears showing "Re-bootstrap complete: 2 created, 4 skipped".
3. **Given** the re-bootstrap is in progress, **When** the user observes the button, **Then** it shows a loading state and is disabled to prevent duplicate requests.
4. **Given** the API call fails (network error or server error), **When** the user clicks the button, **Then** a red toast appears showing the error message, and the button re-enables.

---

### User Story 3 - CLI bootstrap command respects first-run guard (Priority: P3)

An advanced user or system administrator runs `anvil bootstrap-datasets` from the command line. The command checks whether demo data already exists — if it does, it reports that bootstrap was skipped (with a dry-run option to preview). If it doesn't exist, it performs the bootstrap as before.

**Why this priority**: Consistency with the startup behavior. The CLI and auto-startup should use the same first-run detection logic so behavior is predictable regardless of how the application is invoked.

**Independent Test**: Can be tested by (a) running `anvil bootstrap-datasets` in a fresh environment and verifying demo data is created, (b) running it again and verifying it reports "already bootstrapped", and (c) using `--dry-run` to verify the detection logic without side effects.

**Acceptance Scenarios**:

1. **Given** a clean environment with no demo data, **When** a user runs `anvil bootstrap-datasets`, **Then** all bundled demo corpora and datasets are created, and the exit code is 0.
2. **Given** demo data already exists, **When** a user runs `anvil bootstrap-datasets`, **Then** the command reports "demo data already exists — skipped" and exits with code 0.
3. **Given** any environment state, **When** a user runs `anvil bootstrap-datasets --dry-run`, **Then** the command reports what would be created or skipped without making any changes.

---

### Edge Cases

- **Empty database, fresh install**: First startup should bootstrap demo data smoothly. The license catalog must be seeded before bootstrap so provenance FKs resolve.
- **Docker volume reset**: `make compose-reset` wipes the workspace volume. Next `make compose-up` should trigger a fresh bootstrap (empty DB detection).
- **Partial demo data**: If some but not all demo entities exist (e.g., user deleted one corpus), the bootstrap process should create only the missing entities without duplicating existing ones.
- **Concurrent re-trigger requests**: If the user rapidly clicks the re-bootstrap button, duplicate API calls should be prevented (debounced or locked).
- **Bootstrap failure during startup**: If bootstrap fails (e.g., DB connection issue), it should not crash the application. The error should be logged, and the user should be able to retry from the ops menu later.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST detect whether bundled demo data has already been bootstrapped on application startup, before deciding whether to run the bootstrap process.
- **FR-002**: The system MUST skip the automatic bootstrap on startup when demo data is already present, and MUST NOT create duplicate entities.
- **FR-003**: The system MUST provide a user-facing mechanism ("Re-bootstrap Demo Data") on the Operations page to manually trigger the bootstrap process on demand.
- **FR-004**: The system MUST expose an API endpoint that triggers the demo bootstrap process and returns a result summary (entities created, skipped, errors).
- **FR-005**: The CLI command `anvil bootstrap-datasets` MUST use the same first-run detection logic as the startup handler, and report whether bootstrap was performed or skipped.
- **FR-006**: The re-bootstrap action (ops menu or API) MUST be idempotent — running it multiple times must not create duplicate demo entities. Existing entities are skipped.
- **FR-007**: The demo model warmup process MUST proceed regardless of whether bootstrap runs on startup, as long as the demo training data is available (either freshly created or pre-existing).
- **FR-008**: The bootstrap check on startup MUST NOT block the application from becoming ready — if the check or bootstrap fails, the application continues with a logged warning.
- **FR-009**: The re-bootstrap API endpoint MUST prevent duplicate concurrent requests via a two-layer approach: (1) client-side button debouncing (disable button during request) and (2) server-side request-level lock (`asyncio.Lock`) that returns HTTP 409 Conflict if a bootstrap is already in progress.

### Key Entities *(include if feature involves data)*

- **BootstrapGuard**: Tracks whether demo data has been bootstrapped in this environment. Could be a simple database marker (e.g., a flag row or checking for existence of `origin="bundled"` entities) rather than a dedicated table. The detection logic must be reliable across container restarts, volume resets, and version upgrades.
- **BootstrapResult**: Result summary of a bootstrap operation, containing counts of corpora created, corpora skipped, datasets created, datasets skipped, and any errors encountered. Already exists in the current codebase.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: First application startup in a fresh environment creates all bundled demo entities (3 corpora, 3 datasets) within 30 seconds.
- **SC-002**: Subsequent application restarts complete startup 50% faster than the initial startup by skipping the bootstrap process.
- **SC-003**: Users can restore missing demo data from the Operations page in under 3 clicks (navigate to Ops → click Re-bootstrap → confirm success).
- **SC-004**: The re-bootstrap action, when all demo data already exists, completes in under 5 seconds and reports zero new entities created.
- **SC-005**: No duplicate demo entities appear in the database after 10 repeated re-bootstrap invocations.

## Assumptions

- **First-run detection via entity origin check**: Detection will be implemented by querying the database for existing entities with `origin="bundled"`, not by a dedicated bootstrap_metadata table. This is the simplest approach and works with the existing schema.
- **Re-trigger is not a hard reset**: Re-bootstrap will re-import only missing entities and skip existing ones. It will NOT delete and re-create existing demo entities. A "hard reset" (wipe and re-import) is out of scope for this feature.
- **No UI for delete-before-reimport**: The re-bootstrap button does not include a "delete all demo data first" option. Users who want a clean slate should delete entities individually.
- **CLI is secondary UX**: The primary re-trigger mechanism is the ops menu button. The CLI behavior change (respecting first-run guard) is for consistency, not a new feature.
- **Demo model warmup is independent**: The demo model warmup (training a 400-step model in background) is a separate process that depends on demo corpus data being present, not on the bootstrap trigger itself. It should continue to work whether data was created on this startup or pre-exists.
- **Docker compose-reset cleanup**: `make compose-reset` removes the workspace volume including the database, so the next startup naturally detects a fresh environment. No additional Docker-specific detection is required.