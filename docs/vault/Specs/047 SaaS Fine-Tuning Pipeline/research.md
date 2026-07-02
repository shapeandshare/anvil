---
title: 047 SaaS Fine-Tuning Pipeline — Research
type: research
tags:
  - type/research
  - domain/training
  - domain/infrastructure
status: draft
created: '2026-07-02'
updated: '2026-07-02'
---

# Research: 047 SaaS Fine-Tuning Pipeline

## Overview

This document consolidates codebase research for extending the existing SaaS training pipeline (spec 032) to run PEFT fine-tunes on AWS Batch GPU. Three domains were explored: the SaaS training pipeline (032), the PEFT/LoRA engine (044), and LakeFS/asset storage (019/042).

---

## 1. Compute Backend Abstraction (032)

### Registry & Enums (already defined for 047)

| Enum | Value | File |
|------|-------|------|
| `ComputeBackend.SAAS` | `"saas"` | `anvil/services/compute/compute_backend.py` |
| `ComputeBackendResult.SAAS` | `"saas"` | `anvil/services/compute/compute_backend_result.py` |
| `RegistryBackend.SAAS_FINETUNE` | `"saas-finetune"` | `anvil/services/compute/registry_backend.py` |

### Protocol Interface

`ComputeBackendProtocol` (PEP 544 structural typing, not ABC):
- `name: str`
- `def is_available() -> bool`
- `async def run(docs, config, progress_callback, stop_check) -> ComputeResult`

### Registration Pattern

Backends auto-register at module import via `register(RegistryBackend.XXX, _factory)`. Example from `ModalBackend`:

```python
def _modal_factory() -> ModalBackend:
    return ModalBackend()
register(RegistryBackend.MODAL, _modal_factory)
```

### Resolution Flow

- `resolve_backend(config)` — non-LoRA methods
- `resolve_fine_tune(config)` — `method in ("lora", "qlora")` with memory-based routing
  - `AUTO`: local if fits host, SaaS if configured + over-local, else local
  - `SAAS`: SaaS if `_saas_configured()`, else raises `ComputeBackendUnavailable`
- **`_saas_configured()` currently returns `False`** — stub awaiting spec 047 implementation

### SSE / Metrics Streaming

- `TrainingService` creates `asyncio.Queue` per run via `reserve_run()`
- `_build_progress_callback()` enqueues events: `metrics`, `milestone`, `divergence`, `submitted`, `complete`, `error`
- `GET /training/stream/{run_id}` returns `StreamingResponse` with `text/event-stream`
- Spec 032 durable pattern: `job_events` table + `Last-Event-ID` replay

### Status Lifecycle

`ComputeStatus` StrEnum: `SUBMITTED → RUNNING → COMPLETED | FAILED`

Spec 047 clarifies a **5-state pipeline**: `pending → running → completing → completed | failed`

---

## 2. PEFT / LoRA Engine (044)

### LocalLoraBackend

The local LoRA/QLoRA implementation is in `anvil/services/compute/local_lora_backend.py`.

Key internals:
- `_run_real_lora()` — actual PEFT training loop (lines 146-351)
  - Loads base model via `transformers.AutoModelForCausalLM.from_pretrained()`
  - Applies LoRA via `peft.LoraConfig` + `get_peft_model()`
  - Runs training with `torch.optim.AdamW`
  - Saves adapter via `peft_model.save_pretrained()`
  - Returns `(adapter_path, final_loss, samples)`
- `_run_synthetic_lora()` — graceful degraded mode when PEFT packages unavailable
- Auto-registers as `RegistryBackend.LOCAL_LORA = "local-lora"`

Config keys consumed: `method`, `base_model_ref`, `lora_rank`, `lora_alpha`, `lora_target_modules`, `lora_dropout`, `lora_bias`, `device`, `num_steps`, `learning_rate`

### LoRAAdapter ORM Model

File: `anvil/db/models/lora_adapter.py`
- `external_model_id` (FK), `run_id`, `adapter_id`, `label`
- `method` (lora/qlora), `storage_path`, `final_loss`, `final_step`
- `lora_rank`, `lora_alpha`, `lora_target_modules`, `lora_dropout`, `lora_bias`
- `merged_at` (set after merge)

### AdapterMergeService

File: `anvil/services/training/merge_service.py`
- `merge(model_id, adapter_id)` → calls `PeftModel.merge_and_unload()`
- `merge_and_export(model_id, adapter_id)` → full pipeline: license check → merge → HF safetensors export → MLflow lineage → mark_merged()

