# Research: Usable External Models

## Local Asset Loading Path

### Decision
Add a new resolution branch in `InferenceService.load_model()` that resolves external model IDs (from `external_models` table) and loads weights from the local HF-standard directory at `models/{model_id}/hf/`, converting to anvil `LlamaModel` via the existing `_hf_state_dict_to_anvil_format()` helper.

### Rationale
- `load_model()` already has a three-path resolution: cache → experiment artifact → MLflow. Adding a fourth path for external models is the same pattern.
- The existing `_compose_adapter_with_repo()` already demonstrates the end-to-end flow: `from_pretrained()` → `PeftModel` → `merge_and_unload()` → `_hf_state_dict_to_anvil_format()` → `LlamaModel.load()`. For bare inference, we skip the PEFT step and go directly from `from_pretrained()` to conversion.
- The existing `_create_adapter_tokenizer()` (line 748) builds a tokenizer from `AutoTokenizer.from_pretrained(source_id)` — reusable for the bare path.
- Integrity verification is delegated to `from_pretrained()` (which validates safetensors files internally) and the existing SHA-256 metadata recorded on each `ModelAsset` row.

### Alternatives considered
- **Symlink farm at load time** (keep sha256 layout, materialize temp dir via symlinks) — rejected per Q1 clarify. Adds complexity at load time and temp-file management.
- **Flat key-value store with manifest** — rejected per Q1 clarify. Over-engineered for single-host local storage.

## Storage Layout

### Decision
Download assets directly to `models/{model_id}/hf/` with canonical filenames:
- `model.safetensors` (weights)
- `config.json` (model configuration)
- `tokenizer.json` (tokenizer)
- `tokenizer_config.json` (tokenizer configuration)

SHA-256 fingerprints are recorded as `ModelAsset` metadata (existing `sha256`, `storage_path` fields), not as path components.

### Rationale
- `from_pretrained(local_dir)` expects exactly this layout — passing `models/{model_id}/hf/` works directly.
- The existing `model_asset_service.py` already downloads each file and stores it via `self._store.put(storage_path, ...)`. The change is just the path: from `models/{model_id}/assets/{sha256}/{filename}` to `models/{model_id}/hf/{filename}`.
- The `ModelAsset` table already has `storage_path`, `sha256`, `size_bytes` fields — these record the canonical path and integrity hash regardless of directory structure.

### Existing sha256 layout
The old layout (`assets/{sha256}/`) is **not** removed or migrated. New downloads use the new path; old records remain queryable but are not loadable. Per spec clarification, no legacy downloads exist.

## Warm-Start Full Fine-Tuning

### Decision
The existing `_validate_warm_start()` in `training_run_service.py` calls `inference.load_model(model_id=config.base_model_ref)`. Once `load_model()` supports external model IDs, warm-start validation and initialization will work automatically for external models.

### Rationale
- `_validate_warm_start()` (line 358) validates architecture dimensions (`n_embd`, `n_head`, `n_layer`) against the training config. This validation is already generic — it works with any `LoadedModel`.
- For full fine-tuning, the torch training engine (`local_torch_backend.py`) calls `load_model(base_model_ref)` to get the `LlamaModel`, then converts it to PyTorch. No additional changes needed beyond making `load_model()` resolve external models.
- For LoRA/QLoRA, the `local_lora_backend.py` already uses `from_pretrained(source_identifier)` from HF Hub. This should be updated to prefer the local path when assets are available (FR-005).

## Local-First Asset Resolution Across All Consumers

### Decision
All consumers that load external model weights (adapter inference, adapter merge, evaluation) should use the same local-load path when assets are available, falling back to `from_pretrained(source_identifier)` from the Hub only when assets are absent.

### Current state of consumers
| Consumer | Current behavior | Change needed |
|----------|-----------------|---------------|
| Adapter inference (`_compose_adapter_with_repo`) | `from_pretrained(source_id)` from Hub | Prefer local `models/{model_id}/hf/`; fallback to Hub |
| Adapter merge (`merge_service.py`) | `from_pretrained(source_id)` from Hub | Same as above |
| Evaluation (`evaluation_service.py`) | `inference.load_model()` which calls adapter path | Already covered by adapter inference change |

### Implementation approach
Add a `_resolve_local_path(model_id) -> str | None` helper to `InferenceService` that checks `ExternalModelRepository` for asset availability and returns the local path if assets are available. The adapter compose path can then call `from_pretrained(local_path or source_id)`.

## Observability

### Decision
Emit a structured log line on every external model load:
```python
logger.info("External model %d loaded from %s", model_id, source)
```
Where `source` is `"local"` or `"hub"`.

### Rationale
Per Q2 clarify. Minimal cost, answers SC-002/SC-005 verification, enables debugging. No Prometheus counters or additional infrastructure.

## Graceful Degradation

### Decision
When `[finetune]` extras are not installed (`transformers`/`torch` not available), the local-load path must detect this and raise a clear error rather than crashing with an `ImportError`.

### Implementation
- `_TRANSFORMERS_AVAILABLE` and `_PEFT_AVAILABLE` flags are already checked at the top of `inference.py` (line 582 in `_compose_adapter_with_repo`).
- The bare external model load branch should check the same flags and fail with: `"External model loading requires the [finetune] extra. Run: pip install anvil[finetune]"`.