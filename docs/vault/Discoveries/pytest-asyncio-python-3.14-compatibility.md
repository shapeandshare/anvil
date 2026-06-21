---
created: '2026-06-21'
tags:
  - test
  - pytest-asyncio
  - python-3.14
title: pytest-asyncio + Python 3.14 async generator fixture compatibility
type: discovery
updated: '2026-06-21'
---
# pytest-asyncio + Python 3.14 Async Generator Fixture Compatibility

## Problem

`pytest-asyncio 0.26` on Python 3.14 causes event loop corruption when async generator fixtures (`@pytest.fixture async def ... yield`) are collected for 50+ test modules in a single run. Symptoms:

- Tests pass when run in isolation or small batches (2-20 files)
- Tests fail with `ERROR at setup of test_xxx` when run as a directory (`tests/unit/`)
- Root cause: Python 3.14 deprecates `asyncio.get_event_loop_policy()` — pytest-asyncio 0.26 calls this on every async fixture setup/teardown, causing cumulative state corruption

## Fix

Two changes are required:

1. **Upgrade pytest-asyncio to >=1.0** (currently 1.4.0) — 1.x handles Python 3.14's event loop deprecations properly
2. **Use `@pytest_asyncio.fixture(loop_scope="function")`** instead of `@pytest.fixture` for async generator fixtures — in pytest-asyncio 1.x, `@pytest.fixture async def` is not the same as `@pytest_asyncio.fixture`, and only the latter properly manages async generator lifecycle
3. **Batch the test run** — even with 1.4.0, collecting 60+ modules with async generator fixtures can overload the event loop. Run explicit file paths in 2+ batches instead of `tests/unit/` with `-k` filter.

## Batch Pattern

```makefile
BATCH1 = tests/unit/ci/ tests/unit/core/ tests/unit/db/test_corpus_model.py ...
BATCH2 = tests/unit/db/test_corpus_repository.py tests/unit/db/...

test:
	$(PYTHON) -m pytest $(BATCH1) --cov=anvil --cov-report=
	$(PYTHON) -m pytest $(BATCH2) --cov=anvil --cov-report=term-missing --cov-append
```

The `-k` filter approach does NOT work because pytest collects ALL test modules and conftest files first (including their module-level imports) before applying the filter, which still triggers the event loop issue.

## References

- Session: [[Sessions/2026-06-21-unit-test-coverage-fixes]]
- [[012-ddd-services-restructure]]
- [pytest-asyncio 1.0 changelog](https://pytest-asyncio.readthedocs.io/en/latest/)
