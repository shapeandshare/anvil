---
title: Demo Warmup Redundant Re-Train Fix
type: session-log
tags:
  - type/session-log
  - domain/training
  - domain/inference
created: '2026-07-02'
updated: '2026-07-02'
status: draft
source: agent
aliases: Demo Warmup Redundant Re-Train Fix
---

# Demo Warmup Redundant Re-Train Fix

**Session**: Identified and fixed the demo model warmup re-training on every startup despite an existing checkpoint.

## Discovery

While investigating the system startup flow for the user (`"every time we start the system we run the demo flow"`), traced the `lifespan` handler in `anvil/api/app.py` through `_warmup_demo_model()` → `warmup_demo_via_system_pipeline()` in `anvil/services/inference/demo_model_provider.py`.

Found that `warmup_demo_via_system_pipeline()` unconditionally ran the full training pipeline regardless of whether a checkpoint already existed at `data/models/demo/model.json`. The background daemon thread meant the ~30-60s CPU burn was invisible to startup timing but wasteful.

## What was done

Added an early-exit guard at line 105 of `demo_model_provider.py`:

```python
if DEMO_MODEL_PATH.exists():
    logger.info("Demo model exists at %s, skipping warmup", DEMO_MODEL_PATH)
    try:
        model = LlamaModel.load(str(DEMO_MODEL_PATH))
        if model.chars is not None:
            _demo_provider._model = model
            _demo_provider._chars = model.chars
    except Exception:
        logger.warning("Failed to load existing demo model, will re-train", exc_info=True)
    else:
        return
```

- Loads the checkpoint and caches it in `_demo_provider` so the first inference request has zero delay
- On load failure (corrupted checkpoint), falls through to re-train (conservative fallback)
- All 20 existing tests pass

## Files changed

- `anvil/services/inference/demo_model_provider.py` — added early-exit guard

## Discoveries

- [[Discoveries/demo-warmup-redundant-retrain]]