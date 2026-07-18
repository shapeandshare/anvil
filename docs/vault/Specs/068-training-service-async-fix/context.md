# Context — 068 Remove asyncio.run() Blocking Call

> Cross-references: `../066-codebase-remediation/data-inventory.md` §3. **Depends on spec 071** (service DI injection).

## Current State (quoted — CORRECTED)

**There are 3 `asyncio.run()` calls, not 1** (the original review undercounted). All in `anvil/services/training/training.py`:

Lines 327-353 (`_load_docs`):
```python
if dataset_id is not None:
    async def _load() -> list[str]:
        async with AsyncSessionLocal() as session:
            repo = DatasetRepository(session)
            store = LocalFileStore()
            svc = DatasetService(repo, store)
            return await svc.load_docs(dataset_id)
    return asyncio.run(_load())           # ← line 336

async def _load_default() -> list[str]:
    async with AsyncSessionLocal() as session:
        repo = CorpusRepository(session)
        loader = CorpusLoader()
        svc = CorpusService(repo, loader)
        bootstrap = DemoBootstrapService(session)
        corpus = await bootstrap.get_default_corpus()
        ...
        return await svc.load_docs(corpus.id)
return asyncio.run(_load_default())        # ← line 353
```
Plus a third at **line 430** (verify context — likely `_load_docs_from_version` or similar).

Re-verify: `grep -rn "asyncio.run(" anvil/services/training/`

## Why This Is a Problem

`asyncio.run()` creates a NEW event loop and blocks the current thread. In a FastAPI async request context, this can deadlock (nested loops), exhaust threads, and prevents cancellation/timeouts. Violates Constitution Article V (Async-First).

## Dependency on Spec 071

The fix requires the services (`DatasetService`, `CorpusService`, `DemoBootstrapService`) and a session to be available WITHOUT creating a new event loop. This means:
1. `_load_docs` becomes `async def _load_docs(...)`.
2. It receives a session (or uses the workbench's session) instead of `AsyncSessionLocal()`.
3. Services are injected (spec 071), not created inline.

**Do spec 071 first, or do both together.**

## Callers to Update

Find callers of `_load_docs` / `_load_docs_from_version`:
```bash
grep -rn "_load_docs\|load_docs" anvil/services/training/ anvil/api/
```
Each caller must `await` the now-async method. If any caller is in a sync thread context (background training thread), use `asyncio.run_coroutine_threadsafe()` with the running loop.

## Gotchas

- The training run likely executes in a background thread (`threading.Thread` in `training.py` / `training_run_service.py`). The doc-loading may happen inside that thread. If so, the fix must thread the loop reference through, or load docs BEFORE spawning the thread (preferred — load in the async request handler, pass docs into the thread).
- `expire_on_commit=False` is set on the session maker — loaded ORM objects remain usable after commit.
