# API Contract — Adapter Inference, Merge & Export

## Endpoint: `POST /v1/inference/generate`

> **Note**: This endpoint may already exist if spec 044 (FR-020a) implemented it. If so, the only
> change is ensuring `adapter_id` composition works correctly. If not, this spec introduces it.

### Request (existing or new Pydantic model, `extra="forbid"`)

```json
{
  "model_id": 1,
  "prompt": "What is fine-tuning?",
  "adapter_id": "run_42",
  "temperature": 0.7,
  "max_tokens": 100
}
```

**Fields**:
- `model_id: int` — The experiment/model ID
- `prompt: str` — Input prompt text
- `adapter_id: str | None` — When provided, generation composes base model + adapter via `PeftModel.from_pretrained()`. When absent/`null`, falls back to base-only generation.
- `temperature: float` — Sampling temperature (default: `0.7`)
- `max_tokens: int` — Maximum tokens to generate (default: `100`)

**Validation**:
- `adapter_id`, if provided, must reference an existing adapter for the specified `model_id`
- Unknown `adapter_id` → HTTP 404 with message listing available adapter IDs for that base model

### Response

```json
{
  "text": "Fine-tuning is the process of...",
  "model_id": 1,
  "adapter_id": "run_42"
}
```

## Internal Service Contract: AdapterMergeService

### Method: `merge_and_export()`

```python
async def merge_and_export(
    self,
    model_id: int,
    adapter_id: str,
    output_dir: str | Path,
) -> dict[str, Any]:
    """Merge a LoRA adapter into its base model and export as standalone artifact.

    Non-destructive: adapter files are NOT deleted. The merged artifact is
    registered in MLflow Model Registry with full lineage tags.

    Parameters
    ----------
    model_id : int
        FK to ExternalModel (base model).
    adapter_id : str
        Scoped adapter identifier (e.g. "run_42").
    output_dir : str | Path
        Directory for the exported safetensors + config + tokenizer.

    Returns
    -------
    dict with keys:
        - "status": "completed" or "failed"
        - "model_name": MLflow registered model name
        - "model_version": MLflow model version
        - "artifact_path": path to merged weights
        - "error": error message if failed
    """
```

**Atomicity**: Writes to a temp directory first, then atomically renames to `output_dir`.
On failure at any point, the temp directory is cleaned up.

## Internal Service Contract: InferenceService.load_model()

### Extended behavior

Current signature (already accepts `adapter_id`):
```python
async def load_model(
    self,
    model_id: int | None = None,
    version: int | None = None,
    adapter_id: str | None = None,
) -> LoadedModel:
```

**Extended behavior**:
- When `adapter_id` is provided: after loading the base model, call
  `PeftModel.from_pretrained(base_hf_model, adapter_path)` to compose the adapter,
  then either (a) run `merge_and_unload()` and convert back to `LlamaModel`, or
  (b) keep as PeftModel and adapt the inference path.
- When `adapter_id` is `None`: behavior unchanged — base-only inference.

**Decision**: Use `merge_and_unload()` at load time for simplicity — the composed model
becomes a standard `LlamaModel` immediately, compatible with all existing inference
methods (tokenize, embeddings, attention, sampling distribution, generate).

## ComputeResult Contract

### Extended schema

```python
class ComputeResult(BaseModel):
    # ... existing fields ...
    adapter_id: str | None = None  # NEW
```

**Backward compatibility**: `adapter_id` defaults to `None`, so existing code that constructs
`ComputeResult` without it continues to work. Serialization is unaffected.

## MLflow Lineage Tags

After merge+export, the registered model version has these tags:

| Tag | Value | Source |
|-----|-------|--------|
| `anvil.origin` | `"merge"` | This spec |
| `anvil.base_model_ref` | str(model_id) | From merge params |
| `anvil.adapter_id` | str(adapter_id) | From merge params |
| `anvil.merge_timestamp` | ISO 8601 | From `datetime.now(timezone.utc)` |
| `anvil.method` | `"lora"` or `"qlora"` | From LoRAAdapter.method |
