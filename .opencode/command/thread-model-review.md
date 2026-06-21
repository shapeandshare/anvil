---
description: Analyze the codebase's threading/concurrency model, document all thread contexts, and produce a prioritized remediation list for threading issues, anti-patterns, and risks.
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty). The argument is an optional target path or scope restriction. If omitted, default to `anvil/`.

## Goal

Review the codebase's threading and concurrency model — identify all thread contexts, shared-state access patterns, sync-to-async bridges, lock usage, thread lifecycle management, and event-loop hygiene. Produce:

1. **Detailed report** — structured Markdown at `docs/thread-model-review-<YYYY-MM-DD>.md`
2. **Running tracker** — CSV at `docs/thread-model-tracker.csv` that accumulates findings across all runs, tracking each finding's lifecycle (open → fixed → closed)

The running tracker enables tracking regressions and remediation progress over time.

## Operating Constraints

1. **Read-only**: Do not modify any source files. Findings only.
2. **Evidence-based**: Every finding must cite specific file paths and line numbers. No vague claims.
3. **Severity rating**: Every finding gets a severity — `P0` (must fix), `P1` (should fix), `P2` (nice to fix), or `INFO`.
4. **FP-aware**: If you're uncertain, flag as `INFO` and explain why it's ambiguous.
5. **Timebox**: For large codebases, sample a representative cross-section. Prioritize files with explicit threading constructs (`threading.*`, `run_in_executor`, `asyncio.Queue`, `run_coroutine_threadsafe`, `Lock`, `Event`, `subprocess`, daemon threads).
6. **Tracker file management**: The running CSV tracker at `docs/thread-model-tracker.csv` is the source of truth for finding lifecycle. Each run reads the tracker, reconciles findings against the current codebase, and writes back an updated tracker. Never delete tracker rows — mark findings as `Closed` with the closure date.
7. **Finding deduplication**: New findings are keyed by `(file_path, pattern_type)` to prevent duplicates. Before assigning a new `TMR-XXX` ID, check that an existing finding with the same file + same pattern type doesn't already exist (including closed ones).
8. **Pre-seeded context**: Review existing architecture docs and known risks before scanning. Note relevant findings from the Reference section below to avoid rediscovering documented issues.

## Finding Lifecycle Model

Every finding in the tracker has these fields:

```
TMR-XXX | TC-XX | severity | status | file:line | title | first_seen | last_confirmed | resolved_date | notes
```

**Statuses** (task-tracked):
| Status | Meaning |
|--------|---------|
| `open` | Identified, not yet addressed |
| `in_progress` | Work underway (set when someone starts fixing it) |
| `fixed` | Confirmed remediated in codebase |
| `wontfix` | Accepted risk — will not fix (with reason) |
| `false_positive` | Initial finding was incorrect |

**Allowed status transitions:**
- `open` ↔ `in_progress` ↔ `fixed`
- `fixed` → `open` (regression — issue reappeared)
- `open` → `wontfix` | `false_positive`
- `wontfix` → `open` (re-opened after risk re-evaluation)

**Merge rules** (when tracker already exists):
1. For each finding in the existing tracker:
   - Re-check the cited `file:line` against current codebase
   - If the pattern still exists → update `last_confirmed` to today; keep status
   - If the pattern is gone → mark `fixed`, set `resolved_date`
   - If the cited file no longer exists → mark `fixed` (removed), set `resolved_date`
2. For each new finding discovered in this scan:
   - Check if it already exists by `(file_path, pattern_type)` — if so, update existing entry's `last_confirmed`
   - If truly new → assign `TMR-XXX`, add with `status: open`
   - Never create a duplicate row for the same finding

## Analysis Categories

### TC-01 — Thread Context Inventory

Identify **every distinct thread context** in the codebase. For each, record:
- **Name/Purpose** (e.g. "asyncio event loop thread", "training thread pool worker", "MPS metrics sampler daemon")
- **File/Line** where spawned or entered
- **Thread type**: asyncio event loop thread / thread pool worker / dedicated daemon thread / subprocess
- **Lifecycle**: when it starts, what keeps it alive, when it stops
- **Event loop**: does this thread own an event loop? (`asyncio.get_event_loop()`, `asyncio.new_event_loop()`, `asyncio.run()`)

