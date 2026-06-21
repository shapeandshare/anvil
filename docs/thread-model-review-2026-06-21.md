# Thread Model Review — 2026-06-21

**Living task-tracking report.** Last updated: 2026-06-21
**Target**: `anvil/`
**Scope**: Full codebase scan — threading primitives, event loop usage, sync↔async bridges, queues, lock discipline, lifecycle management
**Reviewer**: Sisyphus (agent)

---

## Scan History

| Scan Date | New Findings | Resolved | Regressed | Total Open | Coverage |
|-----------|-------------|----------|-----------|------------|----------|
| 2026-06-21 | +21 | — | — | 21 | `anvil/` (all `.py` files) |

---

## Progress Summary

| Metric | Value |
|--------|-------|
| Total findings (all time) | **21** |
| Currently open | **21** |
| In progress | **0** |
| Fixed / resolved | **0** |
| Wontfix / False positive | **0** |
| Resolved rate | **0%** |

### Open Findings by Severity

| Severity | Count |
|----------|-------|
| P0 | 2 |
| P1 | 6 |
| P2 | 8 |
| INFO | 5 |

### Trend Since Last Review

- New findings added: +21
- Findings resolved: 0
- Findings regressed: 0

> ⚠️ **Top 3 Risks**:
> 1. **Unbounded `asyncio.Queue`** — `TrainingService._queues` has no `maxsize`. Training thread pushes per-step events via `run_coroutine_threadsafe`. A slow/disconnected SSE consumer causes unbounded memory growth (OOM risk).
> 2. **`_bootstrap_lock` TOCTOU race** — `anvil/api/v1/health_ops.py:60` checks `_bootstrap_lock.locked()` before acquiring, allowing two concurrent bootstrap requests to proceed.
> 3. **`asyncio.get_event_loop()` in CLI progress callback** — `anvil/cli.py:276` calls `asyncio.get_event_loop()` from a training worker thread with no running loop, which may fail.

---

## Running Tracker Summary

| Finding ID | Severity | Category | Status | Date Found | Date Closed | File |
|------------|----------|----------|--------|------------|-------------|------|
| TMR-001 | P0 | TC-05 | open | 2026-06-21 | — | `anvil/services/training/training.py:393` |
| TMR-002 | P0 | TC-05 | open | 2026-06-21 | — | `anvil/api/v1/content.py:57` |
| TMR-003 | P1 | TC-03 | open | 2026-06-21 | — | `anvil/services/training/training.py:267,290,381` |
| TMR-004 | P1 | TC-03 | open | 2026-06-21 | — | `anvil/services/inference/demo_model_provider.py:103,365` |
| TMR-005 | P1 | TC-06 | open | 2026-06-21 | — | `anvil/api/v1/training.py:362,582` |
| TMR-006 | P1 | TC-04 | open | 2026-06-21 | — | `anvil/services/training/training.py:48,516-518` |
| TMR-007 | P1 | TC-06 | open | 2026-06-21 | — | `anvil/api/app.py:152-154` |
| TMR-008 | P2 | TC-02 | open | 2026-06-21 | — | `anvil/services/training/training.py:393,558` |
| TMR-009 | P2 | TC-02 | open | 2026-06-21 | — | `anvil/services/inference/demo_model_provider.py:292-293` |
| TMR-010 | P2 | TC-07 | open | 2026-06-21 | — | `anvil/services/inference/demo_model_provider.py:360-371` |
| TMR-011 | P2 | TC-01 | open | 2026-06-21 | — | `anvil/api/app.py:143-147` |
| TMR-012 | P2 | TC-08 | open | 2026-06-21 | — | `anvil/services/inference/demo_model_provider.py:36,311` |
| TMR-013 | P2 | TC-02 | open | 2026-06-21 | — | `anvil/supervisor/supervisor.py:23,131` |
| TMR-014 | INFO | TC-01 | open | 2026-06-21 | — | `anvil/services/tracking/mps_sampler_thread.py:19,44` |
| TMR-015 | INFO | TC-07 | open | 2026-06-21 | — | `anvil/services/tracking/mps_sampler_thread.py:59-81` |
| TMR-016 | INFO | TC-07 | open | 2026-06-21 | — | `anvil/services/tracking/tracking.py` |
| TMR-017 | INFO | TC-02 | open | 2026-06-21 | — | `anvil/supervisor/services.py:47` |
| TMR-018 | INFO | TC-01 | open | 2026-06-21 | — | `anvil/api/v1/training.py:584` |
| TMR-019 | P1 | TC-08 | open | 2026-06-21 | — | `anvil/api/v1/health_ops.py:60` |
| TMR-020 | P2 | TC-07 | open | 2026-06-21 | — | `anvil/cli.py:276` |
| TMR-021 | INFO | TC-07 | open | 2026-06-21 | — | `anvil/services/tracking/mps_sampler_thread.py:59` |

A full CSV export is maintained at `docs/thread-model-tracker.csv`.

---

## Detailed Findings

## Detailed Findings

### TC-01 — Thread Context Inventory

| ID | Severity | Status | File | Title | First Seen | Last Confirmed | Resolved |
|----|----------|--------|------|-------|------------|----------------|----------|
| TMR-014 | INFO | open | anvil/services/tracking/mps_sampler_thread.py:19,44 | MPSSamplerThread — dedicated daemon thread | 2026-06-21 | 2026-06-21 | — |
| TMR-011 | P2 | open | anvil/api/app.py:143-147 | Demo model warmup daemon thread | 2026-06-21 | 2026-06-21 | — |
| TMR-018 | INFO | open | anvil/api/v1/training.py:584 | asyncio.create_task for training run | 2026-06-21 | 2026-06-21 | — |

