---
title: Demo Loss Curve Fix & Attach UI Hardening
type: session-log
tags:
  - type/session-log
  - domain/training
  - domain/tracking
  - domain/ui
created: '2026-07-01'
updated: '2026-07-01'
status: draft
source: agent
aliases: Demo Loss Curve Fix & Attach UI Hardening
---
# Demo Loss Curve Fix & Attach UI Hardening

**Session**: Fixed two bugs causing the loss curve to never render when attaching to a completed demo training run.

- **Bug 1**: The demo warmup pipeline (`warmup_demo_via_system_pipeline`) used a `lambda *args, **kwargs: None` progress callback, so per-step loss was never logged to MLflow.
- **Bug 2**: The `attachExperiment` JS function called `chart.clear()` *before* the async metrics fetch, painting "Waiting for data..." unconditionally. If the fetch returned empty metrics (as it did for the demo run), this state was permanent — nothing ever called `_paint()` again with data.

## What was done

### Frontend: `anvil/api/templates/archetypes/training.html`

- Removed `initChart()` + `chart.clear()` from the pre-fetch section of `attachExperiment`
- Moved `initChart()` into the metrics `.then()` handler — chart is created only when data arrives
- Added an `else if (points.length === 0)` branch that logs `"> No per-step metrics found for experiment #N"` instead of silently leaving the chart stuck
- The attach confirmation banner now always renders (even when metrics are empty)

### Backend: `anvil/services/inference/demo_model_provider.py`

Replaced the no-op progress callback with a real one that logs per-step loss:

```python
_loop = asyncio.get_running_loop()

def _demo_progress(step: int, loss: float) -> None:
    if mlflow_run_id:
        asyncio.run_coroutine_threadsafe(
            tracking_svc.log_metric(mlflow_run_id, "loss", loss, step=step),
            _loop,
        )
```

Also closed several consistency gaps between the demo warmup pipeline and a normal user training run:

| Gap | Fix |
|-----|-----|
| Missing `beta1`, `beta2`, `compute_backend`, `gpu_*` hyperparams | Added to `start_run()` params dict |
| Missing `anvil.status` `"running"` tag at start | Added `set_tag()` after `anvil.experiment_id` |
| No samples.txt artifact logged to MLflow | Added `client.log_artifact()` for `samples.txt` |
| No model.json artifact logged to MLflow | Added `client.log_artifact()` for `model.json` |
| No input provenance (`input_digest`, `input_role`) | Added `tracking_svc.log_corpus_input()` + tags |
| `anvil.status` set to `"finished"` at end (user training doesn't set it) | Removed — now matches user training: only set `"running"` at start |

### Files modified (2 files)

| File | Change |
|------|--------|
| `anvil/api/templates/archetypes/training.html` | Move `initChart()` into metrics `.then()`, remove `chart.clear()`, add empty-metrics branch |
| `anvil/services/inference/demo_model_provider.py` | Real progress callback, richer hyperparams, artifact logging, input provenance |

## Key decisions

- **`run_coroutine_threadsafe` pattern** — matches the existing `mlflow_progress_callback` in `api/v1/training.py`. The demo warmup's training runs in a thread pool via `backend.run()`, so async MLflow calls must be scheduled on the event loop from the worker thread.
- **Don't set `anvil.status` at end** — user training sets `"running"` at start and never changes it (the run status comes from MLflow's `run.info.status` via `finish_run()`). The demo should match this exactly.
- **Samples + model.json artifacts** — matches the `on_complete()` pattern in `api/v1/training.py` exactly, including the `tempfile.TemporaryDirectory` + `client.log_artifact` structure.

## References

- [[2026-06-28-progress-callback-fix]] — prior fix to the progress callback signature mismatch
- [[2026-06-18-experiments-page-bugfix]] — prior work on the demo-warmup MLflow run
- [[2026-06-20-demo-model-user-space-refactor]] — demo model pipeline restructuring
