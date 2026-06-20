# Tasks: Demo Data Bootstrap Guard

**Input**: Design documents from `/specs/014-demo-data-bootstrap/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/rebootstrap-api.md

**Tests**: Included per Article IV (TDD Mandatory). Write tests FIRST (Red-Green-Refactor).

**Organization**: Tasks grouped by user story. Each story is independently testable.

## Format: `[ID] [P?] [Story] Description with file path`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: User story this task belongs to (US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

All paths are relative to repository root. This is a web application with backend code in `anvil/`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: No new project setup needed — all changes are edits to existing files.

No tasks required. Zero new dependencies, zero new files.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Repository query methods needed by the first-run guard in US1.

**⚠️ CRITICAL**: Must complete before any user story can begin.

- [x] T001 [P] Add `count_by_origin()` method to `CorpusRepository` in `anvil/db/repositories/corpora.py`

- [x] T002 [P] Add `count_by_origin()` method to `DatasetRepository` in `anvil/db/repositories/datasets.py`

**Checkpoint**: Both repositories now support `count_by_origin(origin: str) -> int` queries. Foundation ready.

---

## Phase 3: User Story 1 - Fresh environment bootstraps demo data on first startup (Priority: P1) 🎯 MVP

**Goal**: The lifespan handler guards the bootstrap call — runs only on first startup of a fresh environment. On subsequent restarts, detects existing `origin="bundled"` entities and skips the bootstrap.

**Independent Test**: Start app in empty DB → verify demo data exists. Restart app → verify no duplicate entities and startup is faster.

### Tests for User Story 1 (TDD — write first, expect failure)

- [x] T003 [P] [US1] Write `test_guard_skips_bootstrap_when_data_exists` in `tests/test_bootstrap.py` — bootstrap demo data, mock or seed DB to simulate existing state, then verify the guard check prevents a second `bootstrap_all()` call from creating duplicate entities. Also verify FR-007: assert that when guard skips bootstrap, the warmup model's precondition (corpus data available via existing `origin="bundled"` entities) is still satisfied so the demo model warmup can proceed independently.

### Implementation for User Story 1

- [x] T004 [US1] Add origin-based guard check in lifespan handler in `anvil/api/app.py` — before calling `DemoBootstrapService.bootstrap_all()`, query `CorpusRepository.count_by_origin("bundled")` and `DatasetRepository.count_by_origin("bundled")`. If both return 0, proceed with bootstrap. Otherwise, log debug message and skip. Ensure the guard does not block the demo model warmup thread (FR-007): the warmup proceeds in a separate daemon thread after the guard check, and its fallback logic (`_FALLBACK_CORPUS`) handles cases where no bootstrapped corpus is available.

**Checkpoint**: App starts with demo data on first run, skips on subsequent runs. No duplicate entities.

---

## Phase 4: User Story 2 - User re-triggers demo bootstrap from the ops menu (Priority: P2)

**Goal**: A "Re-bootstrap Demo" button in the Operations page System Actions section calls a new API endpoint to re-run demo bootstrap. Follows existing ops page toast pattern for feedback.

**Independent Test**: Click the button → verify toast with created/skipped counts. Delete one demo entity, click again → verify only missing entity is re-created.

### Tests for User Story 2 (TDD — write first, expect failure)

- [x] T005 [P] [US2] Write `test_rebootstrap_endpoint` in `tests/test_bootstrap.py` — use FastAPI `TestClient` to `POST /v1/demo/bootstrap`, verify 200 status and correct `BootstrapResult` field types in response. Then bootstrap again and verify all counts are 0 created (idempotent).

### Implementation for User Story 2

- [x] T006 [P] [US2] Add `POST /v1/demo/bootstrap` endpoint in `anvil/api/v1/health_ops.py` — handler receives `workbench: Annotated[AnvilWorkbench, Depends(get_workbench)]`, calls `workbench.demo().bootstrap_all()`, returns `result.model_dump()`. Match existing ops endpoint patterns (response dict, no HTTPException on success). Add server-side concurrency protection (FR-009): declare a module-level `_bootstrap_lock = asyncio.Lock()` and acquire it at the top of the handler. If the lock is already held, return `{"status": "busy", "message": "Bootstrap already in progress"}` with HTTP 409 Conflict instead of queuing.

- [x] T007 [US2] Add re-bootstrap button HTML and JS handler in `anvil/api/templates/operations.html` — insert `<button class="btn btn-secondary" onclick="ops.rebootstrapDemo()" id="btn-rebootstrap-demo">↻ Re-bootstrap Demo</button>` into the `div.ops-actions-bar` (System Actions section). Add `rebootstrapDemo: async function()` to the `window.ops` object following the `restartAll` pattern: `setBtnLoading()` → `fetch(POST /v1/demo/bootstrap)` → toast success/error (green with counts / red on error) → `setBtnLoading(false)`. This client-side button disable is the first layer of FR-009 concurrency protection (debouncing); the server-side `asyncio.Lock` in T006 is the second layer (request-level locking). Both layers together fully satisfy FR-009.

**Checkpoint**: Ops page shows Re-bootstrap Demo button. Clicking it triggers the API call and shows toast feedback. Idempotent — repeated clicks don't create duplicates.

---

## Phase 5: User Story 3 - CLI bootstrap command respects first-run guard (Priority: P3)

**Goal**: `anvil bootstrap-datasets` only prints the "Bootstrapping..." banner when entities were actually created. If all exist, it exits without fanfare (matching startup handler behavior).

**Independent Test**: Run CLI in empty DB → banner shown. Run again → no banner, exits cleanly.

### Tests for User Story 3 (TDD — write first, expect failure)

- [x] T008 [P] [US3] Write `test_cli_banner_conditional` in `tests/test_bootstrap.py` — call the `_run()` helper or `bootstrap_datasets_main()` in a test context with a populated DB, capture stdout, verify "Bootstrapping demo data" is NOT printed. Then test with empty DB and verify it IS printed.

### Implementation for User Story 3

- [x] T009 [US3] Add conditional banner in `bootstrap_datasets_main()` in `anvil/cli.py` — restructure the live mode (non-dry-run) flow: call `bootstrap_all()` first, then only print "Bootstrapping demo data from data/demo/..." if `bootstrap.corpora_created > 0 or bootstrap.datasets_created > 0`. The summary print should always run (shows created/skipped counts regardless).

**Checkpoint**: CLI output matches startup handler behavior — banner only when work was done.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Quality verification across all changes.

- [x] T010 Run `make lint` and fix any lint violations in changed files
- [x] T011 Run `make typecheck` (mypy --strict) and fix any type errors in changed files
- [x] T012 Run `make test` and verify all tests pass (including new tests)
- [x] T013 [P] Update vault documentation in `docs/vault/Sessions/` with a session log for this feature

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No tasks needed — can start with Phase 2
- **Foundational (Phase 2)**: BLOCKS all user stories — repository methods must exist first
- **User Story 1 (Phase 3)**: Depends on Phase 2 — uses `count_by_origin()` in repositories
- **User Story 2 (Phase 4)**: Depends on Phase 2 only — no dependency on US1 (the endpoint calls `bootstrap_all()` directly without the guard)
- **User Story 3 (Phase 5)**: Depends on Phase 2 only — no dependency on US1 or US2 (CLI uses its own session)
- **Polish (Phase 6)**: Depends on all user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Phase 2 — No dependency on other stories
- **User Story 2 (P2)**: Can start after Phase 2 — Independently testable from US1 and US3
- **User Story 3 (P3)**: Can start after Phase 2 — Independently testable from US1 and US2

### Within Each User Story

- Tests written and FAIL before implementation
- Implementation tasks within a story follow backend → frontend order
- Story complete before moving to next priority
- Each story's test runs independently (different assertions)

### Parallel Opportunities

- **T001, T002**: Can run in parallel (different repository files)
- **T003, T005**: Can run in parallel (different test concerns in same file — but tests for different stories)
- **T006, T007**: Can run in parallel (different files: health_ops.py vs operations.html)
- **All user stories**: Can be implemented in parallel after Phase 2 completes (they touch different files)

---

## Parallel Example: User Story 2

```bash
# Launch backend endpoint + frontend simultaneously:
Task: "Add POST /v1/demo/bootstrap endpoint in anvil/api/v1/health_ops.py"
Task: "Add re-bootstrap button and JS handler in anvil/api/templates/operations.html"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 2: Foundational (repository methods)
2. Complete Phase 3: User Story 1 (lifespan guard)
3. **STOP and VALIDATE**: Test US1 independently — start app in fresh DB, restart, verify no duplicates
4. At this point, the core requirement (FR-001, FR-002, FR-007, FR-008) is delivered

