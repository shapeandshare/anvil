# Feature Specification: Degraded Mode Recovery

**Feature Directory**: `docs/vault/Specs/057-degraded-mode-recovery`
**Created**: 2026-06-29
**Status**: Implemented
**Input**: User description: "Resolve all 7 issues in the MLflow TrackingService degraded mode — add recovery from transient failure, strengthen user signal, narrow exception handling, decouple guards, differentiate failure modes, and add thread safety."

## Clarifications

### Session 2026-06-29

- Q: Retry backoff strategy for MLflow reconnection attempts? → A: Exponential backoff with jitter (1s initial, 2× multiplier, 30s cap, random jitter ±25%).
- Q: How should "recovering" state be surfaced in the UI? → A: No separate recovering state in the UI. Show "degraded" status until recovery is confirmed. The recovering/reconnecting phase is internal to the service.
- Q: Should the tracking status have a dedicated endpoint or be part of an existing one? → A: Add a `tracking` block to the existing authenticated `GET /v1/health/detailed` response, alongside the existing `mlflow` block. Also include `GET /v1/services` consumption as in-scope so the operations page displays tracking status.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Automatic Recovery from Transient MLflow Outage (Priority: P1)

A user has the application running with MLflow tracking as a supervised sidecar. MLflow briefly restarts (upgrade, crash, resource re-schedule). After MLflow comes back online, the next tracking operation automatically reconnects and resumes logging without the user taking any action.

**Why this priority**: Data loss prevention is the highest-severity issue. Currently, a 2-second blip permanently disables tracking for the entire process lifetime, silently losing experiment data for all subsequent runs.

**Independent Test**: Can be tested by starting the app, simulating an MLflow outage (stop the MLflow server), waiting for a tracking operation to enter degraded mode, restarting MLflow, then verifying the next tracking operation succeeds and data appears in the experiment log.

**Acceptance Scenarios**:

1. **Given** the tracking service has entered degraded mode due to MLflow being unreachable, **When** MLflow becomes reachable again and a user starts a new training run, **Then** the tracking service successfully reconnects, logs the run parameters, and exits degraded mode.
2. **Given** the tracking service is in degraded mode, **When** any tracking method is called (log_metric, log_artifacts, etc.), **Then** it periodically retries the MLflow connection rather than permanently short-circuiting.
3. **Given** the tracking service has recovered from degraded mode, **When** subsequent MLflow operations succeed, **Then** the service remains in active mode and does not re-enter degraded mode unless a new failure occurs.

---

### User Story 2 — Visible Tracking Status (Priority: P2)

A user wants to know whether experiment tracking is actively logging data or silently degraded, without having to inspect specific API responses. The status is visible persistently in the UI and accessible via a dedicated API endpoint.

**Why this priority**: Users currently experience silent data loss — the experiments page shows empty, model registry is blank, and artifacts vanish. They have no way to distinguish "no data" from "tracking is off."

**Independent Test**: Can be tested by checking that `GET /v1/health/detailed` returns the correct degraded/active state, and by navigating through the UI to verify a persistent status indicator (e.g., a banner, badge, or toast) is visible on pages that depend on tracking.

**Acceptance Scenarios**:

1. **Given** the tracking service is in degraded mode, **When** a user navigates to the Experiments page, **Then** a clear, persistent visual indicator (e.g., in-page banner) is shown explaining tracking is off and suggesting possible actions.
2. **Given** the tracking service is in degraded mode, **When** a user navigates to the Model Registry page, **Then** the page shows a similar persistent indicator that registry data is unavailable due to degraded tracking.
3. **Given** the tracking service is in degraded mode, **When** a user starts a training run, **Then** the training run page displays a persistent warning that experiment data is not being logged.
4. **Given** the tracking service is in degraded mode, **When** a user or monitoring tool queries `GET /v1/health/detailed`, **Then** the response includes a `tracking` block with the current degraded status and a human-readable reason.

---

### User Story 3 — Exceptions Surface Real Bugs (Priority: P2)

A developer encounters an issue where tracking operations fail. They want genuine programming errors (type errors, null references, misconfiguration) to surface as exceptions rather than being silently swallowed, while expected MLflow connectivity failures still enter degraded mode gracefully.

**Why this priority**: Currently, `except Exception` at every call site swallows type errors, attribute errors, and any real bug, making tracking issues extremely difficult to debug. Training completes successfully but data never reaches MLflow — with no error signal.

