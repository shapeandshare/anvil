---
title: Training SSE Queue Released Prematurely on Client Disconnect
type: discovery
tags:
  - type/discovery
  - domain/training
  - domain/ui
created: '2026-06-28'
updated: '2026-06-28'
status: draft
source: agent
aliases:
  - training-sse-queue-released-on-disconnect
code-refs:
  - anvil/api/v1/training.py
---

# Training SSE Queue Released Prematurely on Client Disconnect

**Discovered**: 2026-06-28
**Context**: `anvil/api/v1/training.py` — `event_stream()` generator in `stream_training()` route
**Severity**: P2 (active training appears errored after page refresh)

## The problem

When a user starts training from `/v1/training-page` and refreshes the page (or navigates away and back), the ongoing training job continues running in the background. However, the UI reports it as "errored" and is unable to reconnect.

The root cause is in the `event_stream()` async generator used by the SSE streaming endpoint (`GET /v1/training/stream/{run_id}`). Its `finally` block unconditionally called `svc.release_queue(run_id)`, which removes the per-run `asyncio.Queue` from `TrainingService._queues`.

The chain of events:

1. Training starts → `TrainingService.reserve_run()` creates an `asyncio.Queue` and stores it in `self._queues[run_id]`
2. SSE consumer connects → `stream_training()` fetches the queue and creates an `event_stream()` generator
3. User refreshes page → old `EventSource` disconnects → ASGI server cancels the generator → `finally` block runs → `svc.release_queue(run_id)` removes the queue from `_queues`
4. New page loads → `restoreTrainingSession()` sees "streaming" status in `sessionStorage` → calls `reconnectToRun()` → `GET /v1/training/{run_id}/status` → `svc.get_queue(run_id)` returns `None` → 404 → `_staleRun()` marks run as "errored"
5. Training continues running, pushing events into the queue object (still alive via closure reference) — but nobody can reach it

## Fix

Changed the `event_stream()` `finally` block to only `release_queue` if the training task has already completed (no longer in `_tasks` dict):

```python
finally:
    if run_id not in _tasks:
        svc.release_queue(run_id)
```

When the client disconnects while training is still active, `_tasks` still contains the `run_id`, so the queue is preserved. The new page's reconnect flow finds the queue and resumes the SSE stream. The orphan-queue cleanup task (120s after training finishes) provides a safety net for queues that are never reconnected.

## See also

- [[Sessions/2026-06-28-training-sse-reconnection|Training SSE Reconnection on Page Refresh]] — session log
- [[Discoveries/backup-sse-state-lost-on-page-refresh|Backup SSE State Lost on Page Refresh]] — similar pattern on the Operations page