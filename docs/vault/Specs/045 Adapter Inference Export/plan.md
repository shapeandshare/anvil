# Implementation Plan: Adapter Inference, Merge & Export

**Branch**: `045-adapter-inference-export` | **Date**: 2026-07-01 | **Spec**: [045 Adapter Inference Export - spec.md](045%20Adapter%20Inference%20Export%20-%20spec.md)
**Input**: Feature specification from `docs/vault/Specs/045 Adapter Inference Export/045 Adapter Inference Export - spec.md`

## Summary

Close the loop on external fine-tuning: represent a LoRA adapter as a first-class result shape in `ComputeResult`, run inference by composing base + adapter at load time, and support optional merge+export of an adapter into standalone weights with MLflow lineage registration.

The codebase already has infrastructure from spec 044: `LoRAAdapter` ORM model, `LoRAAdapterRepository`, `AdapterMergeService` (merge is implemented but destructive), and `InferenceService.load_model()` already accepts an `adapter_id` parameter (composition not yet implemented). This spec makes adapter inference work end-to-end, makes merge non-destructive + lineage-aware, and integrates merge+export through the existing safetensors pipeline.

## Technical Context

**Language/Version**: Python 3.11+ (`from __future__ import annotations`, PEP 604, `StrEnum`)  
**Primary Dependencies**: FastAPI, async SQLAlchemy, `safetensors`, `numpy` (existing); `peft`, `transformers`, `torch` (behind `[finetune]` extra — same as 044)  
**Storage**: `LocalFileStore` at `data/models/{base_model_id}/adapters/{adapter_id}/` (existing 044 layout); merged artifacts at `data/models/{base_model_id}/merged/{adapter_id}/`  
**Testing**: `pytest`, `pytest-asyncio`, `httpx.AsyncClient` (existing project conventions)  
**Target Platform**: Linux/macOS server (existing)  
**Project Type**: Python package (web service, `pip install anvil`)  
**Performance Goals**: No hard latency target for v1; merge+export expected to complete within seconds for TinyLlama-class models on CPU  
**Constraints**: Adapter must persist after merge (non-destructive); atomic failure on merge+export — no partial artifact; NMRG for base install (no new top-level deps)  
**Scale/Scope**: 1 adapter per fine-tune run; multiple adapters per base model distinguished by the existing scoped key `(external_model_id, adapter_id)` on the `LoRAAdapter` ORM (no separate `version` column)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Simplicity First gate (Article XI — hard MUST)**: Confirm this plan favors the simplest, most boring solution that meets the requirement:

- [x] **Simplest viable** (§11.1) — reuse existing `AdapterMergeService`, `SafetensorsExportService`, and `InferenceService.load_model()` rather than building new infrastructure. No new services, no new repositories.
- [x] **Boring over novel** (§11.2) — all dependencies (`peft`, `safetensors`, `mlflow`) are already committed from spec 044. No new deps.
- [x] **YAGNI** (§11.3) — no speculative API for batch adapter inference, no adapter diff engine, no scheduler for async merge jobs. Everything in this plan maps directly to spec requirements FR-020, FR-021, FR-021a.
- [x] **Reuse first** (§11.4) — `AdapterMergeService.merge()`, the `/v1/inference/generate` endpoint, the adapter REST routes, `InferenceGenerateBody`, `LoadedModel.adapter_path`, `SafetensorsExportService`, and `TrackingService.register_source_model()`/`set_tag()` all exist and are reused. Changes: make merge non-destructive, add `merge_and_export()`, inject `TrackingService` into `AdapterMergeService` (one new dependency wiring, not a new service), and implement adapter composition in `load_model()` (currently a no-op that only stores the path).
- [x] **Testable** (§11.6) — each feature has a clear acceptance scenario (US spec). Adapter inference tests load model + adapter, compose, generate. Merge+export tests verify standalone artifact + lineage. Testable without GPU (CPU-only for TinyLlama-class models).

> No deviations from the simplest viable solution. Complexity Tracking table is empty.

## Project Structure

### Documentation (this feature)

```text
docs/vault/Specs/045 Adapter Inference Export/
├── 045 Adapter Inference Export - spec.md   # Feature specification
├── plan.md                                   # This file (/speckit.plan command output)
├── research.md                               # Phase 0 output (/speckit.plan command)
├── data-model.md                             # Phase 1 output (/speckit.plan command)
├── quickstart.md                             # Phase 1 output (/speckit.plan command)
├── contracts/                                # Phase 1 output (/speckit.plan command)
│   └── api-contract.md
└── tasks.md                                  # Phase 2 output (/speckit.tasks command)
```

### Source Code (repository root)

The feature modifies existing files — no new source modules needed for the core logic. Changes are concentrated in:

```text
# MODIFIED FILES (existing — all verified present 2026-07-01)
anvil/services/compute/result.py              # ComputeResult adapter shape (add adapter_id field)
anvil/services/training/merge_service.py      # Non-destructive merge + merge_and_export() + TrackingService dep
anvil/services/inference/inference.py         # Compose base+adapter in load_model() (currently only stores path); generate() must use composed model
anvil/db/repositories/lora_adapter_repository.py  # No change expected; get_by_adapter_id() already exists
anvil/workbench.py                            # Expose AdapterMergeService as lazy property (currently instantiated inline in route)
anvil/api/v1/adapters.py                      # Update inline AdapterMergeService instantiation to use workbench property

# REUSED AS-IS (no change)
anvil/api/v1/inference.py                     # /inference/generate endpoint ALREADY EXISTS (line 362)
anvil/api/v1/inference_schemas.py             # InferenceGenerateBody ALREADY EXISTS (with adapter_id)
anvil/services/inference/loaded_model.py      # adapter_path field ALREADY EXISTS
anvil/services/training/export.py             # SafetensorsExportService reused for merged weights
anvil/services/tracking/tracking.py           # register_source_model() + set_tag() reused for lineage

tests/unit/services/compute/                  # ComputeResult adapter shape tests
tests/unit/services/inference/                # Adapter inference composition tests
tests/unit/services/training/                 # Merge+export tests
tests/e2e/                                    # End-to-end inference + merge tests
```

**Structure Decision**: Single Python package — this is an additive change to the existing `anvil` namespace package. No new source modules or endpoints are created; the generation endpoint and adapter REST routes already exist from spec 044. One structural change: `AdapterMergeService` gains a `TrackingService` dependency and is promoted from inline-in-route instantiation to an `AnvilWorkbench` lazy property (Article VII layering).

## Complexity Tracking

> **Empty** — Constitution Check has no violations. All changes reuse existing infrastructure.