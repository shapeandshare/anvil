# Context — 074 Remove Module-Level Mutable State

> Cross-references: `../066-codebase-remediation/data-inventory.md` §4.

## Current State (verified line refs)

```python
# training.py:128
_tasks: dict[int, asyncio.Task[Any]] = {}

# fine_tune_datasets.py:42
_tasks: dict[int, asyncio.Task[Any]] = {}

# content.py:60
_injection_queue: asyncio.Queue[dict[str, str]] = asyncio.Queue(maxsize=128)
```

Re-verify: `grep -rn "_tasks\|_injection_queue" anvil/api/v1/`

## How They're Used

- `training.py._tasks` — registry of active training background tasks keyed by run_id. Accessed by start (add), stream (read), and cleanup (remove) handlers. There are likely `get_queue`/`release_queue` helpers.
- `fine_tune_datasets.py._tasks` — same pattern for fine-tune jobs.
- `content.py._injection_queue` — queue for content injection events.

Find all accessors:
```bash
grep -rn "_tasks\[" anvil/api/v1/training.py anvil/api/v1/fine_tune_datasets.py
grep -rn "_injection_queue" anvil/api/v1/content.py
```

## Target

Move to `app.state` in the lifespan handler (`anvil/api/app.py:259-322`):
```python
# in lifespan startup:
_app.state.training_tasks = {}
_app.state.fine_tune_tasks = {}
_app.state.content_injection_queue = asyncio.Queue(maxsize=128)
# in shutdown: cancel outstanding tasks, drain queue
```
Routes access via `request.app.state.training_tasks`.

## Reference

`app.py` already stores state: `_app.state.mlflow`, `_app.state.templates`, `_app.state.backup_service`, `_app.state.workspace_paths`. Follow the same pattern.

## Gotchas

- SSE stream handlers may run detached from the request lifecycle — ensure they can still reach `app.state` (they get `request`, so `request.app.state` works).
- Background training tasks are created via `asyncio.create_task` — the task registry must be reachable from both the creating handler and the SSE consumer. `app.state` is shared across requests within one process, so this works.
- Shutdown: the lifespan should cancel any still-running tasks to avoid orphaned coroutines.
- Coordinate with spec 069 (route DI) — the `svc.get_queue`/`release_queue` helpers on `TrainingService` may also touch this state; keep queue ownership consistent (either service-owned or app.state-owned, not both).