#### TMR-014: MPSSamplerThread — dedicated daemon thread with its own event loop
- **Severity**: INFO
- **Status**: open
- **File**: `anvil/services/tracking/mps_sampler_thread.py:19,44,59`
- **Category**: TC-01
- **First seen**: 2026-06-21
- **Last confirmed**: 2026-06-21
- **Pattern**:
  ```python
  class MPSSamplerThread(threading.Thread):              # line 19
      def __init__(self, ...):
          super().__init__(daemon=True, name=...)        # line 44
          self._loop = asyncio.new_event_loop()           # line 59 (in run())
  ```
- **Thread type**: Dedicated `threading.Thread`, daemon
- **Event loop**: ✅ Yes — owns its own `asyncio.new_event_loop()` (line 59), runs `self._loop.run_until_complete()` (lines 65-74)
- **Lifecycle**: Started by `MPSSamplerThread.start()` at `api/v1/training.py:362`. Stopped by `MPSSamplerThread.stop()` (sets `_stop_event`). Loop cleanup in `finally: self._loop.close()` at lines 79-81.
- **Risk**: Properly designed daemon thread with its own event loop. The `finally` block closes the loop. Low risk.

#### TMR-011: Demo model warmup daemon thread
- **Severity**: P2
- **Status**: open
- **File**: `anvil/api/app.py:143-147`
- **Category**: TC-01
- **First seen**: 2026-06-21
- **Last confirmed**: 2026-06-21
- **Pattern**:
  ```python
  threading.Thread(
      target=warmup_demo_via_system_pipeline,
      name="demo-model-warmup",
      daemon=True,
  ).start()
  ```
- **Thread type**: Dedicated `threading.Thread`, daemon
- **Event loop**: ❌ No — runs a synchronous function. However, `warmup_demo_via_system_pipeline()` calls `asyncio.run()` internally which creates/ephemeral event loops.
- **Lifecycle**: Fire-and-forget on app startup. No stop mechanism.
- **Risk**: Daemon thread means it won't block exit. However, if `warmup_demo_via_system_pipeline()` is stuck (e.g., waiting on I/O), it will be abruptly terminated on process exit. The try/except inside the function mitigates this — no unhandled exceptions.

#### TMR-018: asyncio.create_task for training run
- **Severity**: INFO
- **Status**: open
- **File**: `anvil/api/v1/training.py:584`
- **Category**: TC-01
- **First seen**: 2026-06-21
- **Last confirmed**: 2026-06-21
- **Pattern**:
  ```python
  task = asyncio.create_task(_run_training())    # line 584
  _tasks[run_id] = task
  task.add_done_callback(_cleanup)               # line 597
  ```
- **Task type**: asyncio Task on the main event loop
- **Event loop**: Shares the main FastAPI uvicorn event loop
- **Lifecycle**: Spawned by POST `/training/start` handler. Cleanup callback removes from `_tasks` dict on completion.
- **Risk**: Task is not cancelled on FastAPI lifespan shutdown (see TMR-007). If the server shuts down while training is in progress, the task is abruptly cancelled.

---

### TC-02 — Shared State & Thread Safety

| ID | Severity | Status | File | Title | First Seen | Last Confirmed | Resolved |
|----|----------|--------|------|-------|------------|----------------|----------|
| TMR-008 | P2 | open | anvil/services/training/training.py:393,558 | TrainingService._queues dict — shared between threads | 2026-06-21 | 2026-06-21 | — |
| TMR-009 | P2 | open | anvil/services/inference/demo_model_provider.py:292-293 | _demo_provider._model / _chars — module-level singleton | 2026-06-21 | 2026-06-21 | — |
| TMR-013 | P2 | open | anvil/supervisor/supervisor.py:23,131 | _PID_DIR and _processes — module-level mutable state | 2026-06-21 | 2026-06-21 | — |
| TMR-017 | INFO | open | anvil/supervisor/services.py:47 | MLflowService.process — shared subprocess reference | 2026-06-21 | 2026-06-21 | — |

#### TMR-008: TrainingService._queues dict — shared between threads
- **Severity**: P2
- **Status**: open
- **File**: `anvil/services/training/training.py:47,393,558`
- **Category**: TC-02
- **First seen**: 2026-06-21
- **Last confirmed**: 2026-06-21
- **Pattern**:
  ```python
  self._queues: dict[int, asyncio.Queue] = {}            # line 47 — init
  self._queues[run_id] = asyncio.Queue()                 # line 393 — reserve_run()
  self._queues.pop(run_id, None)                         # line 558 — finally cleanup
  ```
  Accessed from: async event loop thread (SSE consumer → `get_queue()`), and the `progress_callback` closure runs `run_coroutine_threadsafe(queue.put(...))` from the training thread pool worker.
- **Threads involved**: Main event loop (consumer at `api/v1/training.py:684`), training thread pool worker (producer via `run_coroutine_threadsafe`), plus `reserve_run()` (event loop), `stop_run()` (any thread, sets `stop_event`), `start_training()` (event loop).
- **Protection**: Dict mutations (`pop`, `__setitem__`) happen on the event loop thread only — no cross-thread dict access. Queue access is thread-safe by design (`asyncio.Queue` itself is not thread-safe but `run_coroutine_threadsafe` serializes access).
- **Risk**: Low. The dict is only mutated on the event loop thread. The `progress_callback` closure captures the queue reference at closure creation time, so it doesn't need to access _queues dict from the worker thread.
- **Recommendation**: Add a comment documenting the thread-safety invariants.

