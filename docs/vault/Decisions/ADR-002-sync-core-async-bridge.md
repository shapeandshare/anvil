---
title: ADR-002 — Sync Core Engine / Async SSE Bridge
type: decision
tags:
- type/decision
- domain/core
created: 2026-06-12
updated: 2026-06-12
aliases:
- ADR-002 — Sync Core Engine / Async SSE Bridge
source: agent
related:
  - '[[Reference/DualBackend]]'
code-refs:
- anvil/core/engine.py
- anvil/services/training/training_service.py
- anvil/api/v1/training.py
---

# ADR-002: Sync Core Engine with Async SSE Bridge

**Status**: Accepted

## Context

The training engine (`anvil/core/engine.py`) is a synchronous, CPU-bound loop — it must be, because it's a tight numerical loop with zero pip dependencies. However, the web layer (FastAPI) is fully async and needs to stream real-time progress to the browser via SSE.

This creates a fundamental impedance mismatch: sync blocking code cannot run on the asyncio event loop without blocking all other requests.

## Decision

### Architecture

1. **Core engine runs in a thread executor**: `loop.run_in_executor(None, train, ...)` offloads the entire training loop to a thread pool thread.

2. **SSE events bridge via `asyncio.Queue` + `run_coroutine_threadsafe`**: The sync `progress_callback` injects events into an `asyncio.Queue` using `asyncio.run_coroutine_threadsafe(queue.put(msg), loop)` — the only thread-safe way to wake up an async queue from a sync context.

3. **FastAPI SSE endpoint reads from the same queue**: `POST /v1/training/stream/{run_id}` polls `queue.get()` with a 30s timeout, yielding SSE events. A heartbeat event prevents connection timeout on long train steps.

4. **Run ID reserves the queue before training starts**: The sequence is: reserve_run() → allocate Queue → start async task → immediately return run_id. This ensures the SSE endpoint can find its queue even before training begins.

### Flow

```
POST /v1/training/start
  ├── svc.reserve_run() → allocates run_id + asyncio.Queue
  ├── asyncio.create_task(svc.start_training(config, run_id, ...))
  └── return {run_id, ...}

Browser then opens GET /v1/training/stream/{run_id}
  └── reads from the same Queue via async generator

Training task:
  ├── _load_docs() via run_in_executor (blocking I/O)
  ├── train(docs, ...) via run_in_executor (CPU-bound)
  │     └── progress_callback → run_coroutine_threadsafe(queue.put)
  └── on_complete → queue.put({"event": "complete", ...})
```

### Code Locations

- **Queue allocation**: `TrainingService.reserve_run()` in `anvil/services/training.py:57-61`
- **Training launch**: `TrainingService.start_training()` same file, lines 63-118
- **Thread bridge**: `loop.run_in_executor(None, lambda: train(...))` at line 92-104
- **SSE bridge**: `asyncio.run_coroutine_threadsafe(queue.put(...), loop)` at line 80-88
- **SSE endpoint**: `stream_training()` in `anvil/api/v1/training.py:119-142`

## Alternatives Considered

1. **Make core engine async throughout**: Rejected — `train()` is a tight numerical loop; adding `await` everywhere would not make it faster and would complicate the educational clarity.

2. **Use multiprocessing with pipe/socket**: Rejected — overkill for a single training process; adds serialization overhead for `Value` objects.

3. **Poll from a file/pipe**: Rejected — SSE is designed for push-based streaming; file polling adds latency and I/O overhead.

4. **Use `asyncio.run_coroutine_threadsafe` for callbacks only**: Chosen — minimal, correct, well-documented Python pattern.

## Consequences

- + Thread-safe concerns: `progress_callback` must not mutate shared state
- + Thread pool manages lifecycle: no zombie threads if disconnected
- + MLflow logging also runs via callbacks from the same thread
- − Cannot cancel mid-step (thread executor doesn't support Python-level cancellation)
- − `asyncio.Queue` is unbounded by default; memory pressure if consumer is slower than producer

## Compliance

- The `train()` function in `anvil/core/engine.py` must remain pure sync with no asyncio imports
- All SSE event production must go through `TrainingService._queues[run_id]` — never directly in route handlers
- `run_coroutine_threadsafe` is the only allowed thread-to-async bridge

## See Also

- [[Decisions/README|Decisions]]
