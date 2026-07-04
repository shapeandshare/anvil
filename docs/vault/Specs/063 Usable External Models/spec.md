---
title: 063 Usable External Models - Spec
type: spec
tags:
  - type/spec
created: 
updated: 2026-07-03
---

# Feature Specification: Usable External Models

**Feature Branch**: `063-usable-external-models`
**Created**: 2026-07-02
**Status**: Draft
**Input**: User description: "Make imported HuggingFace external models usable locally: load downloaded weights for inference and fine-tuning instead of always pulling from the Hub"

## Clarifications

### Session 2026-07-02

- Q: For models already downloaded under the current storage layout, how should we handle the transition to the new load-ready layout? → A: No legacy downloads exist; no migration or backward-compatibility path is required. The new load-ready layout is the only layout.
- Q: What should the asset storage layout on disk look like so downloaded files can be loaded directly? → A: Canonical HF directory layout: download to `models/{model_id}/hf/` with standard filenames (`model.safetensors`, `config.json`, `tokenizer.json`). Sha256 recorded as metadata only, not keying the storage path.
- Q: How should the system make local vs. network load events observable? → A: Structured log line on each model load recording the model ID and the source (`local` or `hub`). No Prometheus counters or additional infrastructure required.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Run an imported model locally (Priority: P1)

A user imports a small, runnable model from HuggingFace, downloads its weights, and then runs text generation with it in the playground — without the model being re-fetched over the network. After the one-time download, generation works even with no internet connection.

**Why this priority**: This is the core promise of the import feature and the single most visible gap today. Downloaded weights are currently never used, so an imported model cannot be run at all without a separately trained adapter. Delivering this alone makes the import → download → use loop meaningful and is a viable standalone MVP.

**Independent Test**: Import a runnable model, complete its asset download, then open the playground for that model and generate text with networking disabled. Success is a coherent generation with no network access and no error.

**Acceptance Scenarios**:

1. **Given** a runnable external model whose assets are downloaded, **When** the user opens the playground for that model and submits a prompt, **Then** the system returns generated text using the locally stored weights and makes no network request to the model host.
2. **Given** a runnable external model whose assets are downloaded, **When** the user opens the model detail page, **Then** a working action to run the model (e.g. "Play") is available and enabled.
3. **Given** an external model that has only been imported (metadata only, assets not downloaded), **When** the user views the model detail page, **Then** run/train actions are disabled or hidden and the user is guided to download assets first.
4. **Given** an external model whose architecture is not on the runnable allow-list, **When** the user views it, **Then** run/train actions remain unavailable and the reason is shown.

---

### User Story 2 - Fine-tune from an imported model (Priority: P2)

A user selects a downloaded external model as the starting point for training — both as a warm-start base for full fine-tuning and as the base for LoRA/QLoRA adapters — and the training run uses the locally stored weights.

**Why this priority**: Extends the imported model from "runnable" to "improvable". It depends on the loading capability from US1 and unlocks the fine-tuning workflows the product is built around. It is independently testable once US1's local loading exists.

**Independent Test**: Choose a downloaded external model as the training base, start a short training run, and confirm it initializes from the external model's weights (loss/behavior consistent with a warm start) using local assets, offline.

**Acceptance Scenarios**:

1. **Given** a downloaded runnable external model, **When** the user starts a full fine-tuning run with that model as the base, **Then** the run validates architecture compatibility and initializes from the external model's weights without error.
2. **Given** a downloaded runnable external model, **When** the user starts a LoRA/QLoRA run with that model as the base, **Then** the adapter trains on top of the locally loaded base weights.
3. **Given** an external model whose assets are not downloaded, **When** the user attempts to use it as a training base, **Then** the system blocks the run with a clear message to download assets first.
4. **Given** an external model whose architecture is incompatible with the requested training configuration, **When** the user attempts the run, **Then** the system rejects it with an explanatory validation error before training starts.

---

### User Story 3 - Downloaded weights are reused everywhere, not re-fetched (Priority: P3)

Across every operation that touches an external model — running, fine-tuning, applying an adapter, merging an adapter, and evaluation — the system uses the locally downloaded assets when they are present, and only reaches out to the network when assets are absent.

**Why this priority**: Consistency and correctness across all existing consumers. It generalizes US1/US2 so the whole product respects downloaded assets, avoids surprise re-downloads and bandwidth, and enables reliable offline operation. It is a refinement layer on top of the earlier stories.

**Independent Test**: With assets downloaded and networking disabled, exercise adapter inference, adapter merge, and evaluation for the external model; all succeed. Then remove/omit assets and confirm the system either falls back to a network fetch (when online) or fails with a clear "assets not available" message (when offline).

**Acceptance Scenarios**:

1. **Given** a downloaded external model, **When** any adapter, merge, or evaluation operation runs against it, **Then** the operation reads the local assets and issues no network request for the base model.
2. **Given** an external model without downloaded assets and an available network, **When** an operation needs the base model, **Then** the system fetches it from the model host as a fallback and records that a network fetch occurred.
3. **Given** an external model without downloaded assets and no network, **When** an operation needs the base model, **Then** the system fails with a clear, actionable "assets not available — download required" message rather than a low-level network error.

---

### Edge Cases