#### TMR-009: _demo_provider — module-level singleton with mutable state
- **Severity**: P2
- **Status**: open
- **File**: `anvil/services/inference/demo_model_provider.py:292-293,387`
- **Category**: TC-02
- **First seen**: 2026-06-21
- **Last confirmed**: 2026-06-21
- **Pattern**:
  ```python
  _demo_provider = DemoModelProvider()                    # line 387 — module-level singleton
  
  class DemoModelProvider:
      def __init__(self):
          self._model: LlamaModel | None = None           # line 292
          self._chars: list[str] | None = None            # line 293
  ```
- **Threads involved**: Any request-handling thread, plus the background warmup daemon thread.
- **Protection**: `_DEMO_TRAIN_LOCK` (threading.Lock, line 36) protects `get_model()` via double-checked locking (lines 311-314). The warmup thread writes `_demo_provider._model` and `_demo_provider._chars` directly (line 264-265).
- **Risk**: The warmup thread (daemon, at `app.py:143-147`) writes directly to `_demo_provider._model = model` and `_demo_provider._chars = uchars` (lines 264-265) **without** holding `_DEMO_TRAIN_LOCK`. This races with `get_model()` which reads `self._model` (line 307) before acquiring the lock.
- **Recommendation**: Either (a) have the warmup thread write through a method that acquires `_DEMO_TRAIN_LOCK`, or (b) make `_model`/`_chars` an atomic reference that's a plain write. Since CPython's GIL makes attribute writes atomic, the practical risk is low (stale read of a reference, not a torn write). Flagging as P2 for correctness.

#### TMR-013: _PID_DIR and _processes — module-level mutable state in supervisor
- **Severity**: P2
- **Status**: open
- **File**: `anvil/supervisor/supervisor.py:23,131`
- **Category**: TC-02
- **First seen**: 2026-06-21
- **Last confirmed**: 2026-06-21
- **Pattern**:
  ```python
  _PID_DIR = "logs"                                       # line 23 — module-level
  
  class ProcessSupervisor:
      def __init__(self, log_dir="logs"):
          self._processes: dict[str, subprocess.Popen] = {}  # line 131
  ```
- **Threads involved**: Main event loop (FastAPI routes call `start`, `stop`, `stop_all`).
- **Protection**: No explicit lock. All access is on the event loop thread in practice.
- **Risk**: `_PID_DIR` is a module-level string constant — only mutated by reassignment, which would be across all uses. `_processes` dict is only accessed from the event loop thread in normal operation. Low risk.
- **Recommendation**: Make `_PID_DIR` a module-level constant proper (rename to `PID_DIR` or add type annotation). For `_processes`, add a comment documenting the single-thread access pattern.

#### TMR-017: MLflowService.process — shared subprocess reference
- **Severity**: INFO
- **Status**: open
- **File**: `anvil/supervisor/services.py:47`
- **Category**: TC-02
- **First seen**: 2026-06-21
- **Last confirmed**: 2026-06-21
- **Pattern**:
  ```python
  self.process: subprocess.Popen | None = None            # line 47
  ```
- **Threads involved**: Main event loop (lifespan startup calls `start()`, lifespan shutdown calls `stop()`).
- **Protection**: Single-thread access in practice (lifespan is sequential).
- **Risk**: No concurrent access. INFO-level documentation finding.

---

### TC-03 — Sync↔Async Bridge Patterns

| ID | Severity | Status | File | Title | First Seen | Last Confirmed | Resolved |
|----|----------|--------|------|-------|------------|----------------|----------|
| TMR-003 | P1 | open | anvil/services/training/training.py:267,290,381 | asyncio.run() inside sync methods called from event loop | 2026-06-21 | 2026-06-21 | — |
| TMR-004 | P1 | open | anvil/services/inference/demo_model_provider.py:103,365 | asyncio.run() in demo model provider | 2026-06-21 | 2026-06-21 | — |

#### TMR-003: asyncio.run() inside sync methods called from event loop
- **Severity**: P1
- **Status**: open
- **File**: `anvil/services/training/training.py:267,290,381`
- **Category**: TC-03
- **First seen**: 2026-06-21
- **Last confirmed**: 2026-06-21
- **Pattern**:
  ```python
  # Line 267 (in _load_docs when dataset_id is set):
  return asyncio.run(_load())
  
  # Line 290 (in _load_docs fallback for default corpus):
  return asyncio.run(_load_default())
  
  # Line 381 (in _load_docs_from_version):
  return asyncio.run(_load())
  ```
- **Bridge type**: `asyncio.run()` from sync context
- **Direction**: sync → async (creates a new event loop, runs async code, closes loop)
- **Call site**: `_load_docs()` is called from `start_training()` at line 479 via `await loop.run_in_executor(None, self._load_docs, ...)`. So `_load_docs()` runs in a **thread pool worker**, NOT on the event loop.
- **Risk**: Actually **safe** because `_load_docs()` runs in a thread pool worker via `run_in_executor` — there is no running event loop in that thread. The `asyncio.run()` creates a fresh event loop. However, if `_load_docs()` were ever called directly from the event loop (e.g., a future code path), it would raise `RuntimeError: asyncio.run() cannot be called from a running event loop`. This is a latent fragility.
- **Recommendation**: Add a docstring/comment documenting that `_load_docs()` MUST be called from a thread pool worker (not the event loop), or refactor to make `_load_docs` itself async.

#### TMR-004: asyncio.run() in demo model provider
- **Severity**: P1
- **Status**: open
- **File**: `anvil/services/inference/demo_model_provider.py:103,365`
- **Category**: TC-03
- **First seen**: 2026-06-21
- **Last confirmed**: 2026-06-21
- **Pattern**:
  ```python
  # Line 103 (in warmup_demo_via_system_pipeline, called from daemon thread):
  docs = asyncio.run(_get_docs())
  
  # Line 270 (in warmup_demo_via_system_pipeline):
  asyncio.run(_run())
  
  # Line 365 (in _load_demo_docs, no running loop):
  return asyncio.run(_load())
  ```
