---
title: 038 Fine-Tuning Arc - spec
type: spec
tags:
  - type/spec
  - domain/training
  - domain/learning
status: draft
spec-refs:
  - docs/vault/Specs/038 Fine-Tuning Arc/
related:
  - '[[038 Fine-Tuning Arc]]'
  - '[[Reference/FineTuningArchitectureDecisions]]'
created: '2026-06-28'
updated: '2026-06-28'
---

# Feature Specification: Fine-Tuning Arc — From Pretraining to Specializing Real Models

**Feature Branch**: `038-fine-tuning-arc`
**Created**: 2026-06-28
**Status**: Draft

## Overview

anvil today teaches how language models work by letting a learner train a small char-level model
**from scratch** and watch it learn. The Fine-Tuning Arc extends that ladder with the next conceptual
rung: **specializing existing models**. It introduces two tracks behind one compute seam — continuing
training of anvil's *own* models (native warm-start), and parameter-efficient fine-tuning of *external*
pretrained models from HuggingFace (LoRA/QLoRA on TinyLlama-class models) — runnable locally and
offloadable to SaaS for larger workloads.

This is an **umbrella spec**. It frames the epic and owns the cross-cutting requirements; it is
decomposed into independently shippable per-feature specs **039–049** (see
`038 Fine-Tuning Arc - shippable-features.md`). The binding architecture decisions live in
[[Reference/FineTuningArchitectureDecisions|Fine-Tuning Architecture Decisions (FT-AD-1..10)]].

**Governing invariant** — *the existing from-scratch pretraining experience and the dependency-free
base install never change.* Every child feature carries the Native-Mode Regression Gate (NMRG). See
FT-AD-2 and the Requirements → Invariants group below.

## User Scenarios & Testing

### User Story 1 — Learner Specializes a Model They Already Trained (Priority: P1)

A learner who has trained a char-level model from scratch selects that checkpoint as a starting point
and continues training it on a new, narrower corpus, watching it specialize in real time. No external
models, no new heavy dependencies.

**Why this priority**: This is the smallest viable slice of "fine-tuning" and the natural first
conceptual step (warm-start = continued training). It reuses the entire existing stack — the engine
already supports `train(docs, model=...)` — so it ships value immediately and teaches the core idea
before any external-model complexity.

**Independent Test**: Train a model from scratch (existing flow), register it, then start a new run
with that model as `base_model_ref` on a different small corpus. Verify the run warm-starts (loss
begins below a from-scratch run) and that lineage links the new model to its parent.

**Acceptance Scenarios**:

1. **Given** a registered anvil checkpoint, **When** the learner starts a run selecting it as the base
   model, **Then** training resumes from those weights rather than random init, and live metrics stream
   as usual.
2. **Given** a fine-tune run completes, **When** the learner views the model registry, **Then** the new
   model records its parent `base_model_ref` (lineage) and the corpus it was specialized on.
3. **Given** no base model is selected, **When** the learner starts a run, **Then** behavior is exactly
   today's from-scratch pretraining (the invariant).

---

### User Story 2 — Learner Imports an External Model from HuggingFace (Priority: P1)

A learner opens an in-app HuggingFace view, browses a curated set of very small models (TinyLlama and
peers), inspects a model's card/metadata, and imports it — creating a tracked metadata entry in
anvil's registry without yet downloading gigabytes of weights.

**Why this priority**: External fine-tuning is the path most learners will actually want. The import
paradigm (metadata first) is the foundation every later external-model feature builds on.

**Independent Test**: Open the HF view, search for "TinyLlama", select a result, click import, and
verify a model metadata entry appears in the registry with source, architecture family, parameter
count, license, tokenizer family, and revision SHA — with assets not yet downloaded.

**Acceptance Scenarios**:

1. **Given** the HF view, **When** the learner searches and selects a model, **Then** its card metadata
   is displayed (params, license, architecture, tokenizer).
2. **Given** a selected model, **When** the learner imports it, **Then** a metadata entry is created in
   the registry marked "metadata only (assets not downloaded)".
