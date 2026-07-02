---
title: Demo Warmup Progress Callback Was a No-Op
type: discovery
status: draft
source: agent
session: 2026-07-01-demo-loss-curve-fix
code-refs:
  - anvil/services/inference/demo_model_provider.py
  - anvil/api/v1/training.py
created: '2026-07-01'
updated: '2026-07-01'
aliases: Demo Warmup Progress Callback Was a No-Op
tags:
  - type/discovery
  - domain/training
  - domain/tracking
---
# Demo Warmup Progress Callback Was a No-Op

The demo warmup pipeline (`warmup_demo_via_system_pipeline` in `anvil/services/inference/demo_model_provider.py`) used `lambda *args, **kwargs: None` as the `progress_callback` argument to `backend.run()`. This meant **zero per-step loss metrics were ever logged to MLflow** during demo training.

The experiment was created in MLflow, `final_loss` was logged after completion, the model was registered — but the loss curve was empty. When the UI attached to the completed demo run and called `GET /v1/experiments/{id}/metrics`, the MLflow query `client.get_metric_history(mlflow_run_id, "loss")` returned `[]`.

## Why this was hard to spot

- The demo worked: a model was trained, registered, and usable from the playground
- The experiment appeared in Past Experiments with `final_loss` visible
- The `progress_callback` parameter's purpose was not obvious from the calling site
- The user training pipeline creates the callback via `_build_progress_callback()` in `TrainingService`, which bundles SSE queue events + MLflow logging + milestone events. The demo bypasses this by calling `backend.run()` directly.

## Status: FIXED

The callback now uses the same `run_coroutine_threadsafe` pattern as user training to log per-step loss to MLflow.