- **Bridge type**: `asyncio.run()` from sync context
- **Direction**: sync → async
- **Call sites**: `warmup_demo_via_system_pipeline()` runs in a daemon thread (no event loop), so `asyncio.run()` at lines 103 and 270 is safe. `_load_demo_docs()` at line 339 also handles the running-loop case with a `try/except RuntimeError` workaround (lines 359-371).
- **Risk**: The `_load_demo_docs()` workaround (lines 359-371) detects a running loop and submits `asyncio.run()` to a `ThreadPoolExecutor`. This is a correct but fragile pattern. If called while a loop is running, it creates a new thread + event loop for every invocation.
- **Recommendation**: The workaround is correct but should be documented with a comment about the `ThreadPoolExecutor` overhead. Consider making `_load_demo_docs` async to eliminate the workaround.

---

### TC-04 — Cancellation & Stop Signal Propagation

| ID | Severity | Status | File | Title | First Seen | Last Confirmed | Resolved |
|----|----------|--------|------|-------|------------|----------------|----------|
| TMR-006 | P1 | open | anvil/services/training/training.py:48,516-518 | No mid-step cancellation — threading.Event checked at step boundaries | 2026-06-21 | 2026-06-21 | — |

#### TMR-006: No mid-step cancellation — threading.Event checked only at step boundaries
- **Severity**: P1
- **Status**: open
- **File**: `anvil/services/training/training.py:48,394,516-518`
- **Category**: TC-04
- **First seen**: 2026-06-21
- **Last confirmed**: 2026-06-21
- **Pattern**:
  ```python
  # Stop event per run:
  self._stop_events[run_id] = threading.Event()           # line 394
  
  # Stop is checked at step boundaries in the progress_callback:
  def progress_callback(step, loss, ...):                  # line 109
      stop_event = self._stop_events.get(run_id)           # line 116
      if stop_event is not None and stop_event.is_set():   # line 117
          raise StopRequested(...)                         # line 118
  ```
- **Mechanism**: `stop_run(run_id)` → `event.set()` → next `progress_callback` invocation raises `StopRequested`.
- **Latency**: At most 1 training step. The callback fires after each step, so stop takes effect at the next step boundary.
- **Gap**: During a single long step (e.g., large batch, slow GPU kernel), stop cannot interrupt mid-step. Thread pool workers don't support Python-level cancellation.
- **Risk**: Acceptable for this codebase (educational LLM training, steps are fast). Documented in ADR-002 as a known consequence. Flagging as P1 because it's a known limitation with no mitigation.
- **Recommendation**: For scenarios where mid-step cancellation matters, add a `SIGINT` handler or use a `concurrent.futures.Future.cancel()` approach (though this only works if the worker periodically checks cancellation).

---

### TC-05 — asyncio.Queue Backpressure & Capacity

| ID | Severity | Status | File | Title | First Seen | Last Confirmed | Resolved |
|----|----------|--------|------|-------|------------|----------------|----------|
| TMR-001 | P0 | open | anvil/services/training/training.py:393 | TrainingService._queues created unbounded — no maxsize | 2026-06-21 | 2026-06-21 | — |
| TMR-002 | P0 | open | anvil/api/v1/content.py:57 | _injection_queue unbounded — no maxsize | 2026-06-21 | 2026-06-21 | — |

#### TMR-001: TrainingService._queues created unbounded — no maxsize
- **Severity**: P0
- **Status**: open
- **File**: `anvil/services/training/training.py:393`
- **Category**: TC-05
- **First seen**: 2026-06-21
- **Last confirmed**: 2026-06-21
- **Pattern**:
  ```python
  # Line 393 — reserve_run():
  self._queues[run_id] = asyncio.Queue()   # NO maxsize!
  
  # Producer (training thread, every step):
  asyncio.run_coroutine_threadsafe(        # line 145
      queue.put({"event": "metrics", ...}),# line 146
      loop,
  )
  ```
- **Queue location**: `TrainingService.reserve_run()` at `training.py:393`, consumed at `api/v1/training.py:684` and `cli.py:400`.
- **Maxsize**: **UNBOUNDED** — no `maxsize=N` parameter.
- **Producer rate**: Training thread pushes one event per step (potentially ~1000+ events/sec for small models), plus divergence/milestone/submitted events.
- **Consumer rate**: SSE endpoint reads via `asyncio.wait_for(queue.get(), timeout=30)` at line 684. If the SSE client disconnects, the consumer stops reading entirely.
- **Memory risk**: **HIGH** — if the SSE client disconnects or is slow, events accumulate without bound. A 1000-step training run with one disconnect would accumulate ~1000 events in the queue.
- **Recommendation**: Set `asyncio.Queue(maxsize=1024)` and handle `asyncio.QueueFull` on the producer side by either (a) dropping old events, or (b) blocking the training thread (which would provide backpressure but may slow training). Option (a) is preferred for SSE streaming.
  
  ```python
  self._queues[run_id] = asyncio.Queue(maxsize=1024)
  ```
  
  Producer side should use `put_nowait()` with a fallback:
  ```python
  try:
      queue.put_nowait({"event": "metrics", ...})
  except asyncio.QueueFull:
      pass  # Drop stale metrics when consumer is slow
  ```