3. **Given** a model not in the curated catalog, **When** the learner imports it, **Then** the system
   records it but flags whether it is eligible for local fine-tuning (FT-AD-8).
4. **Given** a local model file/path, **When** the learner imports it via the generic source, **Then**
   it is tracked identically to an HF import (source-agnostic, FT-AD-4).

---

### User Story 3 — Learner Acquires and Stores Model Assets (Priority: P1)

A learner downloads the weights, tokenizer, and config for an imported model. The assets are tracked
by anvil's governance the same way corpora and datasets are — on the local filesystem now, and in
LakeFS once SaaS is enabled.

**Why this priority**: Fine-tuning external models is impossible without their assets, and "track them
with our system / store them in lakeFS under SaaS" is an explicit requirement.

**Independent Test**: For an imported model, click download; verify weights/tokenizer/config land in
the managed asset store, the metadata entry flips to "assets available", and (in SaaS/dev-stack mode)
the objects are written through the `VersionedContentStore` (LakeFS) rather than raw filesystem.

**Acceptance Scenarios**:

1. **Given** a metadata-only model, **When** the learner downloads assets, **Then** weights, tokenizer,
   and config are stored as managed, content-addressed assets and the entry shows "assets available".
2. **Given** SaaS mode, **When** assets are downloaded, **Then** they are written via the
   `VersionedContentStore` (LakeFS, AD-17) and are RBAC-scoped to the org.
3. **Given** an asset download is interrupted, **When** retried, **Then** it resumes/idempotently
   completes without corrupting the tracked entry.

---

### User Story 4 — Learner Fine-Tunes a Small Model Locally with LoRA (Priority: P1)

A learner picks an imported TinyLlama-class model with assets available, configures a LoRA/QLoRA run on
a small dataset, and runs it on their own machine (GPU if present), producing a small adapter — with
the model's own subword tokenizer used throughout.

**Why this priority**: This is the core of Track B and the headline capability ("fine-tune real LLMs").
It depends on the tokenizer abstraction and the asset store, and proves the local PEFT path end-to-end.

**Independent Test**: With a downloaded TinyLlama-class model and a tiny instruction dataset, start a
LoRA run with minimal settings; verify the subword tokenizer is used, training progresses, and a LoRA
adapter artifact is produced and tracked.

**Acceptance Scenarios**:

1. **Given** a catalog model with assets, **When** the learner starts a LoRA run, **Then** the model's
   subword tokenizer (not char-level) encodes the data and training runs via the torch/PEFT backend.
2. **Given** the `[finetune]` extra is not installed, **When** the learner starts an external fine-tune,
   **Then** the system fails fast with "install `anvil[finetune]`" (FT-AD-2), never silently degrading.
3. **Given** a completed LoRA run, **When** the learner views results, **Then** a LoRA adapter (not a
   full model copy) is stored, linked to its base model.
4. **Given** a model larger than the local catalog envelope, **When** local fine-tune is attempted,
   **Then** the learner is guided to offload to SaaS (FT-AD-8).

---

### User Story 5 — Learner Runs, Merges, and Exports a Fine-Tuned Model (Priority: P2)

A learner generates samples from a fine-tuned model (base + adapter), optionally merges the adapter
into standalone weights, and exports the result.

**Why this priority**: A fine-tuned model is only useful if it can be run and taken away. Inference with
adapters and export close the loop, but they follow the engine work.

**Independent Test**: Load a base model plus its adapter, generate text, then merge+export and verify the
exported artifact runs without the adapter attached.

**Acceptance Scenarios**:

1. **Given** a base model and adapter, **When** the learner runs inference, **Then** the adapter is
   composed onto the base at load time and samples reflect the fine-tuning.
2. **Given** an adapter, **When** the learner merges and exports, **Then** a standalone weights artifact
   is produced and registered.

---

### User Story 6 — Learner Offloads a Larger Fine-Tune to SaaS (Priority: P2)