### Incremental Delivery

1. **Phase 2** → Foundation ready (repository methods with `count_by_origin()`)
2. **Phase 3 (US1)** → Test independently → **MVP complete!** (first-run guard works)
3. **Phase 4 (US2)** → Test independently → ops menu re-trigger added
4. **Phase 5 (US3)** → Test independently → CLI consistency added
5. **Phase 6** → All gates pass (lint, typecheck, tests)

### Sequential (Single Developer)

1. T001, T002 (parallel repository methods)
2. T003 (test guard)
3. T004 (implement guard)
4. T005 (test endpoint)
5. T006, T007 (parallel endpoint + frontend)
6. T008 (test CLI)
7. T009 (implement CLI)
8. T010—T013 (polish)

---

## Summary

| Metric | Value |
|--------|-------|
| Total tasks | 13 |
| Parallelizable tasks | 5 (T001, T002, T003, T005, T006, T008) |
| Core tasks (T001–T009) | 9 |
| Polish tasks (T010–T013) | 4 |
| Test tasks | 3 (T003, T005, T008) |
| Implementation tasks | 6 (T001, T002, T004, T006, T007, T009) |
| MVP scope | Phases 2 + 3 (T001–T004) |
| Files changed | `corpora.py`, `datasets.py`, `app.py`, `health_ops.py`, `operations.html`, `cli.py`, `test_bootstrap.py` |
| **Findings addressed** | **C1** (server-side asyncio.Lock in T006), **C2** (warmup verification in T003+T004), **C3** (implicit in system), **D1** (tightened FR-009 via two-layer lock in T006+T007) |