**Independent Test**: Can be tested by injecting a controlled error (e.g., passing an invalid parameter type) into a tracking call and verifying the exception propagates rather than being silently caught.

**Acceptance Scenarios**:

1. **Given** a developer-written bug in tracking code (e.g., referencing an undefined variable in a parameter), **When** the tracking method executes, **Then** the exception propagates out of the tracking service (is not silently caught) so developers can detect and fix the bug.
2. **Given** an MLflow connection error occurs during a tracking operation, **When** the error is a known MLflow connectivity exception, **Then** the service either enters degraded mode (first occurrence) or silently skips the operation (while degraded).
3. **Given** an unexpected exception type that is neither an MLflow connectivity error nor a known runtime exception, **When** the exception occurs, **Then** it propagates rather than being swallowed, preserving debuggability.

---

### User Story 4 — Empty run_id Does Not Silently No-Op (Priority: P3)

A developer accidentally passes an empty string as a run_id to a tracking method. They want the error to surface as an exception or at minimum to be logged, rather than silently returning and making it appear the operation succeeded.

**Why this priority**: The current `if not run_id` gate is coupled to the degraded-mode convention that `start_run()` returns `""`. Any caller passing an empty run_id for any other reason (bug, data issue) silently no-ops, making debugging extremely confusing.

**Independent Test**: Can be tested by calling any tracking method with an explicitly empty run_id and verifying the call either raises an error or logs a warning.

**Acceptance Scenarios**:

1. **Given** a caller passes an empty string as `run_id` to a tracking method, **When** the method executes, **Then** it does not silently return — it either raises a `ValueError` or logs a warning with diagnostic context.
2. **Given** the tracking service is in degraded mode, **When** `start_run()` returns `""`, **Then** subsequent calls with that empty run_id are still properly handled (the check for empty run_id is independent of the degraded mode check).

---

### Edge Cases

- **Multiple concurrent start_run() calls**: Two training runs start simultaneously. Both attempt to contact MLflow. Both fail. The thread-safe flag setter ensures only one writer modifies the shared state at a time.
- **MLflow recovers mid-operation**: A `log_artifact` call times out. The next call retries the connection, succeeds, and the artifact is logged to the now-reachable server.
- **MLflow version mismatch**: The server is reachable but returns a version incompatibility error. This is a non-transient failure — the service enters degraded mode with reason `"incompatible_version"` and does not retry.
- **Simultaneous degraded and active operations**: One training run's tracking succeeds while another's fails. The degraded state is per-service-instance, so one run's tracking failure does not disable tracking for the other.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001 (Recovery from transient failure)**: The tracking service MUST periodically retry the MLflow connection after entering degraded mode, so that a transient outage does not permanently disable tracking for the process lifetime. At minimum, the first tracking operation after entering degraded mode MUST attempt reconnection. Retries MUST use exponential backoff with jitter (1s initial delay, 2× multiplier, 30s maximum delay, random jitter ±25%).
- **FR-002 (Permanent failure detection)**: Certain failure types (e.g., version incompatibility, authentication rejection) MUST be classified as permanent and MUST NOT trigger retry. The service enters degraded mode without recovery for these cases.
- **FR-003 (Tracking status on health endpoint)**: The authenticated `GET /v1/health/detailed` endpoint MUST include a `tracking` block in its response with the current tracking service status (active/degraded), a machine-readable reason code, and a human-readable description. No separate dedicated endpoint is needed. The separate bare `GET /v1/health` liveness check is unaffected.
- **FR-013 (Operations page tracking status)**: The operations page, which consumes both `GET /v1/health/detailed` and `GET /v1/services`, MUST display the tracking degraded status when the tracking service is in degraded mode.
- **FR-004 (Persistent UI indicator — Experiments page)**: When the tracking service is degraded, the Experiments page MUST display a persistent, clearly visible banner or indicator explaining that experiment tracking is offline and suggesting next steps (e.g., check MLflow server status).
- **FR-005 (Persistent UI indicator — Training page)**: When the tracking service is degraded, the Training run start page and active run page MUST display a visible warning that experiment data will not be logged.
- **FR-006 (Persistent UI indicator — Model Registry page)**: When the tracking service is degraded, the Model Registry page MUST display an indicator that registry data is unavailable due to degraded tracking.
- **FR-007 (Narrowed exception handling — start_run)**: The `start_run()` method MUST catch only known MLflow connectivity exceptions (connection errors, timeouts, server errors) when entering degraded mode. Unexpected exceptions (type errors, attribute errors, null references) MUST propagate to the caller.
- **FR-008 (Narrowed exception handling — all other methods)**: All other tracking methods (`log_metric`, `log_artifacts`, `set_tag`, `finish_run`, `fail_run`, etc.) MUST catch only known MLflow connectivity exceptions. Unexpected exceptions MUST propagate. The silent `except Exception: pass` pattern MUST be replaced with targeted exception handling.
- **FR-009 (Separation of run_id gate from degraded gate)**: The check for empty `run_id` MUST be separated from the check for degraded mode. An empty `run_id` passed to any tracking method MUST either raise a `ValueError` or log a diagnostic warning — it MUST NOT silently no-op.
- **FR-010 (Failure mode differentiation)**: The tracking service MUST distinguish between different failure causes using an enumeration or similar typed mechanism. At minimum: `unreachable` (connection/timeout), `incompatible_version`, `auth_failure`, `unknown`. This reason MUST be exposed via the status API endpoint (FR-003).
- **FR-011 (Thread-safe state mutation)**: All mutations to internal tracking service state (_degraded, _client, _experiment_id, degraded_reason) MUST be synchronized so that concurrent access from multiple `run_in_executor` threads does not produce race conditions or undefined behavior.
- **FR-012 (Logging on state transitions)**: Every transition into or out of degraded mode MUST produce a log entry at WARN level or above, including the reason for the transition.