A learner whose model/dataset exceeds local limits submits the same fine-tune configuration to SaaS,
where it runs on GPU compute, with base assets sourced from LakeFS and the adapter returned and tracked.

**Why this priority**: "Offload larger workloads to SaaS" is a core goal, but it builds on the local
path, the asset/LakeFS storage, and the existing SaaS training pipeline (032).

**Independent Test**: With SaaS mode configured, submit a fine-tune that the resolver classifies as
"too large for local"; verify it dispatches to the SaaS compute backend, streams metrics via the
existing job pipeline, and returns a tracked adapter.

**Acceptance Scenarios**:

1. **Given** SaaS mode, **When** a fine-tune exceeds the local envelope, **Then** the resolver routes it
   to the SaaS backend rather than failing (auto) — or raises if local was explicitly required (D4).
2. **Given** a SaaS fine-tune, **When** it runs, **Then** the base model is fetched from LakeFS, metrics
   stream via the existing `job_events`/SSE pipeline, and the adapter artifact is stored and registered.

---

### User Story 7 — Learner Progresses Through Fine-Tuning Concepts (Priority: P1)

A learner follows an explorable learning arc that explains what fine-tuning is, how warm-start differs
from PEFT/LoRA, when to fine-tune vs prompt vs RAG, and how model architectures differ (and why anvil
supports some but not all).

**Why this priority**: Pedagogy is anvil's reason for existing; fine-tuning must be *taught*, not just
enabled. This is first-class, not documentation (FT-AD-10).

**Independent Test**: Open the fine-tuning learning section; verify pages exist for warm-start vs PEFT,
LoRA intuition, fine-tune-vs-prompt-vs-RAG, and architecture differences, each in the existing
explorable-explanation style and linked into the learning navigation.

**Acceptance Scenarios**:

1. **Given** the learning section, **When** the learner opens the fine-tuning arc, **Then** concepts are
   presented as an ordered progression from the existing from-scratch material.
2. **Given** the architecture-differences page, **When** the learner explores it, **Then** it explains
   tokenization, attention/parameter/context differences and what they imply for fine-tuning — without
   claiming anvil executes every architecture (FT-AD-9).

---

### User Story 8 — Existing From-Scratch Pretraining Is Unchanged (Priority: P1, Invariant)

A user who installs anvil with no extras and trains a char-level model from scratch sees exactly today's
behavior: zero new dependencies, identical flow, identical results.

**Why this priority**: The existing product is the on-ramp and the baseline. Breaking it — or bloating
the base install — is unacceptable. This is the fine-tuning analogue of the SaaS local-mode invariant.

**Independent Test**: `pip install anvil` (no extras), `anvil serve`, train from scratch end-to-end;
assert `torch`/`transformers`/`peft`/`huggingface_hub` are NOT importable from the stdlib core path.

**Acceptance Scenarios**:

1. **Given** a base (no-extras) install, **When** the user trains from scratch, **Then** no ML/cloud
   deps are installed and the stdlib engine path imports none of them.
2. **Given** any fine-tuning feature shipped, **When** the pre-existing test suite runs unmodified,
   **Then** it passes (NMRG).

---

### User Story 9 — Learner Prepares an Instruction Dataset (Priority: P1)

A learner turns raw examples into prompt→response pairs formatted with the target model's chat template,
ready to fine-tune on.

**Why this priority**: Instruction fine-tuning is unusable without correctly formatted, chat-templated
data; this is the missing prerequisite behind every external fine-tune.

**Independent Test**: Prepare a small instruction dataset with a TinyLlama-class chat template and verify
a fine-tune (044) accepts it unchanged.

**Acceptance Scenarios**:

1. **Given** raw examples, **When** the learner prepares a dataset, **Then** records are SFT
   prompt→response pairs tracked via the datasets governance (005).
2. **Given** a target base model, **When** preparing, **Then** the model's chat template is applied (or a
   clearly labeled default), and the formatting + target model are recorded.

---

