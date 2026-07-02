---
title: Demo Warmup Re-Trains Every Startup Despite Existing Checkpoint
type: discovery
status: draft
source: agent
session: 2026-07-02-demo-warmup-redundant-retrain
code-refs:
  - anvil/services/inference/demo_model_provider.py
created: '2026-07-02'
updated: '2026-07-02'
aliases: Demo Warmup Redundant Re-Train
tags:
  - type/discovery
  - domain/training
  - domain/inference
---

`warmup_demo_via_system_pipeline` in `anvil/services/inference/demo_model_provider.py` ran the full training pipeline (compute backend resolution → 400-step training → MLflow run creation → metric logging → safetensors export → model registration) on every application startup, even when a demo model checkpoint already existed at `data/models/demo/model.json`.

Meanwhile `DemoModelProvider.get_model()` already had a lazy-load path that loaded from disk if the checkpoint existed — so the warmup's CPU burn and MLflow clutter (a new "demo-warmup" run per restart) were entirely redundant after the first successful warmup.

## What was fixed

Added an early-exit guard at the top of `warmup_demo_via_system_pipeline`: if `DEMO_MODEL_PATH.exists()`, load it into `_demo_provider`'s cache and return immediately. On load failure (corrupted file), fall through to re-train as before.

## Why this was easy to miss

- The warmup runs in a background daemon thread, so the ~30-60s CPU burn didn't delay startup
- The output was always correct — a model was trained, registered, and usable
- The function's name says "warmup" not "re-train", making the redundant work non-obvious
- No existing test exercised the warmup's startup guard path

## Status: FIXED

See [[Sessions/2026-07-02-demo-warmup-redundant-retrain]].