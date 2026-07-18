# Tasks — 077 Clean Up session.py

**TDD order. Prefer Option A (minimal) per context.md.**

## Phase 0 — Investigate
- [ ] T001 Re-verify lines: `grep -n "cast(\|assert \|_bootstrap_engine()" anvil/db/session.py`.
- [ ] T002 Map consumers of `async_engine`/`AsyncSessionLocal`: `grep -rn "db.session import" anvil/ tests/`. Confirm direct `.begin()` usage (e.g. conftest).

## Phase 1 — Remove assert (Red-Green)
- [ ] T010 **[Red]** `tests/unit/db/test_session_guards.py::test_init_engine_raises_when_engine_none` — patch `_engine=None`, call `init_engine`, expect `RuntimeError` (not `AssertionError`).
- [ ] T011 **[Green]** Replace `assert _engine is not None` (line 101) and `assert _session_maker is not None` (line 137) with `if ... is None: raise RuntimeError(...)`.

## Phase 2 — Remove cast (Refactor)
- [ ] T020 **[Green]** Change `_bootstrap_engine()` to RETURN `(engine, session_maker)` with proper types; assign module globals from the typed return (no `cast()`). Update `reinit_engine()` similarly.
- [ ] T021 Verify `mypy --strict` passes with zero `cast()` in the file.

## Phase 3 — (Optional) lazy init
- [ ] T030 ONLY if a concrete need exists: evaluate lazy `__getattr__`. Otherwise SKIP (YAGNI).

## Phase 4 — Gates
- [ ] T040 `grep -n "cast(\|assert " anvil/db/session.py` returns nothing.
- [ ] T041 `python -O -m pytest tests/unit/db/` — same results as without `-O`.
- [ ] T042 `make lint && make typecheck && make test` (esp. conftest `async_engine.begin()` usage).

## Verification (Success Criteria)
- SC-001: zero `cast()` in session.py.
- SC-002: zero `assert` in session.py.
- SC-003: gates green.
- SC-004: `-O` run identical.