### User Story 10 — Learner Compares Fine-Tuned vs Base (Priority: P1)

A learner runs the same prompts through a fine-tuned model and its base, sees outputs side by side, and
views metrics indicating whether the fine-tune improved.

**Why this priority**: "Did it help?" is the question every fine-tune raises; without comparison the loop
is blind.

**Independent Test**: Evaluate a fine-tuned model and its base on a held-out set; verify side-by-side
samples and a recorded metric delta.

**Acceptance Scenarios**:

1. **Given** a fine-tuned model and its base, **When** evaluated on a held-out set, **Then** side-by-side
   samples and a base→fine-tuned metric delta are shown and recorded.
2. **Given** an adapter model, **When** evaluated, **Then** inference composes base+adapter and the
   correct tokenizer family is used.

---

### User Story 11 — Learner Teaches a Model Iteratively (Priority: P1)

A learner runs a short fine-tune, inspects outputs, adds corrective examples, and runs another round that
builds on the previous one — repeating until satisfied, with the teaching history visible.

**Why this priority**: "Teaching it" is a stated first-class goal; the iterative, checkpoint-chained loop
is what makes fine-tuning feel like teaching rather than a one-shot job.

**Independent Test**: Run two chained teaching rounds; verify round 2 warm-starts from round 1 and the
session lineage is visible.

**Acceptance Scenarios**:

1. **Given** a base model, **When** the learner runs a teaching round, **Then** a short fine-tune runs
   from the current checkpoint and outputs are shown.
2. **Given** a completed round, **When** the learner adds examples and runs again, **Then** the new round
   warm-starts from the previous round's checkpoint and the chain is recorded as lineage.

---

### Edge Cases

- What happens when an imported model's architecture/tokenizer family is unknown to anvil? → It is
  tracked as metadata but flagged not-runnable, with a learning pointer to architecture differences.
- How does the system handle a base model whose license forbids redistribution under SaaS storage? →
  License is recorded at import; asset storage/sharing respects it.
- What happens when a fine-tune's `base_model_ref` points to a model whose assets were deleted? → Run
  fails fast with a clear "assets unavailable, re-download" error, not a silent fallback.
- How does the resolver behave when SaaS is not configured but the model is too large for local? →
  `auto` reports the model exceeds local limits and SaaS is unavailable; explicit local selection
  raises with guidance (D4).
- What happens when the `[finetune]` extra is partially installed (e.g., `transformers` but not
  `peft`)? → Capability probe fails fast naming the missing package.
- What happens when a user imports a GGUF or `.bin` model in v1? → Rejected with a clear message naming
  the format and pointing to the deferred GGUF roadmap (specs 050–052); no best-effort load (FT-AD-11).
- What happens when a model is safetensors but a non-allow-list architecture (e.g. Qwen2)? → Metadata is
  tracked, but fine-tune/inference are disabled (track-but-not-run) with a link to the
  architecture-differences lesson (049).

## Requirements

### Functional Requirements — Native Warm-Start & Lineage (→ spec 039)

- **FR-001**: A training run MUST accept an optional `base_model_ref` identifying an existing registered
  anvil checkpoint; when present, training warm-starts from those weights instead of random
  initialization.
- **FR-002**: The torch training engine MUST support warm-start from an existing model (closing the gap
  where `anvil.core.torch_engine.train_torch` currently has no `model=` parameter), at parity with the
  stdlib engine's existing `train(docs, model=...)`.
- **FR-003**: A fine-tuned model MUST record its lineage — parent `base_model_ref`, the corpus/dataset
  it was specialized on, and that it was produced by warm-start — in the model registry.
- **FR-004**: Warm-start runs MUST stream live metrics through the existing training/SSE pipeline
  unchanged.

### Functional Requirements — External Model Import & Registry (→ specs 040, 041)

- **FR-005**: The system MUST support importing external models via a **source-agnostic** `ModelSource`
  abstraction, with HuggingFace Hub as the first source and local-file/path import as the second.