Search scope: `anvil/` — look for:
- `asyncio.get_event_loop()`, `loop.run_in_executor()`, `asyncio.create_task()`
- `threading.Thread`, `threading.Event`, `threading.Lock`
- `asyncio.run_coroutine_threadsafe()`
- `asyncio.Queue` declared as instance/class/module-level variable
- `subprocess.Popen` with background lifecycle
- `asyncio.new_event_loop()`, `asyncio.run()`
- `concurrent.futures.ThreadPoolExecutor`

### TC-02 — Shared State & Thread Safety

Identify **every piece of mutable state accessed from more than one thread context**. For each:
- **State variable**: the specific data structure (dict, list, Queue, file handle, etc.)
- **Threads involved**: which thread contexts read/write it
- **Protection mechanism**: Lock, Event, atomic operation, or **none**
- **Risk**: data race, torn read, lost update, stale cache

Search scope: `anvil/` — specifically:
- `self._queues`, `self._stop_events`, `self._diverged_runs` in `TrainingService`
- `_demo_provider._model`, `_demo_provider._chars` (module-level singleton)
- `ProcessSupervisor._processes` dict
- Any module-level mutable state (`_demo_provider`, `_PID_DIR`, etc.)
- `run_coroutine_threadsafe` call sites — verify the target `asyncio.Queue` is only accessed from the owning loop thread on the consumer side

### TC-03 — Sync↔Async Bridge Patterns

Identify every location where a synchronous thread communicates with an async context (or vice versa). For each:
- **Bridge type**: `run_coroutine_threadsafe` / `run_in_executor` / `asyncio.run()` called from sync / `asyncio.to_thread()` / shared `threading.Event`
- **Direction**: sync→async or async→sync
- **Pattern correctness**: verify the standard Python pattern is followed
- **Error handling**: what happens when the bridge call fails (exception in worker thread, dropped event, etc.)

Search scope:
```python
# Sync→Async bridges — MUST use run_coroutine_threadsafe
asyncio.run_coroutine_threadsafe(queue.put(...), loop)

# Async→Sync bridges — MUST use run_in_executor or to_thread
await loop.run_in_executor(None, sync_fn, ...)
await asyncio.to_thread(sync_fn, ...)

# Sync calling into async from scratch — risk of event loop conflicts
asyncio.run(...)  # called from sync context
```

Check:
- Is `asyncio.run()` called when an event loop is already running? (RuntimeError risk)
- Is the correct `loop` reference captured at the right time?
- Are `run_coroutine_threadsafe` futures ever awaited or their exceptions checked?

### TC-04 — Cancellation & Stop Signal Propagation

Identify how running threads/operations are stopped. For each:
- **Mechanism**: `threading.Event` / `concurrent.futures.Future.cancel()` / `asyncio.Task.cancel()` / subprocess `SIGTERM` / none
- **Latency**: how quickly does a stop signal take effect?
- **Gap**: is there a period where a stop is requested but the thread cannot observe it?
- **Cleanup**: does the thread release resources (file handles, DB connections, event loops) on stop?

Search scope:
- `self._stop_events[run_id].set()` + `stop_event.is_set()` in `TrainingService`
- `MPSSamplerThread.stop()` + `self._stop_event.set()` / `wait()`
- `subprocess.Popen.terminate()`, `os.killpg()` in `ProcessSupervisor`
- `DemoBootstrapService` asyncio.Lock usage
- `cancel()` on any `asyncio.Task`

### TC-05 — asyncio.Queue Backpressure & Capacity

Identify every `asyncio.Queue` and assess backpressure risk:
- **Queue location**: where declared and where consumed
- **Maxsize**: bounded (`asyncio.Queue(maxsize=N)`) or unbounded (default)
- **Producer rate**: can the producer (sync thread via `run_coroutine_threadsafe`) outpace the consumer (SSE endpoint)?
- **Consumer rate**: what happens if the consumer is slow or disconnects?
- **Memory risk**: unbounded queue + fast producer + slow consumer = OOM

Search scope:
```python
asyncio.Queue()  # unbounded — memory risk
asyncio.Queue(maxsize=...)  # bounded — backpressure behavior
queue.put(...)  # will block forever on full bounded queue without timeout
queue.put_nowait(...)  # raises asyncio.QueueFull
```

Specific locations:
- `TrainingService._queues[run_id] = asyncio.Queue()` at `reserve_run()` — unbounded
- SSE consumer in `anvil/api/v1/training.py` — `queue.get()` with 30s timeout

