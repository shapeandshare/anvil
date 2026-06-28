---
title: asyncio.get_event_loop() returns wrong loop in synchronous callbacks
type: discovery
tags:
  - type/discovery
  - domain/architecture
created: '2026-06-27'
updated: '2026-06-27'
status: draft
source: agent
aliases:
  - get-event-loop-deprecated-sync-callbacks
code-refs:
  - anvil/services/backup/backup_service.py
---
# `asyncio.get_event_loop()` Returns Wrong Loop in Synchronous Callbacks

**Discovered**: 2026-06-27  
**Context**: `backup_service.py` — `_progress` closures in `create_backup()` and `restore()`  
**Severity**: P1 (runtime warning, benign at production scale)

## The problem

Two `_progress` closures in `BackupService` used `asyncio.get_event_loop()` to obtain the event loop for `asyncio.run_coroutine_threadsafe()`:

```python
fut = asyncio.run_coroutine_threadsafe(
    queue.put(ProgressEvent(...)),
    asyncio.get_event_loop(),   # ← wrong loop in Python 3.14
)
```

In Python 3.14, `asyncio.get_event_loop()` is deprecated for most use cases and may return a **different event loop** than the one currently running the application. When this happens:

1. `run_coroutine_threadsafe` submits the coroutine to a loop that isn't running.
2. The coroutine is never scheduled.
3. When the coroutine object is garbage-collected, Python emits:
   ```
   RuntimeWarning: coroutine 'Queue.put' was never awaited
   ```

## Why it happens

- `_progress` is a synchronous closure defined inside an async method (`create_backup()` / `restore()`).
- It's passed as a callback to `ArchiveWriter.write()`, which runs heavy I/O inside `asyncio.to_thread()`.
- When the callback fires from within the thread pool worker, `asyncio.get_event_loop()` may not return the main event loop.

## The fix

Store the running loop at object initialization (which happens in an async context):

```python
# In __init__, called from async lifespan:
self._loop = asyncio.get_running_loop()

# In _progress closure:
fut = asyncio.run_coroutine_threadsafe(queue.put(...), self._loop)
```

`asyncio.get_running_loop()` is the correct, non-deprecated API — it always returns the currently running loop in the current thread, or raises `RuntimeError` if none is running.

## Scope

This was one of **24+ occurrences** of `asyncio.get_event_loop()` in the codebase flagged by the 2026-06-21 thread model review. Only the `backup_service.py` instances have been fixed in this session.

## See also

- [[Sessions/2026-06-27-backup-restore-ui-fixes-and-async-debt|Backup UI Fixes, Async Debt, Notification History]] — session log
- [[Sessions/2026-06-21-thread-model-review|Thread Model Review]] — original audit
- [[Discoveries/pytest-asyncio-python-3.14-compatibility|pytest-asyncio Python 3.14 compatibility]] — related Python 3.14 issues
- [Python docs: `asyncio.get_event_loop()`](https://docs.python.org/3/library/asyncio-eventloop.html#asyncio.get_event_loop)
