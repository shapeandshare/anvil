---
title: Training SSE Reconnection on Page Refresh
type: session-log
tags:
  - type/session-log
  - domain/training
  - domain/ui
created: '2026-06-28'
updated: '2026-06-28'
status: draft
source: agent
aliases: Training SSE Reconnection on Page Refresh
---

# Training SSE Reconnection on Page Refresh

**Session**: Fixed a UX bug where refreshing the Training page during an active
training run would cause the UI to report the run as "errored" and prevent
reconnection, even though training continued running in the background.

## What was done

### Diagnosed the state-loss mechanism

Traced the full training SSE lifecycle:

1. `POST /v1/training/start` → `TrainingService.reserve_run()` creates `asyncio.Queue` in `self._queues[run_id]`
2. Frontend connects `SSESession` → `EventSource` to `/v1/training/stream/{run_id}`
3. `stream_training()` gets the queue, creates `event_stream()` generator that reads events
4. On page refresh: `EventSource` disconnects → ASGI cancels generator → `finally` block runs → `svc.release_queue(run_id)` removes the queue
5. New page: `reconnectToRun()` checks `GET /v1/training/{run_id}/status` → queue is gone → 404 → marked as errored

### Fixed queue release in `event_stream()` finally block

Changed `anvil/api/v1/training.py` line 978:

```python
# Before: unconditional release
finally:
    svc.release_queue(run_id)

# After: only release if training task completed
finally:
    if run_id not in _tasks:
        svc.release_queue(run_id)
```

The `_tasks` dict (in-memory registry of active `asyncio.Task` objects) is the correct signal: if the task is still in `_tasks`, training is still running and the queue must stay accessible. The orphan-queue cleanup (120s after training finishes via `_cleanup` callback) provides the safety net.

### Verified fix paths

- **Normal completion**: training finishes → `_cleanup` removes from `_tasks` → SSE consumes terminal event → `finally` releases queue ✅
- **Page refresh during training**: disconnect → `run_id in _tasks` → queue preserved → new page reconnects ✅
- **Orphan safety net**: 120s after training completes, `_orphan_queue_release()` releases any lingering queue ✅

## Files modified

- `anvil/api/v1/training.py` — 1 edit: conditional `release_queue` in `event_stream()` finally block

## Discoveries

- [[Discoveries/training-sse-queue-released-on-disconnect|Training SSE Queue Released Prematurely on Client Disconnect]]