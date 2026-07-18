# Tasks — 079 Exception Hierarchy Unification

**TDD order. Blocks spec 072. Additive change — preserve existing catch sites.**

## Phase 0 — Investigate
- [ ] T001 Re-verify exception inventory (context.md grep).
- [ ] T002 Audit catch sites that rely on current bases: `grep -rn "except RuntimeError\|except ValueError\|except KeyError" anvil/` — note any that catch the exceptions being re-parented.

## Phase 1 — Base class (Red-Green)
- [ ] T010 **[Red]** `tests/unit/services/test_service_error.py::test_anvil_service_error_fields` — asserts `code`/`message`/`details` attributes.
- [ ] T011 **[Green]** Create `anvil/services/_shared/service_error.py` with `AnvilServiceError(Exception)` carrying `code: str`, `message: str`, `details: dict | None = None`.

## Phase 2 — Re-parent exceptions (Red-Green per exception)
- [ ] T020 **[Red]** For each exception, a test asserting `isinstance(err, AnvilServiceError)` AND (where applicable) the original base still holds.
- [ ] T021 **[Green]** Re-parent the 11 `Exception`/`RuntimeError` service exceptions to `AnvilServiceError`. For `CatalogUnavailableError`/`MigrationError` (currently `RuntimeError`), use `class X(AnvilServiceError, RuntimeError)` if catch sites need `RuntimeError`.
- [ ] T022 **[Green]** Encryption errors: multiple inheritance `(AnvilServiceError, KeyError/ValueError/RuntimeError)` to preserve builtin isinstance checks.
- [ ] T023 Leave `DivergenceError`, `StopRequested`, and client `ApiError*` untouched.

## Phase 3 — Populate code/message
- [ ] T030 Ensure each re-parented exception sets a meaningful `code` (e.g. `MODEL_NOT_FOUND`, `CATALOG_UNAVAILABLE`) and `message`.

## Phase 4 — Gates
- [ ] T040 `make lint && make typecheck && make test` — existing catch sites still work.
- [ ] T041 Confirm no `except RuntimeError` site broke (from T002 audit).

## Verification (Success Criteria)
- SC-001: `AnvilServiceError` defined and importable.
- SC-002: all target service exceptions inherit from it (directly or via MI).
- SC-003: spec 072 handler can catch `AnvilServiceError` (verified when 072 lands).
- SC-004: gates green.
- SC-005: no error-handling regressions.
