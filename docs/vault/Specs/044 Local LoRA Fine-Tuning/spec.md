---
title: 044 Local LoRA Fine-Tuning - spec
type: spec
tags:
  - type/spec
  - domain/training
  - domain/fine-tuning
status: draft
spec-refs:
  - docs/vault/Specs/044 Local LoRA Fine-Tuning/
related:
  - '[[044 Local LoRA Fine-Tuning]]'
  - '[[038 Fine-Tuning Arc]]'
  - '[[043 Subword Tokenizer Abstraction]]'
  - '[[Reference/FineTuningArchitectureDecisions]]'
created: '2026-06-30'
updated: '2026-06-30'  # +5 clarification items; +pre-implementation verification pass (corrected file paths, FR-020a generation endpoint, dataset source model, finetune extra deps)
---

# Feature Specification: Local LoRA Fine-Tuning

**Feature Branch**: `062-local-lora-fine-tuning`
**Created**: 2026-06-30
**Status**: Draft
**Parent Spec**: [[Specs/038 Fine-Tuning Arc/038 Fine-Tuning Arc|038 Fine-Tuning Arc (umbrella)]]

## Overview

Add local LoRA/QLoRA fine-tuning to anvil: the ability to fine-tune a small pretrained HuggingFace
model (e.g. TinyLlama) using low-rank adaptation, all running on local hardware. This is the
**External PEFT** mode from FT-AD-1 — the user imports a model via 040/041, selects LoRA
hyperparameters, and the training backend applies `peft` to train adapter weights while keeping the
base model frozen.

### Scope

| Dimension | Scope |
|-----------|-------|
| **Owned FRs** | FR-016, FR-017, FR-018 (LoRA/QLoRA fine-tuning) |
| **Owned decisions** | FT-AD-1 (external PEFT mode), FT-AD-7 (adapter-aware results), FT-AD-8 (curated catalog) |
| **Depends on** | `043 Subword Tokenizer Abstraction` (tokenizer seam); `040 External Model Import` / `041 HF Model Browser` (model source); `042 Model Asset Storage` (asset management); `torch`, `transformers`, `peft`, `datasets` (behind `[finetune]` extra) |
| **Invariant risk** | **HIGH** — introduces a new fine-tuning backend that must not regress the from-scratch pretraining path; dependency isolation must be proven per NMRG |

---

## User Stories

### US1 — Locally Fine-Tune an Imported HF Model with LoRA (Priority: P1)

A user who has imported a TinyLlama-class model can configure and run a local LoRA fine-tuning job
from the training UI/API, selecting target modules, rank, and LoRA-specific hyperparams, and watch
the loss curve stream in real time. The result is a LoRA adapter saved alongside the base model.
The system accepts both raw `.txt` corpora (auto-chunked per-document for training) and structured
instruction/conversation datasets; the data source is chosen by which existing selector is populated
(`corpus_id`, `dataset_id`, or a structured `FineTuneDataset` reference), not by a format column.

**Independent Test**: Submit a LoRA fine-tune job for a TinyLlama model via the API with known
parameters; verify the job completes, a LoRA adapter artifact is produced, and inference using
base+adapter produces different output than the base model alone.

**Acceptance Scenarios**:

1. **Given** an imported TinyLlama model in the registry and a `.txt` corpus uploaded, **When** the user starts a LoRA fine-tuning job from the training page with target modules, rank `r=8`, and selects the corpus, **Then** the job runs to completion, the loss curve updates over SSE, and a LoRA adapter is saved in the model's storage path.
2. **Given** an imported TinyLlama model in the registry and a structured instruction/conversation dataset (a `FineTuneDataset`), **When** the user starts a LoRA fine-tuning job selecting that dataset, **Then** the structured loading path is used, producing the same adapter artifact.
3. **Given** a completed LoRA fine-tune producing adapter `A1`, **When** the user runs inference on the base model with `adapter_id="A1"`, **Then** inference composes base weights + adapter `A1` at load time, and output reflects the fine-tune.
4. **Given** a base model with multiple adapters, **When** the user runs inference without specifying `adapter_id`, **Then** inference falls back to base-only (no adapter applied).
5. **Given** a LoRA fine-tune job, **When** the user cancels mid-run, **Then** partial adapter
   checkpoints are available (matching the existing checkpointing behavior).