- **FR-006**: Importing a model MUST create a tracked metadata entry recording at minimum: display
  name, source + source identifier, architecture family, parameter count, license, tokenizer family,
  and revision/commit SHA — created BEFORE any asset download.
- **FR-007**: The system MUST provide an in-app HuggingFace view to search, browse, and inspect model
  cards, surfacing a curated catalog of very small models (TinyLlama-class) suitable for local
  fine-tuning.
- **FR-008**: The catalog MUST mark, per model, whether it is eligible for **local** fine-tuning based
  on a documented resource envelope (params, min RAM/VRAM, supported methods) — FT-AD-8.
- **FR-009**: External-model metadata MUST be tracked in the existing model registry alongside anvil's
  own trained models (extending spec 003), distinguishable by origin.

### Functional Requirements — Asset Acquisition & Storage (→ spec 042)

- **FR-010**: The system MUST download model assets (weights, tokenizer files, config) for an imported
  model on explicit request, storing them as managed, content-addressed assets.
- **FR-011**: Asset storage MUST use the existing storage seam: local `FileStore` in local mode and the
  `VersionedContentStore` (LakeFS, AD-17) in SaaS mode — RBAC-scoped to the owning org in SaaS.
- **FR-012**: Asset download MUST be idempotent/resumable and MUST update the model's metadata entry to
  reflect asset availability and integrity (checksums).
- **FR-013**: The system MUST record and respect each model's upstream license for storage and sharing
  decisions.

### Functional Requirements — Tokenizer Abstraction (→ spec 043)

- **FR-014**: Tokenization MUST be abstracted so a model carries its tokenizer as a first-class
  artifact; encode/decode MUST resolve from the attached tokenizer.
- **FR-015**: The abstraction MUST support both anvil's character-level vocabulary and HuggingFace
  subword tokenizers, and MUST record which family a given model uses for downstream inference/eval.

### Functional Requirements — Local PEFT Fine-Tuning (→ spec 044)

- **FR-016**: The system MUST provide a compute backend that fine-tunes external pretrained models using
  parameter-efficient methods (`lora`, `qlora`) and optionally `full`, built on `torch`/`transformers`/
  `peft`, registered behind the existing `ComputeBackendProtocol`.
- **FR-017**: A fine-tune MUST be configured by a `FineTuneSpec` (method, target modules, rank/alpha,
  learning rate, steps, quantization) plus a `base_model_ref` and a dataset.
- **FR-018**: Local fine-tuning MUST be restricted to catalog models within the local resource envelope
  (FT-AD-8); attempts beyond it MUST guide the user to SaaS rather than OOM.
- **FR-019**: All heavy fine-tuning dependencies MUST be optional extras; absence MUST fail fast with an
  install hint and MUST NOT be importable in a base install (FT-AD-2, NMRG).

### Functional Requirements — Adapter Inference, Merge & Export (→ spec 045)

- **FR-020**: A fine-tune run MUST be able to return a LoRA **adapter** artifact distinct from full
  weights; `ComputeResult` MUST represent base+adapter as a first-class result shape (FT-AD-7).
- **FR-021**: Inference MUST compose a base model with its adapter at load time; the system MUST support
  optionally merging an adapter into standalone weights and exporting the result.

### Functional Requirements — Compute Routing & SaaS Offload (→ specs 046, 047)

- **FR-022**: Fine-tunes MUST be dispatched through the existing compute resolution layer
  (`resolve.py`), which selects local vs SaaS by `ResourceSpec`/base-model size under the D4
  degraded-mode rules (auto/local fall back; explicit unavailable selection raises).
- **FR-023**: SaaS fine-tuning MUST reuse the existing SaaS training pipeline (spec 032) — durable
  `job_events`, SSE/poll metrics, usage metering — fetching base assets from LakeFS and returning a
  tracked adapter.

### Functional Requirements — Pedagogy (→ specs 048, 049)

