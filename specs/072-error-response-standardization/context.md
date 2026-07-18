# Context — 072 Standardize API Error Response Format

> Cross-references: `shared-decisions.md` Decision 1 & Decision 4. Consumes spec 079 (`AnvilServiceError`).

## Current State (verified)

Three response envelopes in use (from route survey):
- `{"data": ..., "error": None}` — datasets, corpora, content
- Direct dict — training, experiments, eval
- Flat status dict — health, config

Existing exception handlers in `anvil/api/app.py`:
- `_http_exception_handler` (lines 338-341) → `{"detail": exc.detail}`
- `_tokenizer_load_error_handler` (lines 351-366) → `{"detail": {"type":..., "message":..., ...}}`
- `_catalog_unavailable_handler` (lines 369-380) → `{"detail": "...", "code": "CATALOG_UNAVAILABLE"}`

Note: the auth/rate-limit middleware already returns `{"detail": ..., "code": ...}` (app.py:454-457, 555-558) — this is the closest to a standard. Codes seen: `UNAUTHORIZED`, `FORBIDDEN`, `RATE_LIMITED`, `BAD_REQUEST`, `CATALOG_UNAVAILABLE`.

## Reference Pattern (already in codebase)

The middleware's `{"detail": "...", "code": "..."}` shape is the de-facto standard. Formalize it as `ErrorResponse`:
```python
class ErrorResponse(BaseModel):
    detail: str
    code: str
    fields: dict[str, str] | None = None
```

## Decision Reference

- `shared-decisions.md` Decision 1: error format is `{"detail", "code"}` (aligns with existing middleware).
- `shared-decisions.md` Decision 4: consume `AnvilServiceError` (spec 079) — a single handler catches it and maps `.code`/`.message` → `ErrorResponse`.

## Dependencies

- Spec 079 (exception hierarchy) — provides `AnvilServiceError` with `.code`/`.message`.
- Spec 067 (response_model) — `ErrorResponse` documented in OpenAPI `responses`.

## Gotchas

- FastAPI's built-in 422 validation error has its own shape (`{"detail": [{"loc",...}]}`). Decide: preserve it (standard FastAPI) or wrap it. RECOMMENDATION: preserve 422 as-is (clients expect FastAPI's validation format); standardize only 4xx/5xx application errors.
- The `_tokenizer_load_error_handler` has a rich nested `detail` — decide whether to flatten into `ErrorResponse` or keep the structured detail. Preserve `file`/`cause` info via the `fields` dict.
- Migrating the `{data, error}` wrapper endpoints is coordinated with spec 067 (envelope decision).
