# Tasks — 074 Remove Module-Level Mutable State

**TDD order. Coordinate with spec 069 (queue helpers).**

## Phase 0 — Investigate
- [ ] T001 Map all accessors of `_tasks` and `_injection_queue` (context.md grep commands).
- [ ] T002 Determine ownership: does `TrainingService` own the queue, or the route module? Coordinate with spec 069.

## Phase 1 — training._tasks → app.state (Red-Green)
- [ ] T010 **[Red]** `test_training_tasks_in_app_state` — after app startup, `app.state.training_tasks == {}`; not present as module global.
- [ ] T011 **[Green]** Initialize `app.state.training_tasks` in lifespan startup; update all `training.py` accessors to `request.app.state.training_tasks`. Remove module global (line 128).
- [ ] T012 **[Green]** Add shutdown cleanup (cancel outstanding tasks) in lifespan.

## Phase 2 — fine_tune_datasets._tasks
- [ ] T020 **[Red]** `test_fine_tune_tasks_in_app_state`.
- [ ] T021 **[Green]** Move to `app.state.fine_tune_tasks`; remove module global (line 42).

## Phase 3 — content._injection_queue
- [ ] T030 **[Red]** `test_content_queue_in_app_state`.
- [ ] T031 **[Green]** Move to `app.state.content_injection_queue`; remove module global (line 60); drain on shutdown.

## Phase 4 — Test isolation
- [ ] T040 Verify tests no longer depend on module-global state; two tests in any order see clean state.

## Phase 5 — Gates
- [ ] T050 `grep -rn "^_tasks\|^_injection_queue" anvil/api/v1/` returns nothing.
- [ ] T051 `make lint && make typecheck && make test`.

## Verification (Success Criteria)
- SC-001: zero module-level mutable dict/queue in `anvil/api/v1/`.
- SC-002: task tracking initialized in lifespan, cleaned on shutdown.
- SC-003: tests order-independent.
- SC-004: mypy --strict clean.