- **FR-024**: The learning arc MUST add fine-tuning content as an ordered progression from the existing
  from-scratch material: what fine-tuning is, warm-start vs PEFT/LoRA, and when to fine-tune vs prompt
  vs RAG.
- **FR-025**: The learning arc MUST include an architecture-differences module explaining tokenization,
  attention/parameter/context differences and their fine-tuning implications, explicitly scoping that
  anvil executes a limited architecture set while teaching the broader landscape (FT-AD-9).
- **FR-026**: Each shippable fine-tuning capability MUST ship with its corresponding learning content
  (FT-AD-10).

### Functional Requirements — External Format Support (→ specs 041, 042, 043, 049; FT-AD-11)

- **FR-030**: Asset acquisition MUST accept **safetensors** as the only weight/serialization format in
  v1, and MUST reject PyTorch pickle (`.bin`/`.pt`), GGUF, and pre-quantized GPTQ/AWQ checkpoints with a
  clear, actionable message naming the format and pointing to the deferred GGUF roadmap (specs 050–052).
- **FR-031**: The tokenizer abstraction MUST support, in v1, HF fast tokenizers (`tokenizer.json`) and
  SentencePiece (`tokenizer.model` / `sentencepiece.model`), and MUST record the serialization type on
  the model.
- **FR-032**: The system MUST publish a concrete **runnable architecture allow-list** (v1:
  `LlamaForCausalLM` — Llama 2/3 small variants, TinyLlama). Models outside the allow-list MUST be
  **track-but-not-run** (metadata import succeeds; fine-tune/inference are disabled) and MUST link the
  architecture-differences lesson (049).
- **FR-033**: Import/asset-acquisition MUST **fail closed**: detect declared vs actual format and
  architecture from config and on-disk files, verify against the accepted formats (FR-030) and allow-list
  (FR-032) BEFORE any load attempt, and record the rejection reason on the model entry — never a
  best-effort load of an unsupported format/architecture.

### Functional Requirements — Workflow Completeness (→ specs 053, 054, 055)

- **FR-034**: The system MUST provide preparation of fine-tuning datasets — prompt→response (SFT) pairs,
  application of the base model's chat template, and (optionally) preference pairs — tracked through the
  existing dataset governance (005) and consumable directly by a fine-tune (044/047).
- **FR-035**: The system MUST support evaluating a fine-tuned model against its base — qualitative
  side-by-side samples and quantitative metrics — reusing the existing evaluation service and recording
  the base→fine-tuned delta.
- **FR-036**: The system MUST support an iterative **teaching loop** — add/curate examples, run a short
  fine-tune from the current checkpoint, inspect outputs, repeat — with each round checkpoint-chained to
  the previous (warm-start) and the session recorded as lineage.

### Functional Requirements — Invariants (apply to ALL features)

- **FR-027**: A training run with no `base_model_ref` MUST behave exactly as today's from-scratch
  pretraining — identical flow and observable results.
- **FR-028**: `pip install anvil` with no extras MUST NOT install or import `torch`, `transformers`,
  `peft`, `huggingface_hub`, or `datasets`; the stdlib engine MUST retain its zero-dependency
  guarantee (FT-AD-2).
- **FR-029**: Every feature's Definition of Done MUST include the Native-Mode Regression Gate (NMRG):
  unmodified pre-existing tests pass, lint/typecheck clean, base install boots and trains from scratch
  end-to-end, and the dependency-isolation assertion passes.

### Key Entities

- **ExternalModel**: A tracked metadata record for a model imported from a source — name, source +
  identifier, architecture family, parameter count, license, tokenizer family, revision SHA, asset
  availability, local-eligibility.
- **ModelSource**: Abstraction over where a model comes from (HuggingFace Hub, local file/path, future
  sources). Resolves metadata and asset locations.
- **ModelAsset**: A managed, content-addressed artifact (weights / tokenizer / config) belonging to a
  model, stored via `FileStore` (local) or `VersionedContentStore`/LakeFS (SaaS).
