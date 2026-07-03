# API Contracts: Usable External Models

## Existing Endpoints (no changes)

### `POST /v1/models/{model_id}/download`
Triggers async download of model assets. Unchanged — but the download now stores to `models/{model_id}/hf/` layout.

### `GET /v1/models/external/{model_id}`
Returns external model metadata including `asset_availability` and `runnable_status`. UI uses this to show/hide Play/Train buttons. Unchanged.

### `GET /v1/models/{model_id}/download/{job_id}/status`
Returns download job status with `"complete"`, `"failed"`, `"downloading"`, or `"queued"`. Unchanged.

## Inference Resolution (internal contract)

### `InferenceService.load_model(model_id: int, ...)`

**New resolution path** (fourth, inserted before the ValueError fallthrough):

```
Input:
  model_id: int  — may be either an experiment ID (existing) or external model ID (new)
```

**Behavior**: 
1. Try existing paths (cache → adapter → experiment artifact → MLflow)
2. If none succeed, check if `model_id` is an external model:
   - Query `ExternalModelRepository.get(model_id)`
   - If exists AND `asset_availability == "assets_available"` AND `runnable_status == "runnable"`:
     - Build local path: `models/{model_id}/hf/` 
     - Log: `"External model {model_id} loaded from local"` 
     - Load via `AutoModelForCausalLM.from_pretrained(local_path, trust_remote_code=False)`
     - Convert via `_hf_state_dict_to_anvil_format()`
     - Build tokenizer via `AutoTokenizer.from_pretrained(local_path)`
     - Cache and return `LoadedModel`
   - Else if `asset_availability != "assets_available"`:
     - Raise `ValueError("Assets not downloaded — use POST /v1/models/{model_id}/download first")`
   - Else (not an external model, or track-only):
     - Fall through to existing `ValueError("Model not found")`

### `InferenceService._compose_adapter_with_repo(model_id, adapter_id, repo)`

**Modified behavior**: Prefer local assets when available.

1. Resolve base external model: `ext_model = await ext_repo.get(model_id)`
2. Check local asset availability: `can_load_local = _check_assets_available(model_id)`
3. If `can_load_local`:
   - `base_path = f"models/{model_id}/hf/"`
   - Log: `"Composing adapter {adapter_id} on external model {model_id} from local assets"`
   - `base_model = AutoModelForCausalLM.from_pretrained(base_path)`
4. Else (fallback):
   - Log: `"Composing adapter {adapter_id} on external model {model_id} from Hub"`
   - `base_model = AutoModelForCausalLM.from_pretrained(source_id)` (existing behavior)
5. Continue with existing PEFT compose + merge + convert flow unchanged.

## UI Contract (model_detail.html)

Already implemented in the working tree:

| Element | Condition | Behavior |
|---------|-----------|----------|
| Download button | `asset_availability == "metadata_only"` | Visible, clickable |
| Asset badge | `assets_available` | Green "available" |
| Asset badge | `assets_pending` | Cyan "downloading" |
| Asset badge | `metadata_only` | Yellow "metadata only" |
| Play button | `assets_available AND runnable` | Visible (TODO in P2 implementation) |
| Play button | otherwise | Hidden |
| Continue Training | same as Play | Hidden until P2 implementation |
| Polling | after download click | 2s poll until complete/failed, updates badge