---

### US2 — Locally Fine-Tune with QLoRA (Priority: P2)

A user with constrained GPU memory can fine-tune using QLoRA (4-bit quantization of the base model)
to fit larger models or batch sizes on their hardware.

**Independent Test**: Submit a QLoRA job with `bits=4` for the same model as US1; verify it runs
within lower peak memory than US1 and produces a LoRA adapter compatible with the same inference
path.

**Acceptance Scenarios**:

1. **Given** an imported model and a user on a GPU with limited VRAM, **When** the user selects
   QLoRA with 4-bit NF4 quantization, **Then** the fine-tune runs without OOM and the peak memory
   is measurably lower than LoRA at the same batch size.
2. **Given** a QLoRA fine-tune completes, **When** the adapter is loaded for inference, **Then**
   the adapter merges cleanly with the (now dequantized) base model and produces valid output.

---

### US3 — Optional Adapter Merge (Priority: P3)

After fine-tuning, a user can optionally merge the LoRA adapter into the base model weights,
producing a standalone model artifact (no adapter dependency at inference time).

**Independent Test**: Merge a LoRA adapter into its base model; verify the merged artifact loads
and infers without the adapter present, and output matches base+adapter composition (within
numerical precision).

**Acceptance Scenarios**:

1. **Given** a LoRA adapter exists for a base model, **When** the user requests a merge, **Then**
   a new model artifact is created with merged weights and no adapter metadata.
2. **Given** a merged model, **When** inference runs, **Then** it loads as a standalone model
   without requiring the adapter file.

---

### Edge Cases

- No GPU available → fine-tune on CPU (slow but functional); warn user about expected duration.
- `peft` not installed (`[finetune]` extra missing) → raise `ComputeBackendUnavailable` with
  clear "install `anvil[finetune]`" message.
- Model not in the curated small-model catalog → fine-tune is blocked for local; route to SaaS
  (FT-AD-8).
- Tokenizer not attached to model (dependency on 043) → reject before job submission.
- Adapter merge numerical divergence → test base+adapter composition vs merged weight output;
  document tolerance.
- Inference with unknown/nonexistent `adapter_id` → return 404 with descriptive message listing available adapter IDs for that base model.
- QLoRA requested on unsupported platform → graceful degrade to LoRA with warning banner (see FR-017).
- No data source selected (none of `corpus_id`/`dataset_id`/`fine_tune_dataset_id` populated), or an unsupported/empty dataset → reject with descriptive message listing supported sources (`.txt` corpus, prepared dataset, structured `FineTuneDataset`).

## Requirements

- **FR-016**: The system MUST support LoRA fine-tuning (`peft.LoraConfig`) for imported HF models
  in the curated small-model catalog, running on the local `local-torch` compute backend. The existing
  `TrainConfig` MUST be extended with a `method` field (`"full"` | `"lora"` | `"qlora"`, default `"full"`)
  that selects the training method. When `method="full"` or absent, existing from-scratch behavior is
  unchanged.
- **FR-016a**: When `method` is `"lora"` or `"qlora"`, the following LoRA-specific fields MUST be
  configurable on `TrainConfig`: `lora_rank`, `lora_alpha`, `lora_target_modules`, `lora_dropout`,
  and `lora_bias` (FT-AD-7). Per-architecture default target modules MUST be defined in the curated
  catalog, not hardcoded in the API or backend.
- **FR-016b**: LoRA fine-tuning MUST produce a LoRA adapter artifact (`peft.PeftModel.get_adapter_state_dict()`)
  saved alongside the base model in the existing `FileStore` storage layout.
