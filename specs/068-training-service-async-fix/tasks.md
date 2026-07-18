# Tasks — 068 Remove asyncio.run() Blocking Call

**TDD order. Depends on spec 071 (service DI) — do 071 first or together.**

## Phase 0 — Investigate
- [ ] T001 Re-verify: `grep -rn "asyncio.run(" anvil/services/training/` → confirm 3 occurrences (lines ~336, ~353, ~430).
- [ ] T002 Read `training.py:430` context to identify the third call's method.
- [ ] T003 Map all callers: `grep -rn "_load_docs\|load_docs" anvil/services/training/ anvil/api/`. Determine which run in async vs thread context.

## Phase 1 — Convert _load_docs to async (Red-Green-Refactor)
- [ ] T010 **[Red]** Write `tests/unit/services/training/test_load_docs_async.py::test_load_docs_is_coroutine` — asserts `_load_docs` (or public equivalent) returns a coroutine and awaits correctly with an injected session. Confirm FAILS.
- [ ] T011 **[Red]** Write `test_load_docs_dataset_branch` and `test_load_docs_default_corpus` — verify loaded docs match current behavior using an in-memory session fixture.
- [ ] T012 **[Green]** Convert `_load_docs` to `async def`. Accept an injected `AsyncSession` (or use workbench session) instead of `AsyncSessionLocal()`. Use injected services (from spec 071). Remove all 3 `asyncio.run()` calls. Make tests pass.
- [ ] T013 **[Refactor]** Remove now-dead `_load()`/`_load_default()` inner closures; flatten into async method body.

## Phase 2 — Update callers
- [ ] T020 **[Red]** Write/adjust tests for each caller to expect the async signature.
- [ ] T021 **[Green]** Update all callers to `await` the async method.
- [ ] T022 For any sync-thread caller: refactor so docs are loaded in the async handler BEFORE spawning the training thread, OR use `asyncio.run_coroutine_threadsafe()`. Document the choice.

## Phase 3 — Gates
- [ ] T030 `grep -rn "asyncio.run(" anvil/services/training/` returns nothing.
- [ ] T031 `make lint && make typecheck && make test`.
- [ ] T032 Run training e2e: `tests/e2e/test_training_parity.py` passes unchanged.

## Verification (Success Criteria)
- SC-001: zero `asyncio.run()` in `anvil/services/training/`.
- SC-002: doc-loading call chain fully async.
- SC-003: existing training tests pass without assertion changes.
- SC-004: mypy --strict clean.
