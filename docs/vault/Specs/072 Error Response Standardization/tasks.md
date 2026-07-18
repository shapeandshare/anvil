# Tasks — 072 Standardize API Error Response Format

**TDD order. Consumes spec 079 (`AnvilServiceError`).**

## Phase 0 — Prerequisites
- [ ] T001 Confirm Decisions 1 & 4. Confirm spec 079 provides `AnvilServiceError` with `.code`/`.message`.
- [ ] T002 Decide 422 handling (RECOMMEND: preserve FastAPI default). Document.

## Phase 1 — ErrorResponse model (Red-Green)
- [ ] T010 **[Red]** `tests/unit/api/test_error_response.py::test_error_response_shape` — asserts `{detail, code}` structure.
- [ ] T011 **[Green]** Define `ErrorResponse(BaseModel)` in a shared schemas module.

## Phase 2 — Unified handler
- [ ] T020 **[Red]** `test_service_error_maps_to_error_response` — raising `AnvilServiceError(code="X", message="Y")` yields `{"detail":"Y","code":"X"}` with correct status.
- [ ] T021 **[Green]** Add `@app.exception_handler(AnvilServiceError)` in `app.py` mapping to `ErrorResponse`.
- [ ] T022 **[Green]** Update `_http_exception_handler`, `_tokenizer_load_error_handler`, `_catalog_unavailable_handler` to emit `ErrorResponse` shape (preserve tokenizer `file`/`cause` via `fields`).

## Phase 3 — Standardize existing raises
- [ ] T030 Audit `HTTPException(status_code=..., detail=...)` calls; ensure `code` is included (via a `StandardHTTPException` subclass or by mapping in the handler).
- [ ] T031 Migrate `{data, error}` wrapper error paths (coordinate with spec 067 envelope decision).

## Phase 4 — Gates
- [ ] T040 `make lint && make typecheck && make test`.
- [ ] T041 Verify OpenAPI documents `ErrorResponse` for error status codes.

## Verification (Success Criteria)
- SC-001: all error responses follow `{detail, code}`.
- SC-002: OpenAPI documents `ErrorResponse`.
- SC-003: all `HTTPException` calls include a code.
- SC-004: `make test` green.
- SC-005: consistent with spec 067 envelope choice.