- **Tokenizer (abstraction)**: A model-attached tokenizer; char-level (native) or subword (HF).
- **BaseModelRef**: A reference to the model a run starts from (an anvil checkpoint or an external
  model with assets).
- **FineTuneSpec**: Configuration of a fine-tune — method (`full`/`lora`/`qlora`), target modules,
  rank/alpha, quantization, learning rate, steps.
- **Adapter**: A LoRA delta artifact produced by a PEFT run, linked to its base model.
- **FineTuneRun**: A training run with a `base_model_ref` (+ `FineTuneSpec` for external); records
  lineage and produces a model or adapter.
- **CuratedModelCatalog**: The vetted set of small models offered for local fine-tuning, with resource
  envelopes.
- **WeightFormat**: The accepted serialization of a model's weights (v1: `safetensors`; GGUF deferred).
- **ArchitectureAllowList**: The published set of runnable architectures (v1: `LlamaForCausalLM`);
  models outside it are track-but-not-run.
- **LearningModule**: An explorable learning-arc unit framing a fine-tuning capability.

## Success Criteria

- **SC-001**: A learner can specialize a previously trained anvil model via warm-start and see the new
  model's lineage to its parent — with zero new dependencies installed.
- **SC-002**: A learner can import a TinyLlama-class model from HuggingFace and see a complete tracked
  metadata entry before any weights are downloaded.
- **SC-003**: A learner can download a model's assets and have them tracked by the governance system;
  in SaaS mode the same assets are stored in LakeFS and org-scoped.
- **SC-004**: A learner can run a local LoRA fine-tune of a catalog model using the model's own subword
  tokenizer and obtain a tracked adapter, on a machine within the documented envelope.
- **SC-005**: A learner can run, merge, and export a fine-tuned model so the exported artifact runs
  without the adapter attached.
- **SC-006**: A fine-tune exceeding local limits routes to SaaS (when configured) and streams metrics
  through the existing pipeline, returning a tracked adapter.
- **SC-007**: The fine-tuning learning arc presents an ordered progression including architecture
  differences, in the existing explorable-explanation style.
- **SC-008**: For every shipped feature, the pre-existing test suite passes unmodified and a base
  (no-extras) install neither installs nor imports any ML/cloud dependency (NMRG).
- **SC-009**: Importing an unsupported weight format (e.g. GGUF, `.bin`) or a non-allow-list
  architecture is refused with a clear, actionable message (and, for architecture, tracked as
  not-runnable) — never a best-effort load (FT-AD-11).
- **SC-010**: A learner turns raw examples into a chat-templated instruction dataset and fine-tunes on
  it unchanged.
- **SC-011**: A learner compares a fine-tuned model to its base on identical prompts and sees whether it
  improved (samples + metric delta).
- **SC-012**: A learner teaches a model across ≥2 checkpoint-chained rounds with visible lineage and the
  ability to roll back.

## Assumptions

- Adding new optional prerequisites is acceptable (confirmed): `torch`, `transformers`, `peft`,
  `huggingface_hub`, `datasets` ship as extras, never in the base install.
- HuggingFace Hub is the primary external-model source for now; the import paradigm is source-agnostic
  to allow others (and explicit local-file import) later.
- Local fine-tuning targets very small models (TinyLlama-class); larger models are import-able and
  SaaS-routable but not offered for local fine-tuning.
- anvil does not aim to execute every model architecture; the learning layer covers the broader
  landscape conceptually.
- SaaS fine-tuning builds on the existing SaaS body of work (028 abstraction framework, 032 training
  pipeline) and LakeFS content storage (019 / AD-17) rather than introducing parallel infrastructure.
- The existing compute abstraction (`anvil/services/compute/`) — protocol, registry, `resolve.py`,
  `ComputeResult`, submit-then-poll — is the dispatch seam for fine-tune jobs.
- v1 external-format support is intentionally narrow (safetensors + Llama-family + HF/SentencePiece
  tokenizers, FT-AD-11); GGUF first-class support (export/import/run/train) is committed but deferred to
  separate specs 050–052.