### Key Entities *(include if feature involves data)*

- **DegradedState**: Captures the current tracking service health — `active` or `degraded` (with reason). An internal `recovering` phase exists during retry but is not exposed as a separate UI state; the status endpoint reports `degraded` until the retry succeeds and the service transitions back to `active`.
- **DegradedReason**: Enumeration of failure causes: `unreachable`, `incompatible_version`, `auth_failure`, `permanent_error`, `unknown`. Used by the status API and UI to surface actionable information.
- **TrackingStatus**: Response block returned inside `GET /v1/health/detailed`, containing: `status` (active/degraded), `reason` (DegradedReason or null), `message` (human-readable string), `last_attempt` (timestamp).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: After a transient MLflow outage of up to 30 seconds, the tracking service automatically recovers and logs the next run's data without manual intervention. Verified by: stop MLflow for 10 seconds, start it again, start a training run, verify data appears in the experiment log.
- **SC-002**: A user can determine whether tracking is active or degraded by checking the `GET /v1/health/detailed` response (e.g., via the operations page), without inspecting individual API responses. Verified by: query the health endpoint while tracking is degraded and confirm a clear active/degraded reason in the response.
- **SC-003**: A user viewing any page that depends on tracking (Experiments, Model Registry, Training) during degraded mode sees a persistent visual indicator explaining the situation. Verified by: navigate to each page while tracking is degraded and confirm the indicator is present.
- **SC-004**: A developer can inject a controlled bug (e.g., TypeError in a tracking parameter) and the exception propagates out of the tracking service instead of being silently swallowed. Verified by: unit test that calls log_metric with an invalid argument type and expects the exception to propagate.
- **SC-005**: The tracking service handles 10 concurrent tracking calls without data races or inconsistent state. Verified by: stress test that spawns 10 parallel attempts and verifies all internal state transitions are consistent.
- **SC-006**: Every transition into or out of degraded mode produces a WARN-level log entry. Verified by: inspecting logs after simulating an MLflow outage and recovery.

## Assumptions

- MLflow is run as a supervised sidecar process managed by the application. The app does not control the MLflow process externally.
- A "transient outage" is defined as MLflow being unreachable for up to 30 seconds. Outages longer than this threshold are still recoverable but may lose data for operations attempted during the outage.
- The priority of these fixes is: data recovery (Issue 1) > user visibility (Issue 2) > error transparency (Issues 3, 4, 5) > diagnosability (Issue 6) > thread safety (Issue 7).
- The UI indicator for degraded mode will reuse existing patterns in the project (Jinja2 templates, token-based CSS classes) — no new frontend framework is introduced.
- The "training page" includes the training configuration/start page and the active run monitoring page (dashboard).
- Thread safety is achieved via a single lock rather than per-method synchronization, matching the existing async execution model.
