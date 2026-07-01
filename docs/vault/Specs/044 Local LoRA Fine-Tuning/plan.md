# Implementation Plan: Local LoRA Fine-Tuning

**Branch**: `062-local-lora-fine-tuning` | **Date**: 2026-06-30 | **Spec**: `docs/vault/Specs/044 Local LoRA Fine-Tuning/spec.md`
**Input**: Feature specification from `docs/vault/Specs/044 Local LoRA Fine-Tuning/spec.md`

## Summary

Add local LoRA/QLoRA fine-tuning to anvil: a new `local-lora` compute backend that integrates with
the existing `ComputeBackendProtocol`, extends `TrainConfig` with a `method` enum (`lora`|`qlora`)
and LoRA-specific hyperparameters, and saves adapters as first-class artifacts alongside base models.
A new text-generation endpoint composes base + adapter via explicit `adapter_id` selection (the
existing inference API is educational-only). QLoRA degrades gracefully to LoRA on platforms where
`bitsandbytes` is unavailable. Supports both raw `.txt` corpora and structured instruction datasets
(selected by data-source ID, not a format column).

## Technical Context

**Language/Version**: Python 3.11+ (PEP 604, `StrEnum`, `from __future__ import annotations`)
**Primary Dependencies**: `peft`, `bitsandbytes`, `datasets`, `accelerate` — all NEW additions to the
`[finetune]` extra (which currently contains only `huggingface_hub`, `tokenizers`, `sentencepiece`,
`transformers`). Note: `torch` lives in the `[gpu]` extra, NOT `[finetune]` — the `local-lora` backend
requires BOTH `[finetune]` and `[gpu]` (or `[gpu]` composed into `[finetune]`). No new base-install deps.
**Storage**: `LocalFileStore` — adapters at `models/{base_model_id}/adapters/{run_id}/` using existing
`FileStore` abstraction. No new storage backends.
**Testing**: pytest (existing suite + new unit tests for `LocalLoraBackend`, adapter merge, QLoRA
degrade; NMRG regression test for unchanged from-scratch path)
**Target Platform**: Linux (CUDA), macOS (MPS/CPU)
**Project Type**: library + web-service (existing Python package, FastAPI, Jinja2)
**Performance Goals**: LoRA fine-tune TinyLlama-1.1B on consumer GPU (8GB VRAM) completes in
reasonable time. QLoRA fits in < 6GB VRAM.
**Constraints**: NMRG (from-scratch path untouched per Article I/IV/IX); `extra="forbid"` on
`TrainConfig` requires explicit field additions; all new deps behind `[finetune]`; adapter storage
reuses existing `FileStore` and `ModelAsset` patterns; **Article VII layering** — routes call
`AnvilWorkbench` god class (via `Depends(get_workbench)`), NOT services directly; the new generation
endpoint and adapter-aware `InferenceService.load_model()` must flow through the god class.
**Scale/Scope**: Curated small-model catalog (TinyLlama-class, 125M–1.1B params). Local-only in v1;
larger models route to SaaS (spec 046).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Simplicity First gate (Article XI — hard MUST)**:

- [x] **Simplest viable** (§11.1) — LoRA/QLoRA via `peft` is the standard, most widely-used PEFT
      approach. The `ComputeBackendProtocol` integration reuses the existing job lifecycle, SSE
      streaming, and result type — no new orchestration.
- [x] **Boring over novel** (§11.2) — `peft` and `bitsandbytes` are mature, widely-adopted libraries
      (HuggingFace ecosystem). No experimental or novel frameworks introduced.
- [x] **YAGNI** (§11.3) — `method` enum serves present LoRA/QLoRA needs; future methods (prompt-
      tuning, full fine-tune) can add enum values when concretely needed. Dual dataset format
      serves two present use cases (ad-hoc .txt + instruction-tuning), validated in clarification.
- [x] **Reuse first** (§11.4) — Entire feature reuses: `ComputeBackendProtocol`, `ComputeResult`,
      `TrainingService`, `TrainConfig` (extended, not replaced), `FileStore`, `LocalFileStore`,
      `ModelAsset`/repository pattern, `TimestampMixin`, `AnvilWorkbench` god class, SSE event types,
      `StepMetrics`, `training.html` param-block pattern, `resolve_backend()` two-layer enum model.
      NOTE: a new text-generation endpoint IS new work (no existing generation route to reuse — the
      inference API is educational-only). This is justified: without it, a fine-tuned model cannot be
      exercised, which is the point of the feature.
- [x] **Testable** (§11.6) — All paths are testable via existing pytest infrastructure: submit
      LoRA job via API with mock backend, verify adapter artifact, verify inference composition,
      verify NMRG gate (from-scratch path reports unchanged results), verify QLoRA degrade.

> ✅ Gate passes. No complexity tracking entries required — all complexity is justified by concrete
> present requirements.

## Project Structure

### Documentation (this feature)

