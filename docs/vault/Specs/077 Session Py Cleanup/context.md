# Context — 077 Clean Up session.py

> Cross-references: `../066-codebase-remediation/data-inventory.md` §9.

## Current State (quoted, `anvil/db/session.py`)

`cast()` calls (lines 89, 91, 128, 129):
```python
async_engine: AsyncEngine = cast("AsyncEngine", _engine)
AsyncSessionLocal: async_sessionmaker[AsyncSession] = cast("async_sessionmaker[AsyncSession]", _session_maker)
# and in reinit_engine():
async_engine = cast("AsyncEngine", _engine)
AsyncSessionLocal = cast("async_sessionmaker[AsyncSession]", _session_maker)
```

`assert` statements (lines 101, 137):
```python
assert _engine is not None  # assured by _bootstrap_engine on import   (line 101, in init_engine)
assert _session_maker is not None  # ...                               (line 137, in get_db)
```

Module-level bootstrap at import (line 86):
```python
_bootstrap_engine()  # Auto-initialise from defaults on first module import
```

Re-verify: `grep -n "cast(\|assert \|_bootstrap_engine()" anvil/db/session.py`

## Root Cause

The `cast()` calls exist BECAUSE `_bootstrap_engine()` runs at import and mypy can't prove `_engine`/`_session_maker` are non-None afterward. Fixing the module-level init pattern removes the need for both `cast()` and `assert`.

## Consumers (do not break)

`async_engine` and `AsyncSessionLocal` are imported widely:
```bash
grep -rn "from.*db.session import\|from ..db.session\|from .session import" anvil/ tests/
```
Notably `tests/conftest.py:29` imports `AsyncSessionLocal, async_engine`. Changing these to lazy accessors (functions) would break `async_engine.begin()` call sites. Prefer a solution that keeps them as usable module attributes.

## Approach Options

- **Option A (safest)**: Replace `assert` with explicit `if _engine is None: raise RuntimeError(...)`. Replace `cast()` by having `_bootstrap_engine()` RETURN the engine/maker and assign directly (typed return, no cast). Keep import-time bootstrap.
- **Option B**: Fully lazy init — `async_engine`/`AsyncSessionLocal` become module `__getattr__` lazy properties. More invasive; risks breaking `async_engine.begin()` direct usage.

RECOMMENDATION: **Option A** — minimal, removes cast+assert, keeps backward compat. Only pursue lazy init if there's a concrete need (YAGNI, Principle 13).

## Gotchas

- `reinit_engine()` (workspace path) reassigns the module globals — must still work.
- `-O` flag test: after removing asserts, run `python -O -m pytest tests/unit/db/` to confirm behavior is identical.
- Keep `expire_on_commit=False`, `pool_pre_ping=True`, `check_same_thread=False` connect args unchanged.
