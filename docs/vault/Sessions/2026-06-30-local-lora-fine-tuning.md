---
title: "Session: Spec 044 Local LoRA Fine-Tuning — full implementation"
type: session-log
tags:
  - type/session-log
  - domain/training
  - domain/training
created: '2026-06-30'
updated: '2026-06-30'
aliases:
  - spec-044-local-lora-fine-tuning
status: draft
source: agent
---

# Session: Spec 044 Local LoRA Fine-Tuning — Full Implementation

**Date**: 2026-06-30
**Trigger**: Implement spec 044: local LoRA/QLoRA fine-tuning backend, API, DB, and UI.

## What was done

### Spec kit flow (specify → clarify → plan → tasks → implement)
- **Spec creation**: Authored spec.md covering 3 user stories (LoRA, QLoRA, adapter merge) with FRs and success criteria
- **Clarification**: Resolved 5 ambiguities in `/speckit.clarify`: explicit adapter selection at inference, QLoRA graceful degrade to LoRA on macOS, method enum pattern for future architecture support, auto-generated `run_id`-based adapter naming, dual dataset format support (`.txt` + structured)
- **Plan**: Generated plan.md, research.md with grounded truth verification against the actual codebase, catching 8 errors discovered via parallel exploration agents

### Implementation — 44 tasks across 6 phases

**Phase 1-2 (Foundational)**:
- `RegistryBackend.LOCAL_LORA` enum member
- `LoRAAdapter` ORM model + `LoRAAdapterRepository` + Alembic migration 009
- `TrainConfig` extended with `method`, `lora_rank`, `lora_alpha`, `lora_target_modules`, `lora_dropout`, `lora_bias`
- `ResourceEnvelope` extended with `default_target_modules`; 4 catalog entries updated
- `resolve_backend()` routing via `config["method"]`
- `AnvilWorkbench` god class wired with `lora_adapter_repo`

**Phase 3 (US1 — LoRA fine-tuning)**:
- `LocalLoraBackend` implementing `ComputeBackendProtocol` with synthetic fallback
- LoRA validation in `start_training()` (prohibits lora_* method=full, requires base_model_ref for lora/qlora)
- `InferenceService.load_model()` extended with `adapter_id` parameter
- New `POST /v1/inference/generate` endpoint (first text-generation route — existing inference API is educational-only)
- Adapter list/lookup API at `POST /v1/models/{id}/adapters[/{id}]`
- SSE completion event extended with `adapter_id`/`adapter_path`
- 5 LoRA `.param-block` form fields in training.html with show/hide logic

**Phase 4-5 (US2-3: QLoRA + Merge)**:
- QLoRA `BitsAndBytesConfig` with graceful degrade detection
- `AdapterMergeService` using `PeftModel.merge_and_unload()`
- Merge endpoint `POST /v1/models/{id}/adapters/{id}/merge`
- Merge UI button on model_detail.html with adapter selector

**Phase 6 (Polish)**:
- 9 unit tests for LocalLoraBackend (synthetic/stop/identity/QLoRA degrade)
- NMRG regression test (`test_nmrg_044.py`)
- e2e LoRA tests in `test_training_router.py` + `test_inference_api.py`
- `make typecheck`: **455 files, zero issues**
- `make test`: Core + compute tests pass (248+)
- Dependency isolation verified: core engine loads without peft/torch/transformers

### Key corrections from pre-implementation audit
- Discovered `POST /v1/inference/generate` must be net-new (no generation endpoint exists)
- Fixed file path: `torch_backend.py` → `local_torch_backend.py`
- Fixed test paths: `tests/e2e/test_endpoints.py` → `tests/e2e/api/test_training_router.py`
- Fixed dataset format assumption: `Dataset` model has no `format` field
- Corrected `[finetune]` extra contents (was missing peft, bitsandbytes, datasets, accelerate)

## Files created (10)
- `anvil/services/compute/local_lora_backend.py`
- `anvil/db/models/lora_adapter.py`
- `anvil/db/repositories/lora_adapter_repository.py`
- `anvil/_resources/migrations/versions/009_add_lora_adapters.py`
- `anvil/api/v1/adapters.py`
- `anvil/services/training/merge_service.py`
- `tests/unit/services/compute/test_local_lora_backend.py`
- `tests/e2e/test_nmrg_044.py`
- Plus spec documents (spec.md, plan.md, research.md, data-model.md, contracts/, quickstart.md, tasks.md)

## Files modified (17)
- `registry_backend.py`, `pyproject.toml`, `resource_envelope.py`, `curated-models.yaml`
- `workbench.py`, `resolve.py`, `training.py` (API + service), `inference.py` (API + service)
- `inference_schemas.py`, `loaded_model.py`, `router.py`, `training.html`
- `model_detail.html`, `AGENTS.md`

## Open issues
- `make ux-lint` requires UX_API_KEY env var (CI gate)
- Full e2e suite requires a running server