```text
docs/vault/Specs/044 Local LoRA Fine-Tuning/
├── spec.md              # Feature specification (with clarifications)
├── plan.md              # This file
├── research.md          # Phase 0 — technology research
├── data-model.md        # Phase 1 — entity/field design
├── quickstart.md        # Phase 1 — usage guide
├── contracts/           # Phase 1 — API contracts
│   └── api-contract.md  #   TrainConfig extension, inference contract
└── tasks.md             # Phase 2 — (/speckit.tasks command output)
```

### Source Code (repository root)

```text
anvil/
├── services/
│   ├── compute/
│   │   ├── registry_backend.py    # + LOCAL_LORA = "local-lora" enum member
│   │   ├── local_lora_backend.py  # NEW — ComputeBackendProtocol impl (NEW FILE)
│   │   ├── compute_backend.py     # + LOCAL_LORA user-facing enum member (see resolve note)
│   │   ├── resolve.py             # + route method=lora/qlora → local-lora
│   │   └── registry.py            # + auto-registration side-effect
│   ├── inference/
│   │   ├── inference.py           # + adapter-aware load_model() (base + adapter composition)
│   │   ├── loaded_model.py        # + optional adapter reference
│   │   ├── resource_envelope.py   # + default_target_modules field
│   │   └── model_browser.py       # (reads catalog — no change if envelope model extended)
│   ├── training/
│   │   ├── training.py            # + FineTuneSpec validation + dual dataset loading
│   │   └── merge_service.py       # NEW — adapter merge (or method on backend)
│   └── model_import/
│       └── model_asset_service.py # (adapter storage path pattern reference)
├── api/
│   ├── v1/
│   │   ├── training.py            # + method + lora_* fields on TrainConfig (NOT TrainingConfig)
│   │   ├── inference.py           # + NEW generation route (educational-only today)
│   │   └── adapters.py            # NEW — adapter list + merge endpoints (or extend registry.py)
│   └── templates/archetypes/
│       ├── training.html          # + LoRA param-blocks + inline JS (startTraining() is inline)
│       └── model_detail.html      # + Merge Adapter button
├── db/
│   ├── models/
│   │   ├── model_asset.py         # + ADAPTER asset type OR new lora_adapter.py model
│   │   └── lora_adapter.py        # NEW (if separate model chosen) — LoRAAdapter ORM
│   └── repositories/
│       └── lora_adapter_repository.py  # NEW (if separate model) — async CRUD
├── data/
│   └── curated-models.yaml        # + default_target_modules per entry
├── _resources/migrations/versions/
│   └── 0XX_add_lora_adapters.py   # NEW — Alembic migration (make db-revision)
├── workbench.py                   # + lora_adapter_repo / generation service properties
└── storage/local.py               # No changes — reuse existing FileStore

pyproject.toml                     # + peft, bitsandbytes, datasets, accelerate to [finetune]

tests/
├── unit/
│   └── services/
│       └── compute/
│           └── test_local_lora_backend.py  # NEW (dir tests/unit/services/compute/ exists)
└── e2e/
    ├── api/
    │   ├── test_training_router.py         # + LoRA fine-tune API tests (existing file)
    │   └── test_inference_api.py           # + generation endpoint tests (existing file)
    └── test_nmrg_044.py                    # NEW — NMRG regression (mirror test_nmrg_040.py)
```

**Structure Decision**: Single project (existing Python package). All new code follows existing
domain-driven package decomposition (Constitution Article X) and layered architecture (Article VII —
routes call `AnvilWorkbench`, services call repositories). The `LocalLoraBackend` lives in
`anvil/services/compute/` alongside its peers (`local_torch_backend.py`, `local_stdlib_backend.py`,
`modal_backend.py`). Adapter tracking uses either a new `ModelAssetType.ADAPTER` member OR a dedicated
`LoRAAdapter` ORM model in `anvil/db/models/lora_adapter.py` with a matching repository (decided in
data-model.md — dedicated model chosen for the richer field set: rank, alpha, method, merged_at).
A new Alembic migration is required (`make db-revision MESSAGE="add lora adapters"`).

## Complexity Tracking

> All deviation from the simplest viable solution is recorded here per §11.5.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| New text-generation endpoint | A fine-tuned model must be runnable to have value; the existing inference API is educational-only with no generation route | Reusing an existing endpoint — rejected because none exists; the educational endpoints (tokenize/attention/etc.) do not generate text |
| Dedicated `LoRAAdapter` ORM model (vs. reusing `ModelAsset`) | Adapters carry a rich, adapter-specific field set (rank, alpha, target_modules, dropout, bias, method, final_loss, merged_at) that does not fit `ModelAsset`'s file-oriented columns | Extending `ModelAssetType` with `ADAPTER` — rejected because it would overload `ModelAsset` (a per-file record) with training-run semantics, mixing two bounded contexts (Article X §10.2) |

## Phase 0 — Research

See `research.md` for detailed findings on:
- `peft.LoraConfig` integration patterns for the target architectures
- `bitsandbytes` 4-bit NF4 quantization setup and platform compatibility
- Adapter storage layout (co-located with base model assets)
- Dual dataset format loading (raw `.txt` vs HF `datasets.Dataset`)