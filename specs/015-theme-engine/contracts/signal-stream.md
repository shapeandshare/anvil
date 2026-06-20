# Contract: Live Signal Stream (SSE, neutral)

**Purpose**: Define the widened SSE event surface that the backend emits and the `SSESession` consumes. The backend emits **neutral** signals only — never theme-specific values (R6, FR-011). This contract is the single source of truth for the `metrics` payload and the new `divergence` event.

**Endpoint**: `GET /v1/training/stream/{run_id}` — `Content-Type: text/event-stream` (unchanged).

## Events

Each SSE frame: `event: <name>\ndata: <json>\n\n`. `data` is a JSON object.

### `metrics`  *(widened — additive, back-compatible)*
```json
{
  "step": 1234,
  "loss": 2.713,
  "device": "mps",
  "elapsed_sec": 42.5,
  "steps_per_sec": 18.2,
  "eta_sec": 130.4,
  "grad_norm": 0.84,
  "tokens_per_sec": 596000.0
}
```
| Key | Type | Notes |
|---|---|---|
| `step` | int | existing |
| `loss` | float | existing |
| `device` | str | existing |
| `elapsed_sec` | float | existing |
| `steps_per_sec` | float \| null | existing |
| `eta_sec` | float \| null | existing |
| `grad_norm` | float \| null | **NEW**. Global un-clipped norm sampled after `backward()`; `null` on the pure stdlib engine (R2). |
| `tokens_per_sec` | float \| null | **NEW**. Derived in the service closure from a **rolling sum of per-step `tokens` ÷ window-elapsed** (R4). NOT `batch_size × context_len` — the engines are unbatched and tokens/step varies (`= min(block_size, len-1)`). `null` until a rate is available. |

**Rules**:
- Additive only — existing consumers keep working (`training.html` reads `step`/`loss`).
- NaN/inf loss is NOT emitted as `metrics`; it is routed to `divergence` (below).
- Field set is theme-NEUTRAL; MUST NOT include `disturbance`, `clarity`, colors, or any theme term.

### `divergence`  *(new)*
```json
{ "step": 1450, "reason": "loss_nan" }
```
| Key | Type | Notes |
|---|---|---|
| `step` | int | step at which divergence was detected |
| `reason` | str | `loss_nan` \| `loss_inf` \| `grad_explosion` (`DivergenceReason` StrEnum-backed) |

**Rules**:
- Emitted by the **service closure** when `math.isnan(loss) or math.isinf(loss)` (and optionally a grad-norm explosion threshold) is detected (R3).
- The engines do NOT break on NaN themselves, so the service **raises `DivergenceError`** from the progress closure to halt the run (mirroring the existing `StopRequested` pattern); `complete` is therefore NOT emitted for a diverged run, and persisted run status is reconciled to a terminal `diverged` state.
- The SSE route MUST include `divergence` in its terminal break set (currently `("complete","error")` in `api/v1/training.py`).

### Unchanged events
`complete {final_loss, samples, device}`, `error {message}`, `submitted {backend, device}`, `export_error {error}`, `heartbeat {}`. **New** `milestone {step}` neutral cadence marker emitted every N steps (R5) — additive, **no artifact write, does NOT imply a model checkpoint**, ignorable by existing consumers. (Named `milestone` rather than `checkpoint` to avoid implying a saved artifact.)

## Client consumer: `SSESession` (sse.js)

Add two named-event handlers; everything else unchanged.

```js
session.onmetrics    = function(m) { /* m has the widened fields */ };
session.ondivergence = function(d) { /* NEW: {step, reason} */ };
session.onmilestone  = function(c) { /* NEW: {step} neutral quench-beat marker (no artifact) */ };
session.oncomplete   = function(c) { /* unchanged */ };
```

**Rules**:
- `SSESession` registers `addEventListener('divergence', …)` and `addEventListener('milestone', …)`, exposing `ondivergence`/`onmilestone` (mirrors existing `onmetrics`/`oncomplete` pattern).
- Reconnection/backoff behavior unchanged (5 retries, exponential `[1,2,4,8,16]s`).
- Consumers MUST tolerate missing/`null` `grad_norm`/`tokens_per_sec` (FR-025, SC-008).

## Backend value object: `StepMetrics` (Pydantic BaseModel, service layer)

Lives at `anvil/services/training/step_metrics.py` (NOT in `core/` — Article I). Constructed in the service closure from the engine's stdlib `CoreStepObservation(step, loss, tokens, grad_norm)` plus service-derived fields, then serialized to the `metrics` `data`.

```python
class StepMetrics(BaseModel):
    step: int
    loss: float
    device: str
    elapsed_sec: float
    steps_per_sec: float | None = None
    eta_sec: float | None = None
    grad_norm: float | None = None       # NEW (un-clipped, post-backward)
    tokens_per_sec: float | None = None  # NEW (rolling Σ tokens ÷ elapsed)
```

**Engine boundary** (`core/`, stdlib only):
```python
class CoreStepObservation(NamedTuple):  # plain stdlib, zero-dep
    step: int
    loss: float
    tokens: int            # actual tokens this step (n); unbatched/variable
    grad_norm: float | None
```

**Callback type** (`services/compute/protocol.py`): widened from `Callable[[int, float], None]` to `Callable[[CoreStepObservation], None]` (engine→backend), with the service closure assembling `StepMetrics` and maintaining a rolling token-sum for `tokens_per_sec`.

## Contract tests (TDD — write first)

| Test | Asserts |
|---|---|
| `test_metrics_payload_includes_new_fields` | `metrics` data JSON has `grad_norm` and `tokens_per_sec` keys (nullable). |
| `test_metrics_back_compat` | existing keys unchanged & present. |
| `test_divergence_event_on_nan` | feeding `loss=nan` emits `event: divergence` with `reason=loss_nan`, **halts the run (no further `metrics`)**, and no subsequent `complete`. |
| `test_divergence_breaks_stream` | the SSE generator terminates after a `divergence` event (route break set includes `divergence`). |
| `test_divergence_persists_status` | a diverged run's persisted status is reconciled to a terminal `diverged`/`failed` state via the service/repository (FR-030). |
| `test_milestone_cadence_marker` | a `milestone {step}` event is emitted at the configured step interval; payload is neutral; no artifact is written. |
| `test_tokens_per_sec_rolling` | `tokens_per_sec` equals the rolling sum of per-step `tokens` ÷ window-elapsed (correct for **variable** per-step `tokens`); `null` until a rate exists. NOT computed from a fixed `batch_size × context_len`. |
| `test_stdlib_grad_norm_nullable` | stdlib-engine run emits `grad_norm: null` without error. |
| `test_step_metrics_model` | `StepMetrics` validates types; rejects non-neutral extra fields if `model_config` forbids extras. |