- **Incomplete/partial download**: If some required asset files are missing or a prior download was interrupted, the model MUST be treated as not locally runnable and the user prompted to (re)download; the system MUST NOT attempt to load a partial model.
- **Corrupted/altered asset**: If a stored asset fails its integrity check at load time, the system MUST refuse to load it and surface a corruption error, prompting re-download.
- **Assets present but architecture not runnable**: Downloading assets for a track-only architecture MUST NOT make run/train actions available.
- **Optional runtime not installed**: When the optional fine-tuning/runtime components required to load full external models are absent, the system MUST degrade gracefully with a clear message rather than crashing.
- **Concurrent use during download**: Attempting to run or train while a download for the same model is still in progress MUST be blocked with a clear "download in progress" state.
- **Disk exhaustion**: If storing or materializing assets fails due to insufficient space, the system MUST fail cleanly with an explanatory message and leave no half-written state marked as available.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST allow a runnable external model with downloaded assets to be loaded and used for text generation using only locally stored assets, with no network request to the model host.
- **FR-002**: The system MUST store a downloaded model's assets in a HuggingFace-standard directory layout at `models/{model_id}/hf/` with canonical filenames (`model.safetensors`, `config.json`, `tokenizer.json`) so the directory can be passed directly to `from_pretrained()`. Integrity fingerprints (SHA-256) are recorded as per-asset metadata, not as path components.
- **FR-003**: The system MUST allow a downloaded runnable external model to be selected as the base for full fine-tuning (warm start), including validating architecture compatibility before the run begins.
- **FR-004**: The system MUST allow a downloaded runnable external model to be selected as the base for LoRA/QLoRA fine-tuning.
- **FR-005**: For all operations that require an external model's base weights (running, fine-tuning, adapter application, adapter merge, evaluation), the system MUST prefer locally downloaded assets when they are present.
- **FR-006**: When local assets are absent and a network is available, the system MUST fall back to fetching from the model host, and MUST record that a network fetch occurred.
- **FR-007**: When local assets are absent and no network is available, the system MUST fail with a clear, actionable "assets not available — download required" message.
- **FR-008**: The system MUST verify the integrity of stored assets before loading and MUST refuse to load assets that fail verification, surfacing a corruption/re-download message.
- **FR-009**: The system MUST treat a model with missing or incomplete required assets as not locally runnable and MUST NOT attempt to load a partial model.
- **FR-010**: The system MUST restrict local run/train capabilities to architectures on the runnable allow-list; track-only models MUST remain non-runnable even after asset download, with the reason shown.
- **FR-011**: The model detail UI MUST present working run and train actions for a runnable external model once its assets are available, and MUST disable or hide those actions (with guidance to download first) when assets are metadata-only.
- **FR-012**: The system MUST prevent running or training against a model whose asset download is still in progress, and MUST communicate that in-progress state.
- **FR-013**: When the optional runtime components needed to load full external models are not installed, the system MUST degrade gracefully with an explanatory message and MUST NOT crash.
- **FR-014**: The system MUST ensure that a failed or interrupted asset store operation does not leave a model marked as "assets available".

### Key Entities *(include if feature involves data)*

- **External Model**: A record of a model imported from an external source, including its display name, source identifier, architecture family, runnable status (runnable vs track-only) with reason, and asset availability state (metadata-only, pending, available).
- **Model Asset**: A single downloaded file belonging to an external model (weights, tokenizer, or configuration), including its integrity fingerprint, size, availability status, and storage location. Stored in a standard HuggingFace directory layout (`models/{model_id}/hf/`) with canonical filenames so the directory can be used directly with runtime model loaders.
- **Asset Download Job**: The lifecycle record of a download attempt for a model's assets (queued, in progress, complete, failed) with error information.
- **Training Base Reference**: The linkage that lets a training run start from an existing model, now able to reference an external model as its warm-start or adapter base.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: After a one-time download, a user can generate text from an imported runnable model with networking disabled, with a 100% success rate across supported runnable models (no network errors, no re-download).
- **SC-002**: For an external model with downloaded assets, running, adapter inference, adapter merge, and evaluation each complete with zero network requests to the model host (measured over a full offline test pass).
- **SC-003**: A user can start a fine-tuning run (full or LoRA) from a downloaded external model, and the run initializes from that model's weights without manual file handling.
- **SC-004**: 100% of attempts to run or train a model with missing/incomplete/unavailable assets produce a clear, actionable message (and never a raw low-level network or file error).
- **SC-005**: Downloaded bytes are used: for any external model run after download, the model host is contacted zero times while assets remain valid on disk.

## Assumptions

- **Runnable scope unchanged**: The set of runnable architectures remains the existing allow-list (currently the Llama-family causal LM). Broadening architecture support is out of scope.
- **No legacy downloads**: No assets have been downloaded under a prior storage layout, so no migration or backward-compatibility path is required. The new load-ready layout is the only layout.
- **Optional runtime**: Loading full external models for inference/training depends on optional runtime components that are not part of the base install; behavior when they are absent is graceful degradation, not failure of the whole app.
- **Integrity model reused**: The existing per-asset integrity fingerprinting from the current download feature is retained and used at load time.
- **Single-host storage**: Local asset storage uses the existing file storage abstraction; remote/SaaS storage routing is out of scope for this feature.
- **UI surface**: Run/train affordances are surfaced on the existing model detail page and playground; no new top-level navigation is introduced.
- **Load observability**: Every model load (local or network) emits a structured log line with model ID and source (`local` or `hub`), providing the audit trail to verify network-free operation (SC-002, SC-005).

## Out of Scope

- Supporting model architectures beyond the current runnable allow-list.
- Quantization or format conversion of downloaded weights beyond what is required to load them.
- Remote/SaaS compute routing or remote asset storage changes.
- Changes to how models are discovered or imported (search/import flow is unchanged).
- Migration or backward compatibility for assets downloaded under a prior storage layout (none exist).