### TC-06 — Thread Lifecycle & Resource Cleanup

For every thread/process that outlives a single request:
- Is there a graceful shutdown path?
- Are daemon threads used appropriately? (daemon threads are abruptly terminated on interpreter exit)
- Are event loops closed when threads exit?
- Are subprocesses cleaned up on shutdown?
- Are there any zombie thread/process risks?

Search scope:
- Daemon threads: `MPSSamplerThread` (daemon=True), demo warmup thread
- Event loop cleanup: `self._loop.close()` in `MPSSamplerThread.finally`
- `ProcessSupervisor.stop_all()` — where is it called from? Is it reachable on all exit paths?
- FastAPI lifespan handler — what cleanup does it perform?

### TC-07 — Event Loop Confusion & Cross-Loop Access

Identify places where an event loop from one thread is used in another, or where `asyncio.run()` is called inside a running event loop:
- `asyncio.run()` inside an async function or event loop thread
- `asyncio.get_event_loop()` when the expected loop may not be set
- `asyncio.new_event_loop()` in non-main threads
- Coroutines or awaitable objects passed between threads without `run_coroutine_threadsafe`

Search scope:
```python
asyncio.run(...)  # inside async def or event loop thread — RuntimeError
asyncio.get_event_loop()  # in a non-main thread without new_event_loop
asyncio.new_event_loop()  # check if set as the loop for the thread
```

Specific files to check:
- `anvil/services/inference/demo_model_provider.py` — `asyncio.run(_get_docs())` + `asyncio.run(_run())` called from sync context (warmup thread and `_load_demo_docs`)
- `anvil/services/training/training.py` — `asyncio.run()` calls inside `_load_docs()` and `_load_docs_from_version()`
- `anvil/_resources/migrations/env.py` — Alembic migration runner
- `anvil/db/migration.py` — `run_in_executor` wrapping sync Alembic

### TC-08 — Lock Discipline & Deadlock Risks

Identify all lock acquisitions and assess deadlock/reentrancy risk:
- Lock ordering: if multiple locks exist, is there a consistent acquisition order?
- Reentrancy: `threading.Lock` vs `threading.RLock` — is reentry needed?
- Contention: is the lock held for a long duration? Could it block the event loop?
- `asyncio.Lock` vs `threading.Lock` — are they used in the right context?

Search scope:
```python
threading.Lock()
threading.RLock()
asyncio.Lock()
with lock:  # could this block the event loop?
```

Specific locations:
- `_DEMO_TRAIN_LOCK` in `demo_model_provider.py` — threading.Lock, double-checked locking pattern
- Any `asyncio.Lock` in content ingestion or bootstrap endpoints

## Execution Steps

### Phase 0: Load or Create Running Tracker

1. Check if `docs/thread-model-tracker.csv` exists.
2. If it **does not exist**, create it with this header row:
   ```
   finding_id,category,severity,status,file_line,title,first_seen,last_confirmed,resolved_date,notes
   ```
3. If it **does exist**, read all rows into memory. This is the baseline of known findings. Rows with `status=Closed` represent previously fixed issues — the agent should verify they are still fixed (re-check the file/line for each closed finding). Rows with `status=Open` represent outstanding issues — re-validate that the finding still exists (the code may have been fixed since the last run).
4. Generate new finding IDs by incrementing from the highest existing ID (e.g. `TMR-042` if the last row is `TMR-041`). The ID format is `TMR-` followed by a zero-padded 3-digit number.

### Phase 0.5: Project Inventory

1. Build a quick file inventory of relevant targets:
   - Threading primitives: `**/*.py` matching `threading\.`, `asyncio\.run\(`, `run_in_executor`, `run_coroutine_threadsafe`, `asyncio\.Queue`, `asyncio\.Lock`, `ThreadPool`, `subprocess\.Popen`
   - Event loop usage: `asyncio\.get_event_loop`, `asyncio\.new_event_loop`, `asyncio\.get_running_loop`
   - Async bridge patterns: `run_coroutine_threadsafe`, `run_in_executor`, `to_thread`, `asyncio\.run\(`
2. Note the project's thread model context from `AGENTS.md` and `docs/vault/Decisions/ADR-002-sync-core-async-bridge.md`.

### Phase 1: Reconciled Per-Category Analysis