#### TMR-002: _injection_queue unbounded — no maxsize
- **Severity**: P0
- **Status**: open
- **File**: `anvil/api/v1/content.py:57`
- **Category**: TC-05
- **First seen**: 2026-06-21
- **Last confirmed**: 2026-06-21
- **Pattern**:
  ```python
  # Line 57 — module-level:
  _injection_queue: asyncio.Queue[dict[str, str]] = asyncio.Queue()  # NO maxsize!
  
  # Producer:
  _injection_queue.put_nowait({...})    # line 525 — uses put_nowait (no backpressure!)
  
  # Consumer:
  await asyncio.wait_for(_injection_queue.get(), timeout=30)  # line 980
  ```
- **Queue location**: Module-level at `api/v1/content.py:57`, consumed at `api/v1/content.py:980` in SSE stream.
- **Maxsize**: **UNBOUNDED**.
- **Producer rate**: One event per `IngestionService.accept()` call. Low rate (user-triggered).
- **Consumer rate**: SSE endpoint reads via 30s timeout. If client disconnects, accumulation.
- **Memory risk**: **MEDIUM** — lower risk than TMR-001 because injection events are infrequent (user-triggered, not per-step). But still unbounded.
- **Recommendation**: Set `asyncio.Queue(maxsize=128)` as a safety bound. Since the producer already uses `put_nowait` (line 525), `QueueFull` would raise — catch it and either retry or drop the event.

---

### TC-06 — Thread Lifecycle & Resource Cleanup

| ID | Severity | Status | File | Title | First Seen | Last Confirmed | Resolved |
|----|----------|--------|------|-------|------------|----------------|----------|
| TMR-005 | P1 | open | anvil/api/v1/training.py:362,582 | MPSSamplerThread not stopped on normal completion | 2026-06-21 | 2026-06-21 | — |
| TMR-007 | P1 | open | anvil/api/app.py:152-154 | No task cancellation or queue drainage on FastAPI shutdown | 2026-06-21 | 2026-06-21 | — |

#### TMR-005: MPSSamplerThread not stopped on normal completion
- **Severity**: P1
- **Status**: open
- **File**: `anvil/api/v1/training.py:362,566-582`
- **Category**: TC-06
- **First seen**: 2026-06-21
- **Last confirmed**: 2026-06-21
- **Pattern**:
  ```python
  # Line 361-362 — start:
  mps_thread = MPSSamplerThread(tracking_svc, mlflow_run_id, interval=5.0)
  mps_thread.start()
  
  # Line 566-582 — only stopped in exception handler:
  except Exception as exc:
      ...
      if mps_thread is not None:
          mps_thread.stop()                                # line 582
  ```
- **Issue**: `mps_thread.stop()` is called ONLY in the `except Exception` handler (line 566-582). When training completes **normally** (`try` block succeeds), `mps_thread.stop()` is **never called**. The thread runs until the process exits.
- **Risk**: Since `daemon=True`, the thread doesn't prevent process exit. However, if multiple training runs complete normally, each leaves a sampler thread running (sampling every 5s). Accumulated threads waste resources and keep event loops open.
- **Recommendation**: Add `mps_thread.stop()` in a `finally:` block at the end of `_run_training()`, or attach it to the `_cleanup` callback at line 587.

#### TMR-007: No task cancellation or queue drainage on FastAPI shutdown
- **Severity**: P1
- **Status**: open
- **File**: `anvil/api/app.py:152-154`
- **Category**: TC-06
- **First seen**: 2026-06-21
- **Last confirmed**: 2026-06-21
- **Pattern**:
  ```python
  # Lifespan shutdown — lines 152-154:
  yield
  svc = getattr(app.state, "mlflow", None)
  if svc is not None:
      svc.stop()
  ```
- **Issue**: The lifespan handler only stops the MLflow service. It does NOT:
  - Cancel in-flight `_run_training` asyncio tasks (registered in `_tasks` dict at `api/v1/training.py:585`)
  - Drain or signal training SSE queues
  - Call `MPSSamplerThread.stop()` for any active sampler threads
  - Call `ProcessSupervisor.stop_all()` for any tracked processes
- **Risk**: On server shutdown, in-flight training tasks are cancelled abruptly by the event loop being closed. Queues are abandoned. MPS sampler daemon threads are terminated by process exit.
- **Recommendation**: In the lifespan shutdown handler, iterate `_tasks` and cancel each task with a timeout, then call `supervisor.stop_all()` if a supervisor is registered in `app.state`. This provides graceful shutdown for in-flight operations.

---

### TC-07 — Event Loop Confusion & Cross-Loop Access

| ID | Severity | Status | File | Title | First Seen | Last Confirmed | Resolved |
|----|----------|--------|------|-------|------------|----------------|----------|
| TMR-010 | P2 | open | anvil/services/inference/demo_model_provider.py:360-371 | ThreadPoolExecutor workaround for running event loop | 2026-06-21 | 2026-06-21 | — |
| TMR-015 | INFO | open | anvil/services/tracking/mps_sampler_thread.py:59-81 | MPSSamplerThread creates own event loop — correct pattern | 2026-06-21 | 2026-06-21 | — |
| TMR-016 | INFO | open | anvil/services/tracking/tracking.py | asyncio.get_event_loop() in TrackingService — relies on default loop | 2026-06-21 | 2026-06-21 | — |
| TMR-020 | P2 | open | anvil/cli.py:276 | asyncio.get_event_loop() from sync callback in worker thread | 2026-06-21 | 2026-06-21 | — |
| TMR-021 | INFO | open | anvil/services/tracking/mps_sampler_thread.py:59 | new_event_loop() without set_event_loop() — intentional isolation | 2026-06-21 | 2026-06-21 | — |

