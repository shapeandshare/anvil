---
title: "045 Adapter Inference Export - data model"
type: spec
tags:
  - type/spec
  - domain/training
  - domain/mlops
created: "2026-07-01"
updated: "2026-07-01"
---

# Data Model — Adapter Inference, Merge & Export

## Entities

### ComputeResult (extended for adapter shape)

The existing `ComputeResult` Pydantic model (`anvil/services/compute/result.py`) gets two new fields to
represent the adapter result shape explicitly:

| Field | Type | Description |
|---|---|---|
| (existing) `status` | `ComputeStatus` | Lifecycle status |
| (existing) `model` | `object \| None` | `LlamaModel` instance (local path) — `None` for adapter/remote |
| (existing) `artifact_uris` | `dict[str, str]` | Contains `"adapter_path"` key for adapter results |
| **NEW** `adapter_id` | `str \| None` | Scoped adapter identifier (e.g. `"run_42"`) when result is adapter-shaped |
| (existing) `engine` | `TrainingEngine` | Training engine used |
| (existing) `backend` | `ComputeBackendResult` | Compute backend used |

**Result shapes** after extension:

| Shape | `model` | `adapter_id` | `artifact_uris` |
|-------|---------|-------------|-----------------|
| Local full weights | `LlamaModel` | `None` | `{}` |
| Remote | `None` | `None` | `{remote URIs}` |
| Adapter | `None` | `"run_42"` | `{"adapter_path": "..."}` |

### Standalone Model (merge+export output)

Not a new entity — this is a registered MLflow model version in the Model Registry, with lineage tags:

| Tag | Value | Description |
|-----|-------|-------------|
| `anvil.base_model_ref` | `int` (experiment ID) | Base model that was fine-tuned |
| `anvil.adapter_id` | `str` (e.g. `"run_42"`) | Adapter that was merged |
| `anvil.merge_timestamp` | ISO 8601 | When the merge occurred |
| `anvil.origin` | `"merge"` | Distinguishes from trained-from-scratch models |
| `anvil.method` | `"lora"` or `"qlora"` | Fine-tuning method used |

Storage path: `data/models/{base_model_id}/merged/{adapter_id}/` containing:
- `model.safetensors` — merged weights in anvil/HF format
- `config.json` — merged model config
- `tokenizer.json` — tokenizer metadata
- `MLmodel` — MLflow pyfunc loader
- `conda.yaml` — conda environment spec

### Adapter (reuse from spec 044)

No changes to the `LoRAAdapter` ORM model from spec 044. The existing entity covers all needs:

| Field | Type | Description |
|-------|------|-------------|
| `id` | `int` (PK) | Primary key |
| `external_model_id` | `int` (FK) | Base model this adapter applies to |
| `run_id` | `int` | Training run that produced this adapter |
| `adapter_id` | `str` | Scoped unique ID (`"run_{run_id}"`) |
| `label` | `str \| None` | Optional display label |
| `method` | `str` | `"lora"` or `"qlora"` |
| `storage_path` | `str` | `models/{base_id}/adapters/{run_id}/` |
| `lora_rank` | `int` | LoRA rank |
| `lora_alpha` | `float` | LoRA scaling alpha |
| `lora_target_modules` | `str \| None` | JSON-encoded list |
| `lora_dropout` | `float \| None` | Dropout rate |
| `lora_bias` | `str \| None` | Bias setting |
| `final_loss` | `float \| None` | Final loss |
| `final_step` | `int \| None` | Final step |
| `merged_at` | `datetime \| None` | **Still used** — records when merge completed |
| `created_at` / `updated_at` | `datetime` | Timestamps |

**Important**: The adapter is NOT deleted, nor is `merged_at` set prematurely. The existing
`AdapterMergeService.mark_merged()` behavior changes: instead of setting `merged_at` and deleting
files, `merged_at` is set only AFTER the merged artifact is fully written and registered.

## State Transitions

### Adapter lifecycle (no change from spec 044)

```
CREATED → ADAPTER_SAVED → INFERENCE (base+adapter composition)
                         → MERGE+EXPORT (adapter persists, standalone model created)
```

### Merge+Export flow

```
START
  │
  ├── 1. Resolve adapter from LoRAAdapterRepository
  ├── 2. Load base model + adapter via PeftModel
  ├── 3. Merge: PeftModel.merge_and_unload()
  ├── 4. Convert merged HF model → anvil LlamaModel
  ├── 5. Export: SafetensorsExportService.export()
  │       └── Write to temp directory
  ├── 6. Atomically rename temp → final path
  ├── 7. Register in MLflow Model Registry with lineage tags
  ├── 8. Set adapter.merged_at
  └── DONE
```

On failure at any step between 3 and 8: clean up temp directory and report error.
Adapter files are NEVER modified or deleted.
