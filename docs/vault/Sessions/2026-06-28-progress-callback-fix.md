---
title: Fix Progress Callback Argument Mismatch
type: session-log
tags:
  - type/session-log
  - domain/core
  - domain/training
created: '2026-06-28'
updated: '2026-06-28'
status: draft
source: agent
aliases: Progress Callback Fix
---

# Fix Progress Callback Argument Mismatch

**Session**: Fixed a bug where training failed when selecting "Local (CPU)" or "Local (GPU)" from the compute backend selector, while "Auto" worked. Root cause was a positional-vs-keyword argument mismatch in the progress callback.

## What was done

### Diagnosed the root cause

Traced the full compute backend resolution and training pipeline. The backend resolution logic (`resolve_backend`) was correct — both "auto" and "local-cpu"/"local-gpu" resolved to the right engines. The bug was deeper in the call chain:

1. `TrainingService._build_progress_callback()` defines callbacks with `tokens` and `grad_norm` as keyword-only args (`def cb(step, loss, *, tokens=0, grad_norm=None)`)
2. `train_torch()` (torch engine) calls the callback correctly with keyword args
3. `train()` (stdlib engine) called the callback with 4 positional args: `progress_callback(step, loss.data, n, None)`
4. This caused a `TypeError` that was caught by `LocalStdlibBackend.run()`'s generic exception handler
5. The error surfaced as a generic "Training failed" in the SSE stream

### Fixed the mismatch

Changed `anvil/core/engine.py` to use keyword arguments for `tokens` and `grad_norm`, matching the torch engine convention.

### Updated stale test

`test_stop_check_before_start` expected `FAILED` due to an `UnboundLocalError` on `loss`, but `loss` is initialized as `Value(0.0)` before the loop — so training returns a valid zero-loss result when stopped before any step.

## Files modified

- `anvil/core/engine.py` — 1 line: changed `progress_callback(step, loss.data, n, None)` to keyword args
- `tests/unit/services/compute/test_local_backend.py` — updated `test_stop_check_before_start` expectation to `COMPLETED`

## Discoveries

- [[Discoveries/progress-callback-positional-vs-keyword-mismatch|Progress Callback Positional vs Keyword Argument Mismatch]]