For each of the 8 categories (TC-01 through TC-08):
1. Use parallel background explore agents for broad pattern searches (e.g. one agent for `threading.Lock`/`threading.Event`, another for `run_coroutine_threadsafe`/`run_in_executor`, a third for `asyncio.run()` calls).
2. Collect results and read surrounding context (20 lines) for each finding to confirm or downgrade severity.
3. Cross-reference against the existing tracker by `(file_path, pattern_type)` key:
   - **Existing Open finding still present** → keep it, update `last_confirmed`, note that it's confirmed (do not create a duplicate)
   - **Existing Open finding no longer present** → mark as `fixed` with today's `resolved_date` and note "Fixed — code no longer matches pattern"
   - **New finding discovered** → assign a new `TMR-XXX` ID, add to tracker as `open`
   - **Existing Closed finding still absent** → leave it closed (remediation held)
   - **Existing Closed finding re-appeared** (regression) → re-open: change status to `open`, clear `resolved_date`, add a note "Regression — re-appeared in <YYYY-MM-DD> review"
4. Grade each finding: P0, P1, P2, or INFO.
5. Record: category, file path, line number(s), pattern observed, risk description, severity, recommended fix, and the reconciled tracker status.

### Phase 1.5: Deep-Dive For P0 Findings

For findings rated `P0`:
1. Read the surrounding 20 lines of context to confirm the finding is real (not a false positive)
2. Check if there are compensating controls (e.g., the pattern is wrapped by a higher-level guard)
3. Confirm or downgrade the severity.
4. If confirmed P0, expand the remediation recommendation with a specific implementation approach.

### Phase 2: Detailed Report Generation

Write the report to `docs/thread-model-review-<YYYY-MM-DD>.md` with this structure:

```markdown
# Thread Model Review — <YYYY-MM-DD>

**Living task-tracking report.** Last updated: <YYYY-MM-DD>
**Target**: <path reviewed>
**Scope**: <summary of files/patterns checked>
**Reviewer**: Sisyphus (agent)

---

## Scan History

_A chronological log of every review run. Newest first._

| Scan Date | New Findings | Resolved | Regressed | Total Open | Coverage |
|-----------|-------------|----------|-----------|------------|----------|
| <YYYY-MM-DD> | +N | -N | +N | N | <paths/files> |
| <YYYY-MM-DD> | +N | -N | +N | N | <paths/files> |

_This section grows with each scan — never prune rows._

---

## Progress Summary

| Metric | Value |
|--------|-------|
| Total findings (all time) | **N** |
| Currently open | **X** |
| In progress | **Y** |
| Fixed / resolved | **Z** |
| Wontfix / False positive | **W** |
| Resolved rate | **P%** |

### Open Findings by Severity

| Severity | Count |
|----------|-------|
| P0 | N |
| P1 | N |
| P2 | N |
| INFO | N |

### Trend Since Last Review

- New findings added: +N
- Findings resolved: −N
- Findings regressed: +N

> ⚠️ **Top 3 Risks**:
> 1. ...

---

## Running Tracker Summary

| Finding ID | Severity | Category | Status | Date Found | Date Closed | File |
|------------|----------|----------|--------|------------|-------------|------|
| TMR-001 | P1 | TC-03 | open | 2026-06-20 | — | `path/file.py:L` |
| TMR-002 | P0 | TC-05 | fixed | 2026-06-20 | 2026-06-25 | `path/file.py:L` |
| ... | ... | ... | ... | ... | ... | ... |

A full CSV export is maintained at `docs/thread-model-tracker.csv`.

---

## Detailed Findings

### TC-01 — Thread Context Inventory

| ID | Severity | Status | File | Title | First Seen | Last Confirmed | Resolved |
|----|----------|--------|------|-------|------------|----------------|----------|
| TMR-00N | P1 | open | path/file.py:L | Summary | 2026-06-20 | 2026-06-20 | — |

#### TMR-00N: [Title]
- **Severity**: P1
- **Status**: open
- **File**: `path/file.py:L12-L18`
- **Category**: TC-01
- **First seen**: 2026-06-20
- **Last confirmed**: 2026-06-20
- **Pattern**:
  ```python
  # vulnerable code snippet
  ```
- **Risk**: What could go wrong
- **Recommendation**:
  ```python
  # recommended fix
  ```
- **Notes**: Any context or caveats

[Repeat for each finding in TC-01]

### TC-02 — Shared State & Thread Safety
...
```

