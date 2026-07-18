# Feature Specification: Add response_model to All API Routes

**Feature Branch**: `opencode/witty-forest`  
**Created**: 2026-07-18  
**Status**: Draft  
**Priority**: P0  
**Input**: Codebase review finding #067 — Only `eval.py` uses `response_model=` on FastAPI routes. All other routes return `dict[str, Any]` or bare `dict`, producing incomplete OpenAPI docs and no response validation.

## User Scenarios & Testing

### User Story 1 - Complete OpenAPI documentation (Priority: P1)

API consumers (both human via `/docs` and programmatic via `/openapi.json`) should see accurate response shapes for every endpoint.

**Why this priority**: Without `response_model=`, OpenAPI specs show `{}` for response shapes. This makes the API undocumentable and forces clients to reverse-engineer response formats from source code.

**Independent Test**: Fetch `/openapi.json` and confirm every endpoint has a non-empty `responses` schema that matches its actual return shape.

**Acceptance Scenarios**:

1. **Given** any route defined in `anvil/api/v1/`, **When** `response_model=` is declared on the decorator, **Then** the OpenAPI schema for that endpoint shows the correct response properties.
2. **Given** a response model exists for a route, **When** the route returns extra fields not in the model, **Then** FastAPI strips them from the response (or raises in strict mode).
3. **Given** a response model is defined as `ResponseModel` (Pydantic), **When** a route handler returns it, **Then** the response JSON matches the model schema exactly.

---

### User Story 2 - Consistent response envelope (Priority: P2)

All API responses follow a single consistent envelope pattern (either direct Pydantic models or a standard wrapper).

**Why this priority**: Currently three different response patterns exist (`{"data":..., "error":None}`, direct dict, flat status dict). This creates client confusion and fragile parsing code.

**Independent Test**: A single client can parse responses from all endpoints using one parsing strategy.

**Acceptance Scenarios**:

1. **Given** two different endpoints, **When** both return successfully, **Then** their response JSON follows the same structural pattern.
2. **Given** an endpoint returns an error, **When** the client inspects the response, **Then** the error structure is consistent across all endpoints.

### Edge Cases

- What about paginated responses? Need a `PaginatedResponse[T]` generic model.
- What about SSE streaming endpoints? These don't use `response_model=` (different response class).
- What about file download endpoints (`FileResponse`)? These need special handling.

## Requirements

### Functional Requirements

- **FR-001**: Every route in `anvil/api/v1/` MUST declare `response_model=` on its decorator, using a Pydantic `BaseModel` subclass.
- **FR-002**: Response models MUST be defined in the appropriate `schemas_*.py` file, co-located with their domain.
- **FR-003**: Response models MUST use `ConfigDict(extra="forbid")` (for request) or `ConfigDict(extra="ignore")` (for response) as appropriate.
- **FR-004**: A single response envelope convention MUST be chosen: either direct Pydantic models (like `eval.py`) or a wrapper (`{"data": ..., "error": ...}`).
- **FR-005**: SSE streaming endpoints, file downloads, and health-check endpoints are exempt from `response_model=` but MUST be documented.
- **FR-006**: All routes MUST use `from __future__ import annotations` (PEP 563) for clean forward-reference handling in response models.

### Key Entities

- **Response models**: One Pydantic `BaseModel` per distinct response shape (shared across routes where appropriate)
- **PaginatedResponse[T]**: Generic model for list endpoints with pagination
- **ErrorResponse**: Standard error response shape if envelope pattern is chosen

## Success Criteria

### Measurable Outcomes

- **SC-001**: `/openapi.json` shows complete response schemas for every endpoint.
- **SC-002**: All `dict[str, Any]` return annotations replaced with typed Pydantic models.
- **SC-003**: Single response envelope convention adopted project-wide.
- **SC-004**: No regressions in existing API behavior (all current response values preserved).

## Assumptions

- The `eval.py` pattern (direct Pydantic response models with `response_model=`) is the reference implementation to follow.
- SSE endpoints (`/training/stream/{run_id}`, `/sse/eval/{run_id}`) are exempt from `response_model=`.
- File download endpoints are exempt.
- The response envelope decision (direct model vs wrapper) will be made during implementation — both are valid.