#### TMR-010: ThreadPoolExecutor workaround for running event loop
- **Severity**: P2
- **Status**: open
- **File**: `anvil/services/inference/demo_model_provider.py:359-371`
- **Category**: TC-07
- **First seen**: 2026-06-21
- **Last confirmed**: 2026-06-21
- **Pattern**:
  ```python
  try:
      loop = asyncio.get_running_loop()                    # line 360
  except RuntimeError:
      loop = None
    
  if loop is None:
      return asyncio.run(_load())                          # line 365 — no loop: safe
  else:
      with ThreadPoolExecutor(max_workers=1) as pool:     # line 369 — loop detected
          future = pool.submit(asyncio.run, _load())      # line 370
          return future.result()
  ```
- **Issue**: The workaround correctly handles the "asyncio.run when a loop is running" problem. However, it creates a new `ThreadPoolExecutor` (and new thread + event loop) on every invocation when called from a running event loop. This is wasteful for repeated calls.
- **Risk**: Low in practice — `_load_demo_docs()` is called once on first `get_model()`. But the pattern is fragile (relies on `try/except RuntimeError`) and should be documented.
- **Recommendation**: Move the `ThreadPoolExecutor` to a module-level singleton to avoid repeated thread pool creation. Add a comment explaining the pattern.

#### TMR-015: MPSSamplerThread creates own event loop — correct pattern
- **Severity**: INFO
- **Status**: open
- **File**: `anvil/services/tracking/mps_sampler_thread.py:59-81`
- **Category**: TC-07
- **First seen**: 2026-06-21
- **Last confirmed**: 2026-06-21
- **Pattern**:
  ```python
  self._loop = asyncio.new_event_loop()                    # line 59
  ...
  self._loop.run_until_complete(...)                       # lines 65-74
  ...
  finally:
      if self._loop:
          self._loop.close()                               # line 81
  ```
- **Assessment**: This is the **correct pattern** for a daemon thread that needs its own event loop. `asyncio.new_event_loop()` creates a loop for this thread, `run_until_complete()` runs coroutines synchronously, and `finally` closes the loop. No cross-loop confusion.
- **Recommendation**: None — this is a reference implementation for other thread-based async usage.

#### TMR-016: asyncio.get_event_loop() in TrackingService — relies on default loop
- **Severity**: INFO
- **Status**: open
- **File**: `anvil/services/tracking/tracking.py` (multiple locations: lines 134, 170, 230, 266, 288, 312, 360, 434, 454, 499, 506, 523, 530, 571, 603, 633, 652, 686, 794, 841, 886, 923, 999, 1061)
- **Category**: TC-07
- **First seen**: 2026-06-21
- **Last confirmed**: 2026-06-21
- **Pattern**:
  ```python
  # 24+ occurrences of:
  loop = asyncio.get_event_loop()
  return await loop.run_in_executor(None, sync_fn, ...)
  ```
- **Issue**: `asyncio.get_event_loop()` returns the running event loop in Python 3.10+, or the default event loop. In the FastAPI context, this is the uvicorn event loop, which is correct. However, if these methods are ever called from a thread without an event loop (e.g., from a `run_in_executor` worker), `get_event_loop()` would raise a `RuntimeError` or return a different loop.
- **Risk**: Low — `TrackingService` methods are always called from the FastAPI event loop thread (via route handlers). The `MPSSamplerThread` does use these methods but it captures its own loop via `new_event_loop()` and calls `run_until_complete()`, not `get_event_loop()`.
- **Recommendation**: Replace with `asyncio.get_running_loop()` for clarity and to get immediate `RuntimeError` if called from wrong context.

#### TMR-020: asyncio.get_event_loop() from sync callback in worker thread
- **Severity**: P2
- **Status**: open
- **File**: `anvil/cli.py:276`
- **Category**: TC-07
- **First seen**: 2026-06-21
- **Last confirmed**: 2026-06-21
- **Pattern**:
  ```python
  # Lines 275-283 in anvil/cli.py (inside a sync progress_cb called from training worker thread):
  def progress_cb(step: int, loss: float) -> None:
      try:
          loop = asyncio.get_event_loop()                       # line 276
          t = loop.create_task(                                 # line 277
              tracking_svc.log_metric(mlflow_run_id, "loss", loss, step=step)
          )
          _progress_tasks.add(t)                                # line 280
          t.add_done_callback(_progress_tasks.discard)          # line 281
      except Exception:
          pass
  ```
- **Issue**: `asyncio.get_event_loop()` is called from a thread pool worker (training thread), not the main event loop thread. In Python 3.10+, `get_event_loop()` called from a thread with no running event loop returns the main thread's loop if one exists, or creates a new one — behavior that is **deprecated**. The `loop.create_task()` schedules work on whatever loop was returned, which may be wrong.
- **Risk**: Medium. The `try/except Exception` silently swallows any errors, so a failure would go unnoticed. The metric logging would silently fail. This is the CLI path only (not the main web server), so impact is limited to CLI training.
- **Recommendation**: Use `run_coroutine_threadsafe()` instead of `get_event_loop() + create_task()`, or pass the event loop explicitly as a parameter to `progress_cb`.

#### TMR-021: new_event_loop() without set_event_loop() — intentional isolation
- **Severity**: INFO
- **Status**: open
- **File**: `anvil/services/tracking/mps_sampler_thread.py:59`
- **Category**: TC-07
- **First seen**: 2026-06-21
- **Last confirmed**: 2026-06-21
- **Pattern**:
  ```python
  # Line 59 — in MPSSamplerThread.run():
  self._loop = asyncio.new_event_loop()
  # No call to asyncio.set_event_loop()
  ```
