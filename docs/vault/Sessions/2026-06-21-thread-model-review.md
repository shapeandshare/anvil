---
aliases:
  - Thread Model Review
  - Concurrency Audit
source: agent
created: '2026-06-21T00:00:00.000Z'
source: agent
aliases:
  - Thread Model Review — Full Codebase Scan
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

## Fixes Applied (Same Session)

PR #120 (merged `dc8992c` to main):

| TMR | Severity | Fix |
|-----|----------|-----|
| TMR-001 | P0 | Training SSE queue: `maxsize=1024` + `_enqueue_or_drop` helper with `QueueFull` handling |
| TMR-002 | P0 | Content injection queue: `maxsize=128` + `try/except asyncio.QueueFull` |
| TMR-019 | P1 | Bootstrap lock: replaced TOCTOU `.locked()` check with `_bootstrap_in_progress` flag + `try/finally` |
| TMR-005 | P1 | **False positive** — `mps_thread.stop()` correctly called in `on_complete` callback |

### Tests Added
- `test_reserve_run_creates_bounded_queue` — verifies `maxsize=1024`
- `test_enqueue_or_drop_drops_when_queue_full` — validates silent drop on overflow
- `test_rebootstrap_lock_rejects_concurrent` — verifies 409 on concurrent bootstrap

### Tracker Status
- 2 P0 → **0 P0** (both fixed)
- 3 P0/P1 findings → **0 open** (fixed or false_positive)
- Tracker: `docs/thread-model-tracker.csv` updated

## Files Changed
- `docs/thread-model-review-2026-06-21.md` (new — structured report)
- `docs/thread-model-tracker.csv` (new — running CSV tracker)
- `anvil/services/training/training.py` (TMR-001 fix)
- `anvil/api/v1/content.py` (TMR-002 fix)
- `anvil/api/v1/health_ops.py` (TMR-019 fix)
- `tests/api/test_training_sse_signals.py` (tests for TMR-001)
- `tests/test_bootstrap.py` (test for TMR-019)

## Related

- [[Decisions/ADR-002-sync-core-async-bridge|ADR-002: Sync Core, Async Bridge]] — threading model architecture decision
- [[Reference/ArchitectureOverview|Architecture]] — codebase threading context
- [[Specs/Specs|Specs]] — feature specification index
