---
title: "045 Adapter Inference Export - research"
type: spec
tags:
  - type/spec
  - domain/training
  - domain/mlops
created: "2026-07-01"
updated: "2026-07-01"
---

# Research — Adapter Inference, Merge & Export

## Resolved Decisions

### Decision 1: ComputeResult adapter shape
- **Decision**: Use `artifact_uris` dict with `"adapter_path"` key (existing pattern from `LocalLoraBackend`), plus a new explicit `adapter_id` field on `ComputeResult` for clarity.
- **Rationale**: The existing pattern from spec 044 already stores `artifact_uris={"adapter_path": str(adapter_path)}` on `ComputeResult`. Adding a typed `adapter_id` field differentiates the adapter shape from the existing local/remote paths without breaking backward compatibility. No new class hierarchy needed — just two new fields.
- **Alternatives considered**: New `AdapterComputeResult` subclass — rejected as over-engineering (YAGNI, Article XI). The existing `ComputeResult` is already a union shape.

### Decision 2: Non-destructive merge
- **Decision**: `AdapterMergeService.merge()` will NOT delete the adapter or mark it as merged. Instead, the adapter persists and merge+export creates a new standalone registered model with full lineage `(base, adapter)`.
- **Rationale**: The existing code in `merge_service.py` calls `await self._repo.mark_merged()` and deletes adapter files. Per the spec clarification (Q3), the adapter MUST persist as a distinct entity. This requires changing `merge_service.py` to stop deleting/marking-merged, and instead register the output as a new model in MLflow Model Registry with lineage tags.
- **Alternatives considered**: Keeping destructive merge and adding a "copy before merge" step — rejected as adding complexity without benefit. Simpler to just not delete.

### Decision 3: Adapter composition in inference
- **Decision**: `InferenceService.load_model()` will use `peft.PeftModel.from_pretrained(base_model, adapter_path)` to actually compose base + adapter at load time when `adapter_id` is provided.
- **Rationale**: Currently `load_model()` accepts `adapter_id` but only resolves and stores the path — it does NOT compose the adapter. The actual PeftModel composition is the gap. The composed model must be a `LlamaModel` for compatibility with the existing inference API.
- **Alternatives considered**: Keeping the model in HF/PeftModel format and adding a new inference path — rejected because the existing inference API (tokenize, embeddings, attention, sampling distribution, etc.) operates on `LlamaModel`. The merge output must be convertible to `LlamaModel` format.

### Decision 4: Merge+export atomicity
- **Decision**: Write merged weights to a temp directory first, then atomically rename to the final path.
- **Rationale**: Existing patterns in `LocalFileStore.put()` use `tempfile.NamedTemporaryFile` + `shutil.move()`. The same pattern applies to directory-level operations. If merge or export fails mid-operation, the temp directory is cleaned up.
- **Alternatives considered**: Writing in-place with rollback — more complex; locking — unnecessary for single-user context.

### Decision 5: Model registration after merge
- **Decision**: Use `TrackingService.register_source_model(run_id=..., name=...)` (existing, verified signature) followed by `TrackingService.set_tag(run_id, key, value)` (existing) for each lineage tag: `anvil.origin="merge"`, `anvil.base_model_ref`, `anvil.adapter_id`, `anvil.merge_timestamp`, `anvil.method`. NOTE there is **no adapter `version`** — the scoped key is `(external_model_id, adapter_id)`.
- **Rationale**: This is the existing registration mechanism used by `on_complete` in `training.py`. Adding lineage tags follows the warm-start pattern where `anvil.base_model_ref` and `anvil.warm_start` tags are set on the MLflow run.
- **Dependency gap (verified)**: `AdapterMergeService.__init__` currently takes only `(LoRAAdapterRepository, LocalFileStore)` and is instantiated inline in `anvil/api/v1/adapters.py:149` — it has NO `TrackingService`. Lineage registration REQUIRES injecting a `TrackingService` dependency and exposing the service on `AnvilWorkbench` (see tasks T017).
- **Alternatives considered**: Creating a new registration endpoint — rejected; reuse the existing one with extra tags.

### Decision 6: Export of merged model
- **Decision**: After merge, pass the merged weights through `SafetensorsExportService.export()` to produce HF-compatible safetensors + config + tokenizer. If the merge was done via HF `PeftModel`, the merged model is a `PreTrainedModel` that needs conversion to anvil's `LlamaModel` format first.
- **Rationale**: The existing export pipeline produces the correct artifact format (safetensors, config.json, tokenizer.json, MLmodel, conda.yaml). The merged model is a standard HF model after `merge_and_unload()`, which means it can be loaded as an anvil `LlamaModel` if the architecture matches (TinyLlama-class models are LlamaForCausalLM — same as anvil's LlamaModel).
- **Alternatives considered**: Using HF `save_pretrained()` directly instead of safetensors pipeline — rejected because it bypasses the anvil export pipeline and produces artifacts incompatible with anvil's inference service.

### Decision 7: HF PreTrainedModel → anvil LlamaModel conversion

- **Decision**: After `PeftModel.merge_and_unload()`, extract weights via HF
  `model.state_dict()`, map HF tensor names to anvil internal names (inverse of
  `export_state_dict()` in `anvil/services/training/export.py`), serialize to a temp
  `model.json` file, then call `LlamaModel.load(temp_path)`.
- **Constraint (verified)**: `LlamaModel.load()` takes a **filesystem path string**, NOT a
  weights dict — there is no `from_weights_dict` factory. So the conversion must write a temp
  JSON file (matching `LlamaModel.save()`'s format) and load from it, OR a new
  `LlamaModel.from_weights_dict()` classmethod must be added (new implementation). The temp-file
  approach is the simpler, boring choice (Article XI).
- **Rationale**: The existing `SafetensorsExportService` already has the name mapping
  (anvil→HF) in `export_state_dict()`. The reverse mapping (HF→anvil) is simply the
  inverse. Since the merged model is a standard `LlamaForCausalLM`, all parameters
  (embed_tokens, q_proj, k_proj, v_proj, o_proj, gate/up/down, rms norms) have direct
  anvil equivalents.
- **Alternatives considered**: Keeping the model as a `PeftModel` and adding a parallel
  inference path — rejected (YAGNI, would require duplicating all inference methods).

## Existing Codebase Inventory

| Component | File | Status for 045 |
|-----------|------|----------------|
| ComputeResult | `anvil/services/compute/result.py` | Needs `adapter_id` field |
| AdapterMergeService | `anvil/services/training/merge_service.py` | Needs non-destructive + lineage |
| InferenceService.load_model() | `anvil/services/inference/inference.py` | Needs actual PeftModel composition |
| LoadedModel | `anvil/services/inference/loaded_model.py` | Already has `adapter_path` field |
| SafetensorsExportService | `anvil/services/training/export.py` | Reusable as-is for merged weights |
| LoRAAdapter ORM | `anvil/db/models/lora_adapter.py` | Reusable as-is |
| LoRAAdapterRepository | `anvil/db/repositories/lora_adapter_repository.py` | Reusable; may need `get_by_model_with_adapter_id()` |
| TrackingService | `anvil/services/tracking/tracking.py` | Reusable for lineage registration |
| LocalLoraBackend | `anvil/services/compute/local_lora_backend.py` | Already produces adapters (044) |