Then append the `## Remediation List (Priority Order)` section (Phase 3 template below) and the `## Cross-Cutting Observations` section.

### Phase 3: Remediation List (Priority Order)

Append a remediation section at the end of the report:

```markdown
## Remediation List (Priority Order)

### P0 — Immediate
| # | Finding ID | Category | File | Fix |
|---|------------|----------|------|-----|
| 1 | TMR-00N | TC-XX | `path/file.py:L` | ... |

### P1 — Short-term
| # | Finding ID | Category | File | Fix |
|---|------------|----------|------|-----|
| 1 | TMR-00N | TC-XX | `path/file.py:L` | ... |

### P2 — Medium-term
| # | Finding ID | Category | File | Fix |
|---|------------|----------|------|-----|
| 1 | TMR-00N | TC-XX | `path/file.py:L` | ... |

### INFO — Awareness
| # | Finding ID | Category | File | Note |
|---|------------|----------|------|------|
| 1 | TMR-00N | TC-XX | `path/file.py:L` | ... |
```

### Phase 3.25: Cross-Cutting Observations

Append a section for observations that span multiple categories or don't fit neatly into one TC category:

```markdown
## Cross-Cutting Observations

- ...
```

### Phase 3.5: Write Running Tracker CSV

After the detailed report is generated, write (overwrite) the running tracker CSV at `docs/thread-model-tracker.csv` with ALL findings (all statuses) from the reconciled analysis. Use exact CSV format:

```
finding_id,category,severity,status,file_line,title,first_seen,last_confirmed,resolved_date,notes
TMR-001,TC-03,P1,open,"anvil/services/training/training.py:508-510","No cancellation on training executor — threading.Event checked only at step boundaries",2026-06-20,2026-06-20,,"Replace threading.Event with asyncio.Event + cancel scope"
TMR-002,TC-05,P0,fixed,"anvil/services/training/training.py:384","TrainingService._queues created unbounded — no maxsize",2026-06-20,2026-06-24,2026-06-25,"Set asyncio.Queue(maxsize=1024)"
```

**CSV formatting rules:**
- No spaces after commas in the header row
- Fields containing commas MUST be double-quoted
- Quoted fields escape internal double quotes as `""`
- Date format: `YYYY-MM-DD`
- Empty cells: leave blank (no space between commas) — e.g. `,,` for `resolved_date` on open findings
- Sorting: open/in_progress first (sorted by severity P0→P1→P2→INFO, then by finding_id), then fixed/wontfix/false_positive (sorted by resolved_date descending, then finding_id)

### Phase 4: Summary

After writing the report and CSV, print a brief summary:
- **Findings delta**: X new, Y resolved, Z regressed since last scan
- **Open burden**: N open (X P0, Y P1)
- **Resolved rate**: P% of all-time findings
- **Outputs**: `docs/thread-model-review-<YYYY-MM-DD>.md` (markdown) and `docs/thread-model-tracker.csv` (CSV)
- **Top 3 things to fix first** (P0 items, or most impactful P1 items if no P0 exists)

## Reference: Existing Thread Model Documentation

The project's threading architecture is documented in:
- `docs/vault/Decisions/ADR-002-sync-core-async-bridge.md` — the core decision: core engine runs in `run_in_executor`, SSE events bridge via `asyncio.Queue` + `run_coroutine_threadsafe`
- `docs/vault/Reference/ArchitectureOverview.md` — "Async throughout: Web, DB, storage layers are async. Core engine is sync (runs in thread pool)."
- `docs/vault/Reference/TrainingDataFlow.md` — data flow diagram with thread pool and `run_coroutine_threadsafe`
- `docs/vault/Reference/DualBackend.md` — references ADR-002

## Known Threading Risks (pre-existing, to re-validate)

1. **No mid-step cancellation**: Thread executor doesn't support Python-level cancellation. `threading.Event` is checked only at step boundaries via `stop_check`.
2. **Unbounded asyncio.Queue**: `TrainingService.reserve_run()` creates `asyncio.Queue()` with no `maxsize`. Fast producer + slow/disconnected SSE consumer = unbounded memory growth.
3. **`asyncio.run()` from sync context where a loop may be running**: `_load_docs()`, `_load_docs_from_version()`, and `demo_model_provider.py` all call `asyncio.run()` from potentially ambiguous contexts.
