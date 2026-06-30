# Tasks: Degraded Mode Recovery

**Input**: Design documents from `docs/vault/Specs/057-degraded-mode-recovery/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Included per TDD mandate (Constitution Article IV) — tests written before implementation (Red-Green-Refactor).

**Organization**: Tasks grouped by user story for independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2)
- Include exact file paths in descriptions

## Path Conventions

- **Single project**: paths relative to repository root
- Existing source under `anvil/`, tests under `tests/`

---

## Phase 1: Setup

**Purpose**: New file scaffolding and dependency verification

- [x] T001 Create `anvil/services/tracking/tracking_status.py` with DegradedReason (StrEnum), DegradedState (BaseModel), and TrackingStatus (BaseModel) as defined in data-model.md
- [x] T002 [P] Verify MLflow exception classes are importable (`from mlflow.exceptions import MlflowException`, `RestException`) — document the MRO for exception narrowing

---

## Phase 2: Foundational (Core TrackingService Refactor)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented. Addresses Issues 3, 4, 5, 6, 7.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T003 Write failing unit tests for narrowed exception handling in `tests/unit/services/test_tracking_degraded.py` — verify `MlflowException` and `ConnectionError` enter degraded mode, `TypeError` and `AttributeError` propagate
- [x] T004 [P] Write failing unit tests for separated run_id gate — verify empty run_id raises `ValueError` instead of silent no-op in `tests/unit/services/test_tracking_degraded.py`
- [x] T005 [P] Write failing unit tests for failure mode differentiation — verify each DegradedReason maps to the correct exception type in `tests/unit/services/test_tracking_degraded.py`
- [x] T006 [P] Write failing unit tests for thread safety — verify concurrent `start_run()` calls with `asyncio.gather` don't corrupt state in `tests/unit/services/test_tracking_degraded.py`
- [x] T007 [P] Write failing unit tests for logging on state transitions — verify WARN log emitted on degraded entry/exit in `tests/unit/services/test_tracking_degraded.py`
- [x] T008 Refactor `TrackingService.__init__` in `anvil/services/tracking/tracking.py` — replace `self._degraded: bool` with `self._state: DegradedState`, add `self._lock: asyncio.Lock`, import `tracking_status.py`
- [x] T009 Rewrite `TrackingService._lazy_init()` in `anvil/services/tracking/tracking.py` — catch `(MlflowException, ConnectionError, TimeoutError, OSError)`, classify failure via DegradedReason, set DegradedState accordingly. All other exceptions propagate. Use `asyncio.Lock` for thread-safe state mutation.
- [x] T010 Narrow exception handling in ALL other TrackingService methods (`log_metric`, `log_artifacts`, `set_tag`, `finish_run`, `fail_run`, `log_dataset_input`, `log_corpus_input`, `register_source_model`, `get_safetensors_artifacts`, `list_experiments`, `get_experiment`, `list_registered_models`, `log_dataset_lifecycle_event`, `log_corpus_lifecycle_event`) in `anvil/services/tracking/tracking.py` — replace `except Exception: pass` with `except (MlflowException, ConnectionError, TimeoutError, OSError): pass`
- [x] T011 Separate the degraded gate from the run_id validation gate in ALL TrackingService methods in `anvil/services/tracking/tracking.py` — split `if self._degraded or not run_id: return` into two independent checks: degraded gate returns empty/default, empty run_id raises `ValueError`
- [x] T012 [P] Add WARN-level logging on state transitions in `TrackingService` in `anvil/services/tracking/tracking.py` — every entry/exit of degraded mode logs the DegradedReason
- [x] T013 [P] Add `@property is_degraded` and `@property tracking_status` accessors to `TrackingService` in `anvil/services/tracking/tracking.py` — expose current DegradedState for health endpoint consumption

**Checkpoint**: Foundation ready — core tracking service refactored. All exception handling narrowed, gates separated, state machine operational, thread-safe, logged. Unit tests passing.

---

## Phase 3: User Story 1 — Automatic Recovery from Transient MLflow Outage (Priority: P1) 🎯 MVP

**Goal**: After a transient MLflow outage, the tracking service automatically retries, reconnects, and resumes logging without user intervention.

**Independent Test**: Start app, simulate MLflow outage (stop MLflow), trigger tracking operation → enters degraded mode, restart MLflow, trigger tracking operation → service recovers, logs data, exits degraded mode.

- [x] T014 Write failing unit tests for retry logic in `tests/unit/services/test_tracking_degraded.py` — verify exponential backoff with jitter, verify recovery when MLflow becomes reachable again
- [x] T015 Add `_maybe_reconnect()` method to `TrackingService` in `anvil/services/tracking/tracking.py` — implements exponential backoff with jitter (1s initial, 2× multiplier, 30s cap, ±25% jitter). Only retries when `DegradedReason.UNREACHABLE`.
- [x] T016 [P] Update `_lazy_init()` to call `_maybe_reconnect()` before returning the cached client in `anvil/services/tracking/tracking.py` — if client exists but service is degraded, attempt retry
- [x] T017 [P] Reset `retry_count` to 0 and transition state to `active` when retry succeeds in `anvil/services/tracking/tracking.py`

**Checkpoint**: US1 complete. Automatic recovery from transient outages operational. `_maybe_reconnect()` retries with backoff and recovers.

---

## Phase 4: User Story 2 — Visible Tracking Status (Priority: P2)

**Goal**: Users can clearly see whether tracking is active or degraded via the health endpoint and persistent UI banners.

**Independent Test**: Check `GET /v1/health/detailed` returns `tracking` block with correct status. Simulate degraded mode and verify UI banner appears on Experiments, Training, Model Registry, and Operations pages.

- [x] T018 Write failing tests for tracking block in health endpoint in `tests/e2e/test_tracking_degraded.py` — verify `GET /v1/health/detailed` includes `tracking` block with correct `status` and `reason`
- [x] T019 Update `GET /v1/health/detailed` in `anvil/api/v1/health_ops.py` — import `get_workbench`, access `workbench.tracking.tracking_status`, add `tracking` block to response dict
- [x] T020 Add degraded banner HTML to `base.html` in `anvil/api/templates/base.html` — add `{% block degraded_banner %}` with `section-card--banner` warning pattern (⚠ icon, `--accent-warn` color), hidden by default via inline `style="display:none"`
- [x] T021 [P] [US2] Add degraded banner JS logic to training page in `anvil/api/templates/archetypes/training.html` — on page load, fetch `/v1/health/detailed`, show banner if `data.tracking.status === 'degraded'`
- [x] T022 [P] [US2] Add degraded banner JS logic to experiments page in `anvil/api/templates/experiments.html` — same pattern as T021
- [x] T023 [P] [US2] Add degraded banner JS logic to model registry page in `anvil/api/templates/archetypes/models.html` — same pattern as T021
- [x] T024 [P] [US2] Add degraded banner JS logic to operations page in `anvil/api/templates/operations.html` — same pattern as T021. Also update `GET /v1/services` consumption to reflect tracking status.
- [x] T025 [P] [US2] Update `POST /v1/training` response in `anvil/api/v1/training.py` — ensure `"tracking": "degraded"` key still present when degraded (already implemented, verify unchanged)

**Checkpoint**: US2 complete. Health endpoint exposes tracking status. All 4 target pages show persistent degraded banner when tracking is off.

---

## Phase 5: Polish & Cross-Cutting Concerns

**Purpose**: Verification, cleanup, and validation

- [x] T026 Write e2e test for end-to-end degraded mode cycle in `tests/e2e/test_tracking_degraded.py` — start app, verify active status, simulate MLflow outage, verify degraded status + UI banner, restart MLflow, verify recovery
- [x] T027 [P] Write stress test for concurrent tracking calls with `asyncio.gather`(10) in `tests/unit/services/test_tracking_degraded.py` — verify no data races or inconsistent DegradedState (SC-005)
- [x] T028 Run `make lint`, `make typecheck`, `make test` — fix any regressions. Verify no new type errors from the `exceptions` import changes.
- [x] T029 [P] **UX compliance gate**: run `make ux-lint` on all changed templates — must pass GATE: PASS before merge
- [x] T030 Update vault session log (`docs/vault/Sessions/`) with summary of tracking degraded behavior changes

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS all user stories
- **US1 Recovery (Phase 3)**: Depends on Foundational — builds on refactored TrackingService
- **US2 Visible Status (Phase 4)**: Depends on Foundational, independent of US1
- **Polish (Phase 5)**: Depends on all user stories complete

### User Story Dependencies

- **US1 (P1)**: Can start after Foundational — no dependency on other stories
- **US2 (P2)**: Can start after Foundational — independent of US1
- **US3 & US4**: Addressed in Foundational phase (exception narrowing, run_id gate) — these are internal code quality concerns of TrackingService itself, so they're folded into Phase 2 rather than getting dedicated phases. Their P2/P3 priorities from the spec are reflected in their placement in Phase 2 (foundational, blocks all other work).

### Within Each Phase

- Tests MUST be written and FAIL before implementation (TDD)
- Models/types before services
- Services before endpoints/routes
- Story complete before moving to next priority

### Parallel Opportunities

- **Phase 1**: T001 and T002 can run in parallel
- **Phase 2**: T003-T007 (test writing) can all run in parallel. T012 and T013 can run in parallel with T009-T011.
- **Phase 3**: T014 (tests) must come before T015-T017. T016 and T017 can run in parallel after T015.
- **Phase 4**: T018 (test) before T019 (health endpoint). T021-T025 (per-page banners) can all run in parallel after T020 (base template banner).
- **Phase 5**: T026 can run in parallel with T027. Both depend on all prior phases.

---

## Parallel Example: Foundational Phase (Phase 2)

```bash
# Launch all test-writing tasks in parallel:
Task: "Write failing unit tests for narrowed exception handling in tests/unit/services/test_tracking_degraded.py"
Task: "Write failing unit tests for separated run_id gate in tests/unit/services/test_tracking_degraded.py"
Task: "Write failing unit tests for failure mode differentiation in tests/unit/services/test_tracking_degraded.py"
Task: "Write failing unit tests for thread safety in tests/unit/services/test_tracking_degraded.py"
Task: "Write failing unit tests for logging on state transitions in tests/unit/services/test_tracking_degraded.py"
```

## Parallel Example: Visible Tracking Status (Phase 4)

```bash
# After T019 (health endpoint) is done, launch per-page banners in parallel:
Task: "Add degraded banner to training page in anvil/api/templates/archetypes/training.html"
Task: "Add degraded banner to experiments page in anvil/api/templates/experiments.html"
Task: "Add degraded banner to model registry page in anvil/api/templates/archetypes/models.html"
Task: "Add degraded banner to operations page in anvil/api/templates/operations.html"
```

---

## Implementation Strategy

### MVP First (Phase 1 → 2 → 3)

1. Complete Phase 1: Setup (tracking_status.py)
2. Complete Phase 2: Foundational (core TrackingService refactor — exception narrowing, state machine, lock, run_id gate)
3. Complete Phase 3: US1 — Automatic Recovery (retry logic)
4. **STOP and VALIDATE**: Test US1 independently — recovery from transient MLflow outage works

### Incremental Delivery

1. Phase 1 + 2 complete → Core tracking service production-ready (no more silent bug swallowing, thread-safe)
2. Add Phase 3 → Automatic recovery deployed (MVP — no more permanent data loss from transient blips)
3. Add Phase 4 → Users get visibility into tracking status (UI indicators + health endpoint)

### Single-Developer Strategy

With a single developer:

1. Complete Phase 1 → 2 → 3 → 4 → 5 sequentially
2. Each phase delivers independently testable value
3. Stop after Phase 3 if time-constrained: the highest-impact fix (data loss prevention) is done

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story is independently completable and testable
- Verify tests fail before implementing (TDD)
- This feature does NOT require Alembic migrations, new dependencies, or schema changes
- The `experiment-tracking.js` widget's existing degraded mode simulation is an interactive lesson feature, not a replacement for the persistent UI banner