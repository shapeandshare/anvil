# Feature Specification: Remove asyncio.run() Blocking Call from TrainingService

**Feature Branch**: `opencode/witty-forest`  
**Created**: 2026-07-18  
**Status**: Draft  
**Priority**: P0  
**Input**: Codebase review finding #068 — `TrainingService._load_docs()` calls `asyncio.run(_load())` inside a sync method, which blocks the calling thread in an async-first codebase. This violates Article V (Async-First) of the Constitution.

## User Scenarios & Testing

### User Story 1 - Non-blocking doc loading (Priority: P1)

When training starts and the service loads documents, the event loop should not be blocked. The async call chain should flow naturally without `asyncio.run()`.

**Why this priority**: `asyncio.run()` creates a new event loop and blocks the current thread until complete. In a FastAPI async context, this can cause deadlocks, thread exhaustion, and degraded concurrency. It also prevents proper cancellation and timeout handling.

**Independent Test**: A unit test can call the async version of `_load_docs` and verify it returns the expected documents without blocking.

**Acceptance Scenarios**:

1. **Given** `TrainingService._load_docs` is called with a `dataset_id`, **When** it executes, **Then** it does not call `asyncio.run()` and instead uses async/await natively.
2. **Given** the method is converted to async, **When** upstream callers invoke it, **Then** they `await` the result properly through the call chain.
3. **Given** a training run with doc loading, **When** it completes, **Then** the loaded documents are identical to the current behavior.

---

### User Story 2 - Call chain updated (Priority: P2)

All callers of `TrainingService._load_docs()` (or its public equivalent) are updated to properly `await` the async method.

**Why this priority**: Changing a method from sync to async requires updating all call sites. Missed callers will get coroutine objects instead of results.

**Independent Test**: mypy strict mode catches any missed `await` because returning a `Coroutine` where a `list[str]` is expected is a type error.

**Acceptance Scenarios**:

1. **Given** `_load_docs` is now `async def`, **When** a caller invokes it without `await`, **Then** mypy reports a type error.
2. **Given** all callers are updated, **When** the test suite runs, **Then** all tests pass.

### Edge Cases

- What if a caller is a sync function in a thread (e.g., `threading.Thread` used for warmup)? Need `asyncio.run_coroutine_threadsafe` instead.
- What if the sync caller is in a non-async context (e.g., `__init__` or property getter)? Restructure to defer async work.

## Requirements

### Functional Requirements

- **FR-001**: `TrainingService._load_docs()` MUST be converted from a sync method using `asyncio.run()` to a fully async `async def` method.
- **FR-002**: The `DatasetService`, `CorpusService`, and `DemoBootstrapService` instantiations inside `_load_docs()` MUST be refactored so they are injected via constructor or workbench, not created inline (see companion spec #006).
- **FR-003**: All callers of `_load_docs()` MUST be updated to `await` the result.
- **FR-004**: Any callers that are in sync context (threads, non-async functions) MUST use `asyncio.run_coroutine_threadsafe()` or `asyncio.get_event_loop().run_in_executor()` instead.
- **FR-005**: The `AsyncSessionLocal()` creation inside the `_load_docs` helper MUST be replaced with session injection.
- **FR-006**: mypy --strict MUST pass with zero new errors.

### Key Entities

- **TrainingService._load_docs()**: The method being converted (in `anvil/services/training/training.py`)
- **DatasetService**: Currently instantiated inside the method (dependency to be injected)
- **CorpusService**: Currently instantiated inside the method (dependency to be injected)
- **DemoBootstrapService**: Currently instantiated inside the method (dependency to be injected)

## Success Criteria

### Measurable Outcomes

- **SC-001**: `asyncio.run()` does not appear anywhere in `anvil/services/training/`.
- **SC-002**: The doc-loading call chain is fully async (no `asyncio.run()` in any transitive caller).
- **SC-003**: All existing training tests pass without modification to test assertions.
- **SC-004**: mypy --strict passes with zero new errors.

## Assumptions

- The callers of `_load_docs` are themselves async methods that can be updated to `await`.
- No caller is in a truly sync-only context that cannot be converted.
- The document loading behavior is unchanged — only the async plumbing changes.
