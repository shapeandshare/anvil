# Feature Specification: Remove Module-Level Mutable State from Routes

**Feature Branch**: `opencode/witty-forest`  
**Created**: 2026-07-18  
**Status**: Draft  
**Priority**: P1  
**Input**: Codebase review finding #074 — `training.py:128` has `_tasks: dict[int, asyncio.Task[Any]]` (in-memory task registry), `fine_tune_datasets.py:42` has the same pattern, and `content.py:60` has `_injection_queue: asyncio.Queue[dict[str, str]]`. This is module-level mutable state that prevents horizontal scaling and complicates testing.

## User Scenarios & Testing

### User Story 1 - State lives in application context (Priority: P1)

In-memory task registries and queues are stored in `request.app.state` rather than as module-level variables, so they are tied to the application lifecycle.

**Why this priority**: Module-level mutable state is a concurrency hazard — it is shared across all requests, all workers, and cannot be properly cleaned up. Moving to `app.state` makes the lifecycle explicit and enables future horizontal scaling.

**Independent Test**: A test creates a fresh application instance and verifies that task tracking is empty before any requests and properly cleaned up after.

**Acceptance Scenarios**:

1. **Given** a new FastAPI application instance is created, **When** it starts, **Then** `app.state.training_tasks` is an empty dict.
2. **Given** a training run starts, **When** it registers a task, **Then** the task appears in `app.state.training_tasks` (not in a module-level `_tasks` dict).
3. **Given** a training run completes or errors, **When** cleanup runs, **Then** the task is removed from `app.state.training_tasks`.

---

### User Story 2 - Test isolation without module state (Priority: P2)

Tests can create multiple application instances without shared task state bleeding between them.

**Why this priority**: Module-level state makes tests order-dependent. If test A creates a task and test B doesn't clean it, test C sees stale state. Moving to `app.state` scopes state per application instance.

**Independent Test**: Two test cases run in any order and each sees an empty initial task registry.

**Acceptance Scenarios**:

1. **Given** test A creates training tasks, **When** test B starts, **Then** it sees an empty task registry (no bleed from test A).

### Edge Cases

- The `Tasks` dict is accessed from in-process async tasks (background training). What if the app is shut down while tasks are running? Need cleanup in lifespan shutdown.
- What about the `asyncio.Queue` in `content.py:60`? Same pattern — move to `app.state.content_injection_queue`.

## Requirements

### Functional Requirements

- **FR-001**: The `_tasks: dict[int, asyncio.Task[Any]]` in `training.py` MUST be moved to `app.state.training_tasks`.
- **FR-002**: The `_tasks: dict[int, asyncio.Task[Any]]` in `fine_tune_datasets.py` MUST be moved to `app.state.fine_tune_tasks`.
- **FR-003**: The `_injection_queue: asyncio.Queue[dict[str, str]]` in `content.py` MUST be moved to `app.state.content_injection_queue`.
- **FR-004**: The application lifespan handler MUST initialize these state items on startup and clean them up on shutdown.
- **FR-005**: Routes MUST access these via `request.app.state.<name>` instead of module-level references.
- **FR-006**: All accessor helper functions (e.g., `get_tasks()`, `get_queue()`) MUST be updated to receive `app.state` or `request` instead of reading module globals.
- **FR-007**: Tests MUST be updated to avoid monkey-patching module-level state — use `app.state` manipulation instead.

### Key Entities

- **training._tasks**: Task registry for training runs
- **fine_tune_datasets._tasks**: Task registry for fine-tuning jobs
- **content._injection_queue**: Queue for content injection

## Success Criteria

### Measurable Outcomes

- **SC-001**: Zero module-level mutable dict/list/queue instances in `anvil/api/v1/` that hold request-scoped or app-scoped state.
- **SC-002**: All task tracking initialized in lifespan, cleaned up in shutdown.
- **SC-003**: `make test` passes — tests do not depend on order due to module state.
- **SC-004**: mypy --strict passes.

## Assumptions

- The tasks are genuinely in-process (not distributed), so `app.state` is appropriate.
- The content injection queue serves a similar purpose and can coexist in `app.state`.
- The training module's `get_queue` and `release_queue` functions receive `app.state` as a parameter.
