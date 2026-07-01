# API Contract — Local LoRA Fine-Tuning

## Endpoint: `POST /v1/training/start`

### Request (extended `TrainConfig`)

```json
{
  "method": "lora",
  "base_model_ref": 1,
  "dataset_id": 5,
  "lora_rank": 8,
  "lora_alpha": 16,
  "lora_target_modules": ["q_proj", "v_proj"],
  "lora_dropout": 0.05,
  "lora_bias": "none",

  "num_steps": 500,
  "learning_rate": 2e-4,
  "compute_backend": "auto"
}
```

**Validation**:
- `method` is `"full"` (default when absent), `"lora"`, or `"qlora"`
- When `method != "full"`: `base_model_ref` is REQUIRED, architecture fields (`n_embd`, `n_layer`, `n_head`, `block_size`) are IGNORED (inherited from base model)
- When `method == "full"`: all `lora_*` fields MUST be absent/null (HTTP 422 if present)
- `lora_target_modules` defaults to the curated catalog's `default_target_modules` for that architecture if omitted
- `lora_rank`, `lora_alpha`, `lora_dropout` default to peft library defaults if omitted

### Response

```json
{
  "run_id": 42,
  "mlflow_run_id": "abc123def",
  "experiment_id": 7,
  "status": "running",
  "tracking": "active"
}
```

No structural changes to the response body.

## Endpoint: `POST /v1/inference/generate` (NEW — does not exist today)

> ⚠️ **This is a NEW endpoint.** The existing inference API (`anvil/api/v1/inference.py`) is
> educational-only (9 routes: tokenize, embeddings, attention, sampling-distribution, forward-graph,
> backward-graph, autograd-example, loss-breakdown, model-params). There is NO text-generation route.
> This spec introduces `POST /v1/inference/generate`. Exact route name TBD in implementation
> (`/generate` recommended); it must route through `AnvilWorkbench` per Article VII.

### Request (new Pydantic model, `extra="forbid"`)

```json
{
  "model_id": 1,
  "prompt": "What is fine-tuning?",
  "adapter_id": "run_42",
  "temperature": 0.7,
  "max_tokens": 100
}
```

**Field**: `adapter_id: str | None` — when provided, generation composes base model + adapter via
`PeftModel.from_pretrained()`. When absent/`null`, falls back to base-only generation.

**Validation**:
- `adapter_id`, if provided, must reference an existing adapter for the specified `model_id`
- Unknown `adapter_id` → HTTP 404 with message listing available adapter IDs for that base model

### Response

New response model returning generated text (e.g. `{ "text": "...", "model_id": 1, "adapter_id": "run_42" }`).

### `InferenceService.load_model()` extension

Current signature: `async def load_model(self, model_id: int | None = None, version: int | None = None) -> LoadedModel`.
Extended to accept an optional adapter reference and compose base + adapter at load time. Currently
loads a single `LlamaModel` from `data/models/experiment_{id}.json` with NO adapter concept.

## SSE Events (unchanged)

Existing SSE event types are reused exactly:
- `metrics` — per-step loss, tokens/sec, etc.
- `complete` — training finished with `final_loss`, `samples`
- `error` — training failed
- `divergence` — non-finite loss
- `milestone` — every 10% of steps
- `heartbeat` — 30s keepalive

No new event types needed. Adapter-specific metadata is included in the `complete` event's
`data` payload as optional fields:
```json
{
  "event": "complete",
  "data": {
    "final_loss": 0.42,
    "samples": ["..."],
    "device": "cuda",
    "adapter_id": "run_42",
    "adapter_path": "models/1/adapters/run_42/"
  }
}
```

## Backend Registry Entry

| Registry name | Enum member | Backend class | Availability |
|---|---|---|---|
| `"local-lora"` | `RegistryBackend.LOCAL_LORA` | `LocalLoraBackend` | `[finetune]` extra installed AND base model is in curated catalog |

**Resolution priority** in `resolve_backend()`:
1. If `method == "full"` → existing resolve logic (unchanged)
2. If `method == "lora"` or `method == "qlora"` → resolve to `local-lora` backend
3. If `base_model_ref` is set and method is `"full"` → existing warm-start path (unchanged)