- **FR-017**: The system MUST support QLoRA (4-bit NF4 quantization via `bitsandbytes`) as a LoRA
  variant, gated on GPU availability and `bitsandbytes` being installed. On platforms where
  `bitsandbytes` is unavailable (e.g. macOS MPS), the system MUST gracefully degrade to regular LoRA,
  logging a warning and displaying a banner: "QLoRA not available on this platform; falling back to LoRA."
- **FR-018**: The system MUST support optional adapter merge, producing a standalone merged model
  artifact (deleted adapter files). This is a separate, explicit operation — NOT automatic after
  fine-tuning (FT-AD-7).
- **FR-019**: The fine-tuning job lifecycle MUST follow the existing `ComputeBackendProtocol`
  (submit → poll → result), with SSE progress streaming from the job's event callbacks
  (FT-AD-6).
- **FR-020**: Inference MUST compose base model weights + LoRA adapter at load time when `adapter_id` is specified on the generation request, and MUST fall back to base-only inference when no `adapter_id` is provided (FT-AD-7). The `adapter_id` field is an explicit, user-supplied parameter — no auto-detection, no implicit "latest adapter" heuristic.
- **FR-020a**: A text-generation endpoint MUST be introduced to exercise a fine-tuned model. The existing inference API (`anvil/api/v1/inference.py`) is educational-only and has no generation route. This spec owns the new generation endpoint that accepts `model_id` + optional `adapter_id` + `prompt` and returns generated text. `InferenceService.load_model()` MUST be extended to load a base model + LoRA adapter composition.
- **FR-021**: The curated small-model catalog (FT-AD-8) MUST document per-model: parameter count,
  minimum RAM/VRAM, and supported fine-tuning methods (LoRA only, or QLoRA too).
- **FR-022 (NMRG)**: The from-scratch pretraining path MUST be untouched — a training run with no
  `base_model_ref` is identical to today. The NMRG gate (spec 038) MUST pass.
- **FR-023**: LoRA fine-tuning MUST accept both raw `.txt` corpora (auto-chunked per-document) and
  structured instruction/conversation datasets. The data source MUST be selected by which existing
  identifier is populated (`corpus_id`, `dataset_id`, or a structured `FineTuneDataset` reference) —
  there is no `format` column on the `Dataset` model to key off. User-facing documentation MUST explain
  both paths and their use cases (ad-hoc vs. instruction-tuning).

### Key Entities

- **LoRA Adapter**: a small set of low-rank weight deltas produced by fine-tuning, stored alongside
  the base model. Each adapter has a unique `adapter_id` (auto-generated from the run ID, e.g.
  `run_42`), scoped to the base model. Users may optionally assign a human-readable label for UI
  display. Explicitly selected at inference time via `adapter_id`. Optionally mergeable into base weights.
- **FineTuneSpec**: configuration for a fine-tuning job expressed via `TrainConfig` fields — `method`
  (`"full"` | `"lora"` | `"qlora"`), `lora_rank`, `lora_alpha`, `lora_target_modules`, `lora_dropout`,
  `lora_bias`. LoRA-specific hyperparams are architecture-agnostic; per-architecture default target
  modules live in the curated catalog.
- **Curated Catalog**: the allow-list of models eligible for local fine-tuning (FT-AD-8).
  TinyLlama-class models with known resource envelopes.

## Success Criteria

- **SC-001**: LoRA fine-tune completes for a TinyLlama model via the API; adapter artifact exists.
- **SC-002**: QLoRA fine-tune runs within lower peak memory than LoRA at equivalent batch size.
- **SC-003**: Adapter merge produces a standalone model; base+adapter composition and merged weights
  produce equivalent output (within 1e-5 numerical tolerance).
- **SC-004 (NMRG)**: `make test` passes; `make typecheck` is clean; `pip install anvil` pulls no
  `torch`/`transformers`/`peft`/`bitsandbytes`; from-scratch training works end-to-end.
