# Data Model: Usable External Models

## Affected Entities

### ExternalModel (table: `external_models`)

No new fields — the existing schema already supports this feature.

| Field | Type | Purpose | Used by |
|-------|------|---------|---------|
| `id` | int (PK) | Model identifier; used as `model_id` in `load_model()` | Inference, UI, asset download |
| `source_identifier` | str | HF repo ID (e.g. `"meta-llama/Llama-3.1-8B"`) | `from_pretrained()` fallback path |
| `asset_availability` | str | `"metadata_only"`, `"assets_pending"`, or `"assets_available"` | UI (show/hide run/train actions), inference load gate |
| `runnable_status` | str | `"runnable"` or `"track_only"` | UI (show/hide Play/Train) |
| `architecture_family` | str | e.g. `"LlamaForCausalLM"` | Architecture allow-list check |
| `display_name` | str | User-visible model name | UI detail page |

**Key constraint**: `load_model(model_id=X)` MUST check that `asset_availability == "assets_available"` AND `runnable_status == "runnable"` before attempting a local load, and MUST return a clear error otherwise.

### ModelAsset (table: `model_assets`)

No schema changes needed — the `storage_path` field already records the actual path.

| Field | Type | Current example | New example |
|-------|------|----------------|-------------|
| `storage_path` | str | `models/42/assets/a1b2c3/model.safetensors` | `models/42/hf/model.safetensors` |
| `asset_type` | str | `WEIGHTS`, `TOKENIZER`, `CONFIG` | Same (unchanged) |
| `status` | str | `AVAILABLE` | Same (unchanged) |
| `sha256` | str | `a1b2c3d4...` | Same integrity hash, recorded as metadata only |

**Note**: The existing `models/{model_id}/assets/{sha256}/{filename}` layout is **not** removed or migrated. Only NEW downloads use the HF-standard `models/{model_id}/hf/{filename}` layout.

### InferenceService (in-memory model cache)

No schema changes. The existing `_cache: dict[tuple[int, int], tuple[LlamaModel, Tokenizer]]` caches by `(model_id, version)`. External models will use `version=1` by default, consistent with existing convention. The cache is populated on first load and reused on subsequent calls.

## State Transitions

### Asset availability lifecycle

```
metadata_only ──(download started)──> assets_pending ──(download complete)──> assets_available
                      │                                                           │
                      └──(download failed)──> metadata_only                        │
                                                                                   │
                                               assets_available ──(all assets deleted)──> metadata_only
```

### Inference load resolution order

```
load_model(model_id)
  │
  ├── cache hit (model_id, version)? → return cached (LlamaModel, Tokenizer)
  │
  ├── adapter_id provided? → try _load_adapter_model() [ext model resolution]
  │     └── fail → fall through
  │
  ├── experiment artifact exists? → load from `data/models/experiment_{id}.json`
  │
  ├── MLflow model exists? → load from MLflow Model Registry
  │
  ├── EXTERNAL MODEL PATH (NEW):
  │     ExternalModel exists + assets_available + runnable?
  │     → load from `models/{model_id}/hf/` via from_pretrained(local_dir)
  │     → convert via _hf_state_dict_to_anvil_format()
  │     → cache + return
  │
  └── raise ValueError("Model not found")
```

## Validation Rules

- **Load gate**: Local load requires `asset_availability == "assets_available"` AND `runnable_status == "runnable"`
- **Integrity**: `from_pretrained()` validates safetensors internally; SHA-256 metadata exists for independent verification
- **Runtime dependency**: If `transformers`/`torch` not installed, load attempt fails with clear message — no crash
- **Fallback**: When local assets absent + network available → use `from_pretrained(source_identifier)` from Hub
- **Offline**: When local assets absent + network unavailable → fail with "assets not available — download required"