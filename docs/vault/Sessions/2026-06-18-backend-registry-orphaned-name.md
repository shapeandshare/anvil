---
title: Backend Registry Orphaned-Name Bug
type: session-log
tags:
  - type/session-log
  - domain/architecture
  - domain/training
created: '2026-06-18'
updated: '2026-06-18'
aliases:
  - 2026-06-18-backend-registry-orphaned-name
source: agent
---
## Session: Backend registry orphaned-name bug — training silently killed before SSE stream

**Date**: 2026-06-18

### Discovery

Training from the web UI (and CLI) silently failed immediately on start. The run was created, the training task spawned, but it crashed inside `start_training()` before any SSE events were pushed. The queue was cleaned up in the `finally` block, so by the time the UI's EventSource connected, the queue was gone — the SSE endpoint responded with `"Training run has already completed or was never started"`.

### Root Cause

`resolve_backend()` returns `{"backend": "local", "engine": "torch"}` for both `local-cpu` and `local-gpu` compute backends. But the compute backend registry (added in ADR-015) registers backends under composite names: `"local-stdlib"` and `"local-torch"`. Nothing is registered as bare `"local"`.

At `TrainingService.start_training()` line 191, `get_backend("local")` raised `ComputeBackendUnavailable("Compute backend 'local' is not registered")`. This exception was caught by the background task's generic `except Exception` handler in the API route, which marked the experiment as failed and called `tracking_svc.fail_run()`.

### Impact

- Training runs appeared to "start" (POST returned run_id) but never streamed data to the UI
- The UI could never reconnect because the queue was already removed
- The error was invisible to the user — it was only discoverable by checking the experiment's `error_message` in the DB
- Both CLI (`anvil train --gpu`) and web UI paths were affected

### Fix

Added a backend-name mapping in `TrainingService.start_training()`:

```python
if backend_name == "local":
    backend_name = f"local-{engine_name}"
```

This maps the generic `"local"` returned by `resolve_backend()` to the engine-qualified registry name (`"local-stdlib"` or `"local-torch"`) before the `get_backend()` lookup.

### Pattern Gap

The naming mismatch exists because `resolve_backend()` and the compute registry were designed at different abstraction levels:

- `resolve_backend()` returns human-facing category names (`"local"`, `"modal"`)  
- The registry uses implementation-qualified names (`"local-stdlib"`, `"local-torch"`, `"modal"`)

The `TrainingService` is the bridge layer that should translate between them — but that translation was simply missing. `"modal"` happened to work because it matches 1:1.

### Files Changed

- `anvil/services/training.py` — Added `"local"` → `f"local-{engine_name}"` mapping at registry lookup
- `tests/unit/services/test_training_phases.py` — Updated `test_local_cpu_selects_local_stdlib_backend` assertion to expect `"local-stdlib"`

### Vault Enrichment

- Updated [[Reference/DualBackend]] — Added architecture note about the registry naming layer
- Updated [[Reference/DecisionLog]]