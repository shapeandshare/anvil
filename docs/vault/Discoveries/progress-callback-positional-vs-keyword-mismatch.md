---
title: Progress Callback Positional vs Keyword Argument Mismatch
type: discovery
status: draft
source: agent
session: 2026-06-28-progress-callback-fix
code-refs:
  - anvil/core/engine.py
  - anvil/services/training/training.py
  - anvil/services/training/torch_engine.py
created: '2026-06-28'
updated: '2026-06-28'
tags:
  - type/discovery
  - domain/core
  - domain/training
  - status/draft
aliases:
  - Progress Callback Mismatch
---

# Progress Callback Positional vs Keyword Argument Mismatch

`anvil/core/engine.py`'s `train()` function calls the `progress_callback` with 4 positional arguments: `progress_callback(step, loss.data, n, None)`. Meanwhile, `TrainingService._build_progress_callback()` in `anvil/services/training/training.py` defines the callback with `tokens` and `grad_norm` as **keyword-only** arguments (after `*`).

The torch engine (`anvil/services/training/torch_engine.py`) correctly uses keyword arguments: `progress_callback(step, loss_val, tokens=n, grad_norm=grad_norm)`.

## Impact

- Selecting **Local (CPU)** or **Local (GPU)** when no GPU is available caused a `TypeError` because the stdlib engine path was used.
- Selecting **Auto** worked because on GPU-capable machines it selects the torch engine, which already used keyword args.
- On CPU-only machines, **Auto** also failed (silently, through the same stdlib path).
- The bug was silent to the user during training — it manifested as a `ComputeResult(status=FAILED)` caught by `LocalStdlibBackend.run()`'s generic exception handler, surfacing as a generic "Training failed" error in the SSE stream.

## Fix

Changed `anvil/core/engine.py` line 647 to pass `tokens` and `grad_norm` as keyword arguments, matching the torch engine convention:

```python
# Before:
progress_callback(step, loss.data, n, None)

# After:
progress_callback(step, loss.data, tokens=n, grad_norm=None)
```

## References

- [[Discoveries/Discoveries|Discoveries]]
- `anvil/core/engine.py` — stdlib `train()` function, line 647
- `anvil/services/training/training.py` — `TrainingService._build_progress_callback()`
- `anvil/services/training/torch_engine.py` — `train_torch()` (shows correct keyword-arg pattern)