- **Issue**: `asyncio.new_event_loop()` creates a new event loop for the daemon thread, but `asyncio.set_event_loop()` is never called to register it as the thread's loop. This is intentional isolation — the thread manages its own loop reference and never calls `get_event_loop()` within the thread. Since all async work uses `self._loop.run_until_complete()` directly, this is functionally correct.
- **Risk**: Low — the loop is used via direct reference only. No code in the daemon thread calls `asyncio.get_event_loop()` expecting to retrieve it.
- **Recommendation**: Add a comment explaining the intentional isolation to prevent future refactoring errors.

---

### TC-08 — Lock Discipline & Deadlock Risks

| ID | Severity | Status | File | Title | First Seen | Last Confirmed | Resolved |
|----|----------|--------|------|-------|------------|----------------|----------|
| TMR-012 | P2 | open | anvil/services/inference/demo_model_provider.py:36,311 | _DEMO_TRAIN_LOCK — threading.Lock with double-checked locking | 2026-06-21 | 2026-06-21 | — |
| TMR-019 | P1 | open | anvil/api/v1/health_ops.py:60 | _bootstrap_lock TOCTOU race in rebootstrap_demo | 2026-06-21 | 2026-06-21 | — |

#### TMR-012: _DEMO_TRAIN_LOCK — threading.Lock with double-checked locking
- **Severity**: P2
- **Status**: open
- **File**: `anvil/services/inference/demo_model_provider.py:36,311`
- **Category**: TC-08
- **First seen**: 2026-06-21
- **Last confirmed**: 2026-06-21
- **Pattern**:
  ```python
  _DEMO_TRAIN_LOCK = threading.Lock()                      # line 36
  
  def get_model(self):                                     # line 295
      if self._model is not None:                          # line 307 — first check (no lock)
          return self._model, self._chars
      
      with _DEMO_TRAIN_LOCK:                               # line 311 — acquire lock
          if self._model is not None:                      # line 312 — second check (with lock)
              return self._model, self._chars
          # ... train or load model ...
  ```
- **Mechanism**: `threading.Lock` protects the model training/loading path. Double-checked locking pattern for lazy initialization.
- **Contention**: Lock is held during model training (400 steps, ~30-60s), which is **very long**. Any concurrent request to `get_model()` during training would block for tens of seconds.
- **Risk**: The long-held lock could cause request timeouts on FastAPI endpoints. Since the training happens synchronously inside the locked section, the entire event loop thread is blocked during training.
- **Recommendation**: Move the actual training outside the lock. The double-checked locking pattern should only initialize from an already-trained model (disk load), not do the training itself under the lock. Alternatively, use an `asyncio.Lock` with `await asyncio.to_thread()` for the training part.

#### TMR-019: _bootstrap_lock TOCTOU race in rebootstrap_demo
- **Severity**: P1
- **Status**: open
- **File**: `anvil/api/v1/health_ops.py:60-67`
- **Category**: TC-08
- **First seen**: 2026-06-21
- **Last confirmed**: 2026-06-21
- **Pattern**:
  ```python
  # Lines 35, 60-67 in anvil/api/v1/health_ops.py:
  _bootstrap_lock: asyncio.Lock = asyncio.Lock()
  
  @router.post("/demo/bootstrap")
  async def rebootstrap_demo(...):
      if not _bootstrap_lock.locked():        # line 60 — TOCTOU: check before acquire
          async with _bootstrap_lock:          # line 61 — acquire
              result = await workbench.demo.bootstrap_all()
              return result.model_dump()
      raise HTTPException(status_code=409, ...)
  ```
- **Issue**: Classic TOCTOU (time-of-check-time-of-use) race condition. The `if not _bootstrap_lock.locked()` check at line 60 is separate from the `async with _bootstrap_lock:` acquisition at line 61. Two concurrent requests can both see the lock as unlocked (line 60 passes for both), and both proceed into the `async with` block — the second request will block on the `async with`, NOT receive a 409. The 409 is only returned if the second request arrives **after** the first has already acquired the lock.
- **Risk**: Medium. The bootstrap operation is idempotent, so two concurrent bootstraps would not corrupt data (the `async with` serializes the actual bootstrap). The 409 response is only returned in a narrow window. The main risk is that two concurrent bootstraps could cause a brief double-load of demo data.
- **Recommendation**: Remove the `if not _bootstrap_lock.locked()` check and use `async with _bootstrap_lock:` directly. The lock provides serialization; the 409 can be implemented by replacing the lock with an `asyncio.Lock` + `asyncio.Event` pattern, or by using a `try: lock.acquire() except asyncio.CancelledError`. The simplest fix:
  ```python
  _bootstrap_in_progress = False
  
  @router.post("/demo/bootstrap")
  async def rebootstrap_demo(...):
      global _bootstrap_in_progress
      if _bootstrap_in_progress:
          raise HTTPException(status_code=409, ...)
      _bootstrap_in_progress = True
      try:
          async with _bootstrap_lock:
              result = await workbench.demo.bootstrap_all()
              return result.model_dump()
      finally:
          _bootstrap_in_progress = False
  ```

---

## Cross-Cutting Observations

1. **Overall architecture is sound**: The sync-core/async-bridge pattern (ADR-002) is correctly implemented. `run_in_executor` + `run_coroutine_threadsafe` is the standard Python pattern for bridging sync and async contexts. The `MPSSamplerThread` correctly uses `new_event_loop()` for its dedicated thread.

2. **`asyncio.get_event_loop()` vs `asyncio.get_running_loop()`**: The codebase uses `asyncio.get_event_loop()` extensively (55 occurrences) but `asyncio.get_running_loop()` only 3 times. In Python 3.10+, `get_event_loop()` raises `DeprecationWarning` and `get_running_loop()` is preferred. This is a pervasive style issue, not a correctness bug — all call sites are in async functions running on the main event loop.