### Fine-Tune Dependencies (`[finetune]` extra)

`transformers`, `peft`, `bitsandbytes`, `datasets`, `accelerate`, `huggingface_hub`, `tokenizers`, `sentencepiece`

---

## 3. Asset Storage & LakeFS (019/042)

### Current State: Local-Only

No LakeFS implementation exists yet. All storage uses `LocalFileStore`.

### FileStore Abstraction

`anvil/storage/interface.py` — `FileStore` ABC
- `get(path) → AsyncIterator[bytes]`
- `put(path, stream) → etag`
- `delete(path)`
- `list(prefix) → list[FileInfo]`

Local impl: `anvil/storage/local.py` — `LocalFileStore`

### VersionedContentStore Abstraction

`anvil/services/content/versioned_content_store.py` — `VersionedContentStore` ABC
- Session-based content ingestion (`open_session` → `stage` → `accept_session`)
- Version pinning via `freeze_version`
- Content-addressed blob storage (`open_blob(content_hash)`)
- **Future LakeFS mapping**: sessions→branches, accept→merge, version→commit/tag

Local impl: `anvil/services/content/local_versioned_content_store.py`
- Blobs at `data/content/blobs/<first2>/<sha256>`
- Staging at `data/content/staging/<slug>/<uuid>/`

### Model Asset Service

`anvil/services/model_import/model_asset_service.py`

- `submit_download(external_model_id) → job_id`
- `run_download(job_id)` — downloads via `HfHubSource`, verifies SHA-256
- Storage path: `models/{model_id}/assets/{sha256}/{filename}`
- `ModelAsset` ORM tracks per-file: `asset_type`, `filename`, `storage_path`, `sha256`, `size_bytes`, `status`

### External Model Registry

`anvil/db/models/external_model.py` — `ExternalModel`
- `source_type` (HUGGINGFACE/LOCAL), `source_identifier`, `asset_availability`
- Base models resolved via `HfHubSource` → HuggingFace Hub downloads

---

## 4. Reality Check (verified 2026-07-02)

A second, deeper verification pass against the actual `anvil/` source (not docs) found that
the assumed foundation is **absent**:

| Assumed dependency | Actual state in code |
|--------------------|----------------------|
| Spec 032 `ResourceSpec` class | **Does not exist** — only glossary string in `learning.py` |
| Spec 032 `job_events` table | **Does not exist** — no ORM model |
| AWS Batch dispatch (boto3, submit_job) | **Does not exist** |
| Usage metering / billback table | **Does not exist** — only glossary string |
| SaaS/Batch compute backend | **Does not exist** — only `RegistryBackend.SAAS_FINETUNE` enum value |
| `[saas]` extra (boto3/aioboto3) | **Does not exist** — extras are gpu/compute/vault-health/dev/finetune |
| LakeFS store | **Does not exist** — only `LocalVersionedContentStore`/`LocalFileStore` |
| Multi-tenancy / `org_id` | **Does not exist** — only OpenAPI glossary strings |
| LoRA adapter DB persistence | **Broken even locally** — `LoRAAdapterRepository.add()` has zero post-training callers; `ComputeResult.adapter_id` always `None` |

## 5. Decisions (MVP — Oracle-reviewed)

| Decision | Rationale | Alternatives Considered |
|----------|-----------|------------------------|
| Rescope 047 to a thin MVP; defer 032/LakeFS/tenancy | The assumed foundation doesn't exist; building it all = scope creep (violates YAGNI/Article XI) | Option A (halt for prereqs) — blocks useful progress; Option B (fold full infra) — huge scope creep |
| New minimal `SaasFinetuneProvider` seam (submit/poll/fetch) | Swappable + testable transport; real AWS Batch layers in later | Hard-coded transport — untestable, bakes in absent Batch |
| Follow `ModalBackend` submit-then-poll pattern | Proven remote-backend pattern already in the codebase | Inventing a new job framework — reinvention |
| Reuse `RegistryBackend.SAAS_FINETUNE` + `_saas_configured()` gate | Enum value + stub already exist | N/A |
| Fix adapter-persistence for BOTH local + SaaS inside 047 | Current correctness gap; prerequisite for a credible "tracked adapter" result | Separate spec — leaves 047's core deliverable unverifiable |
| Reuse `LoRAAdapter` ORM + existing `LocalFileStore` | No schema/dep changes; `storage_path` is generic | New tables / LakeFS now — premature |
| Fix training.py remap bug (LoRA remap only fires in LOCAL branch) | SaaS result never hits the remap → `get_backend("saas")` would fail | N/A — it's a bug |