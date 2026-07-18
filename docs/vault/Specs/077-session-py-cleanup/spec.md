# Feature Specification: Clean Up session.py (cast, assert, Module Globals)

**Feature Branch**: `opencode/witty-forest`  
**Created**: 2026-07-18  
**Status**: Draft  
**Priority**: P2  
**Input**: Codebase review finding #077 — `anvil/db/session.py` uses `cast()` for type narrowing (lines 89-93), `assert` for production logic (lines 101, 137), and module-level global engine/session_maker variables. These patterns are fragile and can be bypassed or disabled.

## User Scenarios & Testing

### User Story 1 - No cast() for type narrowing (Priority: P2)

Module-level exports use proper type annotations or factory functions instead of `cast()` to reassure mypy.

**Why this priority**: `cast()` is a type-safety escape hatch that tells mypy "trust me, this is the right type." If the bootstrap logic ever fails, `cast()` hides the bug. A proper solution makes the type correct by construction.

**Independent Test**: Running `mypy --strict` on `session.py` passes without any `cast()` calls in the file.

**Acceptance Scenarios**:

1. **Given** `session.py` is loaded, **When** mypy type-checks it, **Then** all `cast()` calls are removed and the types are inferred or annotated correctly.
2. **Given** `async_engine` is accessed, **When** it is used, **Then** its type is correctly `AsyncEngine` (not `Any` or incorrectly narrowed).

---

### User Story 2 - No assert for production logic (Priority: P2)

`assert` statements in `session.py` are replaced with proper guards that cannot be disabled.

**Why this priority**: `python -O` disables `assert`. In production, this means the assertions that `_engine is not None` would be skipped, potentially causing `None`-related crashes later.

**Independent Test**: Running Python with `-O` flag does not change behavior of `session.py`.

**Acceptance Scenarios**:

1. **Given** `init_engine()` is called, **When** `_engine` is `None`, **Then** a `RuntimeError` with a clear message is raised (not an `AssertionError`).
2. **Given** Python is run with `-O`, **When** the session module is used, **Then** all guards still execute.

---

### User Story 3 - Module-level engine uses proper init (Priority: P2)

The module-level engine bootstrap uses a factory function or async initialization pattern instead of running `_bootstrap_engine()` at module import time.

**Why this priority**: Running DB initialization at import time means the engine is created before the lifespan handler can configure it. The `reinit_engine()` workaround for workspaces then disposes and recreates it, which is wasteful.

**Independent Test**: Importing the module does not create a DB engine — it is created when the first session is requested.

**Acceptance Scenarios**:

1. **Given** `import anvil.db.session` is executed, **When** no database access has been requested, **Then** no engine is created.
2. **Given** `get_db()` is called for the first time, **When** it creates a session, **Then** the engine is lazily created at that point.

### Edge Cases

- Existing code that accesses `async_engine` at module level (e.g., in `conftest.py`) needs a lazy accessor or async factory.
- Backward compatibility: existing imports of `async_engine` and `AsyncSessionLocal` must continue to work.

## Requirements

### Functional Requirements

- **FR-001**: All `cast()` calls in `session.py` MUST be removed (lines 89, 92).
- **FR-002**: All `assert` statements in `session.py` MUST be replaced with proper conditional checks and `RuntimeError` (lines 101, 137).
- **FR-003**: Module-level `_bootstrap_engine()` call at import time (line 86) SHOULD be replaced with lazy initialization.
- **FR-004**: If lazy initialization is adopted, `async_engine` and `AsyncSessionLocal` must become lazy accessors (functions or properties).
- **FR-005**: The workspace `reinit_engine()` path must continue to work correctly.
- **FR-006**: All test and production code that imports `async_engine` and `AsyncSessionLocal` must continue to work.
- **FR-007**: `mypy --strict` must pass with zero new errors.

### Key Entities

- **session.py**: The file being modified
- **async_engine**: Module-level `AsyncEngine` (currently `cast()`)
- **AsyncSessionLocal**: Module-level `async_sessionmaker` (currently `cast()`)
- **_engine**: Internal `AsyncEngine | None` backing field
- **_session_maker**: Internal `async_sessionmaker | None` backing field
- **conftest.py**: Tests that import `async_engine` directly

## Success Criteria

### Measurable Outcomes

- **SC-001**: Zero `cast()` calls in `session.py`.
- **SC-002**: Zero `assert` statements in `session.py`.
- **SC-003**: `make test` and `make typecheck` pass.
- **SC-004**: Running `python -O -m pytest` on session tests produces the same results as without `-O`.

## Assumptions

- Lazy initialization of the engine is the preferred approach, but a factory function pattern with an explicit `init_engine()` call is an acceptable alternative if lazy is too complex.
- Backward compatibility is critical — changes that break `from anvil.db.session import async_engine` must be coordinated with the migration.