- **SC-005**: The curated catalog documents supported fine-tuning methods and resource envelopes
  for at least 3 models.

## Clarifications

### Session 2026-06-30

- Q: How does inference select which LoRA adapter to use? → A: Explicit adapter selection — user picks which adapter via an `adapter_id` field on the inference request; no auto-detection, no implicit "latest" heuristic. Supports multiple adapters per base model.
- Q: What happens when QLoRA is requested on a platform where `bitsandbytes` is unavailable (macOS MPS)? → A: Graceful degrade — attempt QLoRA; if `bitsandbytes` is unavailable, log a warning and automatically fall back to regular LoRA on the same model. User sees a banner: "QLoRA not available on this platform; falling back to LoRA."
- Q: How should the FineTuneSpec relate to the existing `TrainConfig`, considering future support for other architectures? → A: Method enum — add a `method: str = "full" | "lora" | "qlora"` field on `TrainConfig`. When method is `lora`/`qlora`, LoRA-specific fields (`lora_rank`, `lora_alpha`, `lora_target_modules`, `lora_dropout`) are validated. When method is `"full"` (the default when absent), existing from-scratch behavior is unchanged. LoRA hyperparams are architecture-agnostic — per-architecture default target modules live in `curated-models.yaml`, not the API schema.
- Q: What is the adapter naming scheme when a user fine-tunes the same base model multiple times? → A: Auto-generated `run_id`-based adapter_id (e.g. `run_42`). User can optionally provide a human-readable label for display in the UI. Inference uses the deterministic `adapter_id`.
- Q: What dataset formats should LoRA fine-tuning accept? → A: Both `.txt` corpora (auto-chunked into training examples) AND structured instruction/conversation datasets. The data source is determined by which existing selector is populated — `corpus_id` (raw `.txt`), `dataset_id` (prepared dataset), or a `FineTuneDataset` reference (structured instruction-tuning, spec 053) — NOT by a `format` column (the `Dataset` model has no such field). `.txt` enables quick ad-hoc fine-tuning; structured datasets unlock instruction-tuning. This context MUST be included in any user-facing documentation so users understand which format suits their use case.

## Assumptions

- Spec 043 (Tokenizer Abstraction) is complete before 044 implementation begins.
- Spec 040/041 (Model Import/Browser) is complete — imported models exist in the registry with
  attached tokenizers.
- The `local-torch` compute backend (`anvil/services/compute/local_torch_backend.py`) exists and is
  the reference pattern for the new `local-lora` backend.
- **There is no existing text-generation inference endpoint** — the inference API
  (`anvil/api/v1/inference.py`) is educational/visualization-only (tokenize, embeddings, attention,
  etc.). A generation endpoint that composes base+adapter is NEW work owned by this spec (see FR-020a).
- LoRA adapters are stored flat alongside base model files in the existing `LocalFileStore` layout;
  no new storage abstractions needed for v1.
- The `[finetune]` extras group includes `torch`, `transformers`, `peft`, `datasets`,
  `bitsandbytes` (for QLoRA), and `accelerate`.

## Rejected Alternatives

1. **Full fine-tuning (all weights) for local models** — Rejected because it requires
   O(pretraining) memory and compute, which is infeasible on consumer hardware for even
   TinyLlama-class models. LoRA/QLoRA is the pragmatic local path; full fine-tuning belongs on SaaS
   (spec 046).
2. **Prompt-tuning / prefix-tuning variants** — Rejected for v1 because LoRA is the most widely
   adopted and best-tooled PEFT method in the `peft` ecosystem. Other PEFT methods may be added
   later (tracking issue, not v1 commitment).
3. **Automatic adapter merge on job completion** — Rejected per FT-AD-7. The adapter is the
   primary artifact; merge is an explicit, user-initiated operation to keep the adapter-as-deliverable
   paradigm clear.