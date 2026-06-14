# API Contract: Optimizer State SSE Event

**Event Type**: `optimizer_state` (in `/v1/training/stream/{run_id}` SSE stream)
**Purpose**: Stream per-parameter optimizer state during training for the Adam lesson.

## Event Format

```
event: optimizer_state
data: {"step": 42, "params": [{"index": 0, "m": 0.0023, "v": 0.0001, "grad": -0.0156}, ...]}
```

## Data Fields

| Field | Type | Description |
|-------|------|-------------|
| `step` | int | Current training step |
| `params` | ParamSnapshot[] | Per-parameter optimizer state |

**ParamSnapshot**:
| Field | Type | Description |
|-------|------|-------------|
| `index` | int | Parameter index (0 to N-1) |
| `m` | float | First moment (momentum) estimate |
| `v` | float | Second moment (adaptive LR) estimate |
| `grad` | float | Current gradient value (pre-reset) |

## Frequency

Sent every N steps (configurable, default: every 10 steps) to avoid overwhelming the SSE stream. Controlled by `optimizer_snapshot_interval` parameter in training config.

## Implementation Notes

- Only available for CPU training path (PyTorch Adam does not expose m/v directly)
- If GPU path is used, emit no `optimizer_state` events (Adam lesson falls back gracefully)
- `m` and `v` are captured AFTER the Adam update but BEFORE gradient reset
- Total message size: ~`N_params * 3 floats * 8 bytes ≈ 100KB` for 4192 params (compressed, well within SSE limits)

## Backend Changes Required

### `engine.py` — `train()` function
Add `optimizer_state_callback(step, m, v, grads)` parameter:
```python
def train(docs, ..., optimizer_state_callback=None):
    ...
    for step in range(num_steps):
        # ... forward + backward ...
        grads = [p.grad for p in model.params]
        # ... Adam update ...
        if optimizer_state_callback:
            optimizer_state_callback(step, m, v, grads)
```

### `training.py` — `TrainingService`
Extend the existing `progress_callback` to emit `optimizer_state` events:
```python
def progress_callback(step, loss):
    # ... existing metrics event ...
    
def optimizer_state_callback(step, m, v, grads):
    asyncio.run_coroutine_threadsafe(
        queue.put({
            "event": "optimizer_state",
            "data": json.dumps({
                "step": step,
                "params": [
                    {"index": i, "m": m[i], "v": v[i], "grad": grads[i]}
                    for i in range(len(m))
                ]
            })
        }),
        loop,
    )
```