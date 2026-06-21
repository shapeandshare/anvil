---
created: '2026-06-21T00:00:00.000Z'
tags:
  - type/session-log
  - domain/architecture
  - domain/core
title: Thread Model Review — Full Codebase Scan
type: session-log
updated: '2026-06-21T00:00:00.000Z'
---
# Thread Model Review — Full Codebase Scan

**Date**: 2026-06-21
**Reviewer**: Sisyphus (agent)

## Summary

Conducted a comprehensive thread model review of the entire `anvil/` codebase across 8 analysis categories (TC-01 through TC-08). Produced a structured report at `docs/thread-model-review-2026-06-21.md` and a running CSV tracker at `docs/thread-model-tracker.csv`.

**Findings**: 21 total (2 P0, 6 P1, 8 P2, 5 INFO)

## Thread Contexts Found

1. **MPSSamplerThread** (`mps_sampler_thread.py:19`) — daemon thread with own event loop, periodic MPS GPU metric sampling
2. **Demo model warmup thread** (`app.py:143`) — daemon thread, fire-and-forget startup warmup
3. **MLflow subprocess** (`supervisor/services.py:130`) — managed `mlflow server` subprocess
4. **Supervisor processes** (`supervisor/supervisor.py:153`) — generic subprocess management
5. **Training thread pool** — `run_in_executor` offloads sync training to default executor
6. **Content store thread pool** — `run_in_executor` for filesystem I/O
7. **TrackingService thread pool** — 40+ `run_in_executor` calls for MLflow sync client
8. **CLI training** — `asyncio.run()` at top-level entry points

## Key Risks Found

| Severity | Finding | File |
|----------|---------|------|
| **P0** | Unbounded `asyncio.Queue` in training SSE — OOM risk | `training.py:393` |
| **P0** | Unbounded `_injection_queue` — memory growth | `content.py:57` |
| **P1** | TOCTOU race on `_bootstrap_lock` | `health_ops.py:60` |
| **P1** | `asyncio.run()` latent fragility in sync methods | `training.py:267,290,381` |
| **P1** | MPS thread not stopped on normal completion | `training.py:582` |
| **P1** | No shutdown task cancellation on FastAPI lifespan | `app.py:152-154` |

## Architecture Assessment

- **Overall**: Sound — ADR-002 sync-core/async-bridge pattern is correctly implemented
- **Strongest**: Process lifecycle management (SIGTERM→SIGKILL with timeout), MPSSamplerThread loop cleanup pattern
- **Weakest**: Unbounded queues (2× P0), incomplete FastAPI lifespan shutdown, `asyncio.get_event_loop()` vs `get_running_loop()` (24+ occurrences of deprecated pattern)

## Files Changed
- `docs/thread-model-review-2026-06-21.md` (new — structured report)
- `docs/thread-model-tracker.csv` (new — running CSV tracker)