3. **No `multiprocessing` usage**: The codebase doesn't share state across processes via `multiprocessing`. All parallelism is within-process via threads and async. This simplifies the memory model considerably.

4. **No explicit signal handlers**: No `signal.signal()` or `atexit.register()` calls. Process cleanup relies on FastAPI's lifespan context manager and OS process termination.

5. **Training state dictionary access**: `TrainingService._queues`, `_stop_events`, `_run_metadata`, `_diverged_runs` are dict/set instances mutated only from the event loop thread. The `progress_callback` closure (executed in thread pool) accesses `self._stop_events` to check stop — but this is a `threading.Event` which is thread-safe.

6. **Injection queue backpressure**: The content injection SSE queue (`anvil/api/v1/content.py:57`) uses `put_nowait()` which raises if the queue is full. Since there's no `maxsize`, it never fills — so there's no backpressure. If a `maxsize` were added, `put_nowait()` would raise `asyncio.QueueFull`.

7. **`asyncio.run()` vs `run_coroutine_threadsafe`**: The codebase has 14 `asyncio.run()` calls and 5 `asyncio.run_coroutine_threadsafe` calls. The `asyncio.run()` calls are from CLI entry points and sync helper methods called from thread pool workers — contexts where there's no running event loop. The `run_coroutine_threadsafe` calls are the "hot path" (training progress) where a sync thread needs to push into an async queue. The pattern usage is correct in both cases.

---

## Remediation List (Priority Order)

### P0 — Immediate
| # | Finding ID | Category | File | Fix |
|---|------------|----------|------|-----|
| 1 | TMR-001 | TC-05 | `anvil/services/training/training.py:393` | Set `asyncio.Queue(maxsize=1024)` and handle `QueueFull` on producer side (drop stale metrics) |
| 2 | TMR-002 | TC-05 | `anvil/api/v1/content.py:57` | Set `asyncio.Queue(maxsize=128)` and handle `QueueFull` (catch on `put_nowait`) |

### P1 — Short-term
| # | Finding ID | Category | File | Fix |
|---|------------|----------|------|-----|
| 1 | TMR-003 | TC-03 | `anvil/services/training/training.py:267,290,381` | Document that `_load_docs` must run in thread pool; consider making async |
| 2 | TMR-004 | TC-03 | `anvil/services/inference/demo_model_provider.py:103,365` | Document the running-loop workaround; consider making `_load_demo_docs` async |
| 3 | TMR-005 | TC-06 | `anvil/api/v1/training.py:362,582` | Add `mps_thread.stop()` in `finally:` block for normal completion path |
| 4 | TMR-006 | TC-04 | `anvil/services/training/training.py:48,516-518` | Document step-boundary cancellation limitation; consider SIGINT handler |
| 5 | TMR-007 | TC-06 | `anvil/api/app.py:152-154` | Cancel in-flight `_tasks` on lifespan shutdown; drain/signal queues |
| 6 | TMR-019 | TC-08 | `anvil/api/v1/health_ops.py:60` | Fix TOCTOU race — remove `.locked()` check, use `async with` directly |

### P2 — Medium-term
| # | Finding ID | Category | File | Fix |
|---|------------|----------|------|-----|
| 1 | TMR-008 | TC-02 | `anvil/services/training/training.py:393,558` | Document thread-safety invariants on `_queues` dict |
| 2 | TMR-009 | TC-02 | `anvil/services/inference/demo_model_provider.py:292-293` | Use `_DEMO_TRAIN_LOCK` for warmup thread writes to `_demo_provider._model` |
| 3 | TMR-010 | TC-07 | `anvil/services/inference/demo_model_provider.py:360-371` | Cache `ThreadPoolExecutor` at module level; document the workaround |
| 4 | TMR-011 | TC-01 | `anvil/api/app.py:143-147` | Add logging when warmup thread exits; consider join with timeout on shutdown |
| 5 | TMR-012 | TC-08 | `anvil/services/inference/demo_model_provider.py:36,311` | Move training outside lock; use `asyncio.Lock` for request-level concurrency |
| 6 | TMR-013 | TC-02 | `anvil/supervisor/supervisor.py:23,131` | Rename `_PID_DIR` to `PID_DIR` (constant); document single-thread dict access |
| 7 | TMR-020 | TC-07 | `anvil/cli.py:276` | Replace `get_event_loop()`+`create_task()` with `run_coroutine_threadsafe()` |

### INFO — Awareness
| # | Finding ID | Category | File | Note |
|---|------------|----------|------|------|
| 1 | TMR-014 | TC-01 | `anvil/services/tracking/mps_sampler_thread.py:19,44` | Reference implementation for thread+loop pattern |
| 2 | TMR-015 | TC-07 | `anvil/services/tracking/mps_sampler_thread.py:59-81` | Correct new_event_loop + cleanup pattern |
| 3 | TMR-016 | TC-07 | `anvil/services/tracking/tracking.py` | 24+ uses of `get_event_loop()` — consider migrating to `get_running_loop()` |
| 4 | TMR-017 | TC-02 | `anvil/supervisor/services.py:47` | Single-thread access to `MLflowService.process` — no issue |
| 5 | TMR-018 | TC-01 | `anvil/api/v1/training.py:584` | Training task has cleanup callback; not cancelled on shutdown |
| 6 | TMR-021 | TC-07 | `anvil/services/tracking/mps_sampler_thread.py:59` | Add comment explaining intentional new_event_loop isolation |
