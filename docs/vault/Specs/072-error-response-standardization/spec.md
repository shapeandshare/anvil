# Feature Specification: Standardize API Error Response Format

**Feature Branch**: `opencode/witty-forest`  
**Created**: 2026-07-18  
**Status**: Draft  
**Priority**: P1  
**Input**: Codebase review finding #072 — Three different error response envelope patterns exist across routes: `{"data": ..., "error": None}` (datasets/corpora/content), direct `dict` (training/experiments/eval), and flat status `dict` (health/config). No consistent error schema.

## User Scenarios & Testing

### User Story 1 - Consistent error responses (Priority: P1)

Every API endpoint returns errors in the same structured format, allowing clients to write a single error handler.

**Why this priority**: Clients currently must detect which error format an endpoint uses before parsing. This is fragile, error-prone, and makes API client SDKs more complex than necessary.

**Independent Test**: A client can catch any non-2xx response, parse it with a single error model, and extract a human-readable message + error code.

**Acceptance Scenarios**:

1. **Given** any API endpoint returns a 4xx error, **When** the client inspects the response body, **Then** the body contains `{"detail": "...", "code": "ERROR_CODE"}` (or a single agreed-upon format).
2. **Given** an endpoint that previously used `{"data": ..., "error": "message"}`, **When** it returns a success, **Then** it returns the standardized format.
3. **Given** an endpoint that previously used `{"data": ..., "error": None}`, **When** it returns a success, **Then** it returns the standardized format.

---

### User Story 2 - Structured error codes (Priority: P2)

Errors include machine-readable codes that clients can use for programmatic routing (e.g., "UNAUTHORIZED", "NOT_FOUND", "VALIDATION_ERROR", "RATE_LIMITED").

**Why this priority**: String matching on `detail` is fragile — it breaks when error messages are reworded. Codes are stable identifiers.

**Independent Test**: A client catches a 401 response and routes to login page by checking `error.code === "UNAUTHORIZED"`.

**Acceptance Scenarios**:

1. **Given** a 401 Unauthorized response, **When** parsed, **Then** it includes `"code": "UNAUTHORIZED"`.
2. **Given** a 404 Not Found response, **When** parsed, **Then** it includes `"code": "NOT_FOUND"`.
3. **Given** a 422 Validation Error response, **When** parsed, **Then** it includes `"code": "VALIDATION_ERROR"`.

### Edge Cases

- What about the `{"data": ..., "error": None}` wrapper pattern used for successful responses? Need to decide whether to keep the wrapper or return direct Pydantic models.
- What about server errors (500) from exception handlers? Should they also follow the format?
- What about validation errors from Pydantic (422)? FastAPI's default `{"detail": [{"loc": ..., "msg": ..., "type": ...}]}` needs to be preserved or converted.

## Requirements

### Functional Requirements

- **FR-001**: A single error response format MUST be adopted for all HTTP error responses (4xx, 5xx).
- **FR-002**: The format MUST include a human-readable `detail` field and a machine-readable `code` field.
- **FR-003**: The format MUST be defined as a Pydantic `ErrorResponse` model for OpenAPI documentation.
- **FR-004**: All route handlers MUST return errors in the standardized format (via `HTTPException` or custom exception handlers).
- **FR-005**: A custom `HTTPException` subclass or exception handler MUST be provided to ensure consistency.
- **FR-006**: Existing error handling in `app.py` (`_http_exception_handler`, `_tokenizer_load_error_handler`, `_catalog_unavailable_handler`) MUST be updated to produce the standardized format.
- **FR-007**: The success response envelope decision (direct Pydantic model vs `{"data": ..., "error": None}` wrapper) MUST be made and applied consistently (coordinated with spec #002).

### Key Entities

- **ErrorResponse**: Pydantic model with `detail: str`, `code: str`, optional `fields: dict`
- **StandardHTTPException**: Subclass of `HTTPException` that guarantees the standard format
- **error_response_handler**: Updated exception handler in `app.py`

## Success Criteria

### Measurable Outcomes

- **SC-001**: All error responses across all endpoints follow the same format.
- **SC-002**: OpenAPI schema documents the `ErrorResponse` model.
- **SC-003**: All existing `HTTPException` calls are updated or wrapped to include `code`.
- **SC-004**: `make test` passes with zero regressions.
- **SC-005**: The `eval.py` pattern (Pydantic response models) is used as the reference, or the wrapper pattern is chosen — either way, it's consistent.

## Assumptions

- The FastAPI default `HTTPException` will be wrapped or subclassed to add the `code` field.
- The existing exception handlers in `app.py` are the right place to enforce the format.
- Success response envelope decision is resolved in coordination with spec #002.
