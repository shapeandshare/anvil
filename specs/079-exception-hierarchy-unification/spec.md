# Feature Specification: Exception Hierarchy Unification

**Feature Branch**: `opencode/witty-forest`  
**Created**: 2026-07-18  
**Status**: Draft  
**Priority**: P2  
**Input**: Codebase review finding #079a — Server-side exceptions inherit from mixed bases (`Exception`, `RuntimeError`, `ValueError`, `KeyError`) with no common ancestor. No unified `AnvilServiceError` base class exists for service-layer errors.

## User Scenarios & Testing

### User Story 1 - Unified exception hierarchy (Priority: P2)

All service-layer exceptions inherit from a common `AnvilServiceError` base, enabling consistent error handling, logging, and API error conversion.

**Why this priority**: Currently each service raises whatever exception type it chooses. Error handlers in `app.py` must list each type explicitly (`HTTPException`, `TokenizerLoadError`, `CatalogUnavailableError`). A unified hierarchy enables a single handler that catches all service errors and translates them to HTTP responses.

**Independent Test**: Catching `AnvilServiceError` in a test catches all service-layer exceptions.

**Acceptance Scenarios**:

1. **Given** any service method raises an error, **When** caught by an `except AnvilServiceError` handler, **Then** it catches the exception.
2. **Given** a new service is added, **When** it throws an `AnvilServiceError`, **Then** the centralized error handler in `app.py` converts it to the standard API error format.

---

### User Story 2 - Structured error attributes (Priority: P2)

Service exceptions carry structured fields (`code`, `message`, `details`) enabling the error handler to build rich API error responses without parsing exception strings.

**Why this priority**: The current `ModelSourceError` in `import_types.py` demonstrates the right pattern (carries `code`, `message`, `source`) but it's the exception, not the rule. Most exceptions carry only a string message that must be re-parsed by handlers.

**Independent Test**: An `AnvilServiceError` instance has a `.code` attribute and a `.message` attribute that can be accessed programmatically.

**Acceptance Scenarios**:

1. **Given** a `DatasetNotFoundError(AnvilServiceError)`, **When** caught, **Then** `err.code == "DATASET_NOT_FOUND"` and `err.message` is human-readable.
2. **Given** the API error handler receives an `AnvilServiceError`, **When** it builds the response, **Then** it uses `err.code` for the `code` field and `err.message` for `detail`.

### Edge Cases

- Already-cohesive exception groups (like `encryption_errors.py` inheriting from `ValueError`/`KeyError`/`RuntimeError`) should retain their specific inheritance AND also inherit from `AnvilServiceError` (multiple inheritance).
- Exception types used as control flow (e.g., `StopRequested` for training cancellation) should be considered carefully — they may not need `AnvilServiceError`.

## Requirements

### Functional Requirements

- **FR-001**: A new base class `AnvilServiceError(Exception)` MUST be defined in `anvil/services/_shared/` (or `anvil/exceptions.py`).
- **FR-002**: `AnvilServiceError` MUST carry `code: str` and `message: str` fields (plus optional `details: dict`).
- **FR-003**: All existing service-layer exceptions SHOULD be updated to inherit from `AnvilServiceError` (or a domain-specific base that inherits from it).
- **FR-004**: Cohesive exception groups (encryption errors) MAY use multiple inheritance to retain their specific parent AND `AnvilServiceError`.
- **FR-005**: The API error handler in `app.py` SHOULD catch `AnvilServiceError` and convert it to the standard API error format (coordinated with spec #007).
- **FR-006**: Exceptions used for control flow (`StopRequested`, `DivergenceError`) MAY remain outside the hierarchy if they are not API-facing.
- **FR-007**: The client SDK's `ApiError` hierarchy (`api_error.py`) is already well-structured and does NOT need to be unified with the server hierarchy.

### Key Entities

- **AnvilServiceError**: New base class in `anvil/services/_shared/`
- **Existing exceptions to unify**: `CatalogUnavailableError`, `SafetensorsExportError`, `TokenizerLoadError`, `MigrationError`, `ComputeBackendUnavailable`, `RemotePollError`, `RemoteSubmissionError`, `ModelSourceError`
- **Existing exceptions to keep separate**: Encryption errors (already cohesive), control-flow exceptions
- **Client ApiError**: Already well-structured, no changes needed

## Success Criteria

### Measurable Outcomes

- **SC-001**: `AnvilServiceError` base class defined and importable.
- **SC-002**: All service-layer exceptions inherit from `AnvilServiceError` (directly or transitively).
- **SC-003**: The API error handler catches `AnvilServiceError` and produces standard-formatted responses.
- **SC-004**: `make test`, `make lint`, and `make typecheck` pass.
- **SC-005**: No regressions in existing error handling.

## Assumptions

- The change is additive (existing exception classes work as before) — existing `except Exception` handlers still catch them.
- Migration can be incremental — each exception class can be updated independently.
- The `AnvilServiceError` base lives in `_shared/` to avoid circular imports.
