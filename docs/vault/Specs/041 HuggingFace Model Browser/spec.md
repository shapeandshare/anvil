---
title: 041 HuggingFace Model Browser - spec
type: spec
tags:
  - type/spec
  - domain/training
  - domain/ui
status: draft
spec-refs:
  - docs/vault/Specs/041 HuggingFace Model Browser/
related:
  - '[[041 HuggingFace Model Browser]]'
  - '[[038 Fine-Tuning Arc]]'
  - '[[Reference/FineTuningArchitectureDecisions]]'
created: '2026-06-28'
updated: '2026-06-28'
---

# Feature Specification: HuggingFace Model Browser & Curated Catalog

**Feature Branch**: `041-huggingface-model-browser`
**Created**: 2026-06-28
**Status**: Draft
**Parent Spec**: [[Specs/038 Fine-Tuning Arc/038 Fine-Tuning Arc|038 Fine-Tuning Arc (umbrella)]]

## Overview

An in-app HuggingFace view to search, browse, and inspect model cards, fronted by a **curated catalog**
of very small models (TinyLlama-class) with documented resource envelopes. Each model shows whether it
is eligible for **local** fine-tuning, so learners discover models that will actually fit their machine.
One-click import feeds the registry (spec 040).

### Scope

| Dimension | Scope |
|-----------|-------|
| **Owned FRs** | FR-007, FR-008, FR-032 (publish allow-list) |
| **Owned decisions** | FT-AD-8, FT-AD-11 (allow-list aspect) |
| **Depends on** | 040 (import paradigm + `ExternalModel`); `huggingface_hub` library (behind `[finetune]` extra, token optional) for `HfApi.list_models()` / `HfApi.model_info()` |
| **Invariant risk** | **LOW** — new UI + read-only HF API calls behind the extra; no-token fallback meets free-tier rate limits with local cache layer |

---

## User Story

### US — Learner Browses and Picks a Model That Fits (Priority: P1)

A learner opens the HF view, browses the curated small-model catalog, inspects a model's card, sees
whether it fits locally, and imports it.

**Independent Test**: Open the HF view, search "TinyLlama", inspect a result's card (params, license,
architecture, tokenizer), confirm the local-eligibility badge reflects its envelope, and import it.

**Acceptance Scenarios**:

1. **Given** the HF view, **When** the learner searches and selects a model, **Then** its card metadata
   is displayed (params, license, architecture, tokenizer family).
2. **Given** the curated catalog, **When** the learner browses it, **Then** each model shows a
   local-eligibility badge derived from its documented resource envelope.
3. **Given** a selected model, **When** the learner clicks import, **Then** a metadata entry is created
   via spec 040.
4. **Given** a model outside the curated catalog, **When** inspected, **Then** it is still import-able
   but clearly flagged "not offered for local fine-tuning".

### Edge Cases

- HF API unavailable → the curated catalog (static metadata) still renders; live search degrades
  gracefully.
- A catalog model's upstream card changes (params/license) → catalog metadata is the display source of
  truth, with a link to the live card.
- Machine has no GPU → eligibility badges reflect CPU-only envelopes honestly.

## Requirements

- **FR-007**: The system MUST provide a dedicated in-app HuggingFace view at `/v1/hf-browser` to search,
  browse, and inspect model cards, surfacing a curated catalog of very small models (TinyLlama-class)
  suitable for local fine-tuning. The view consists of a search bar, a catalog/results list, and a
  detail panel on selection.
- **FR-008**: The catalog MUST mark, per model, whether it is eligible for local fine-tuning based on a
  documented resource envelope (params, min RAM/VRAM, supported methods).
- **FR-008a**: Local-eligibility MUST be computed against the running host's detected resources where
  available (reusing device detection in `anvil/services/compute/resolve.py`), not a static assumption.
- **FR-007a**: The curated catalog MUST be maintained as in-repo metadata (not solely a live API call)
  so the view is useful offline and stable across upstream card changes.
- **FR-032**: The browser MUST publish the concrete runnable **architecture allow-list** (v1:
  `LlamaForCausalLM` — Llama 2/3 small variants, TinyLlama) and the accepted weight format (safetensors)
  so eligibility is transparent. A model outside the allow-list or in an unsupported format MUST be shown
  as **track-but-not-run** (import-able as metadata; fine-tune/inference disabled), with a link to the
  architecture-differences lesson (049).

## Success Criteria

- **SC-001**: A learner completes search → inspect → import for a catalog model without leaving the app.
- **SC-002**: Each catalog model displays an accurate local-eligibility badge from its envelope.
- **SC-003**: The view degrades gracefully when the HF API is unavailable (catalog still renders).
- **SC-004**: The runnable architecture allow-list and accepted format are visible in the browser; a
  non-allow-list or unsupported-format model is clearly shown as track-but-not-run with a lesson link.
- **SC-005 (NMRG)**: Pre-existing tests pass unmodified; base install imports no HF client.

## Key Entities

### CuratedModelCatalog

An in-repo metadata catalog of vetted small models (TinyLlama-class and similar) offered for local fine-tuning. Each entry is a structured record:

| Field | Type | Description |
|-------|------|-------------|
| `hf_id` | `str` | HuggingFace model ID (e.g. `"TinyLlama/TinyLlama-1.1B-Chat-v1.0"`) — stable key |
| `display_name` | `str` | Human-readable name |
| `params` | `str` | Parameter count label (e.g. `"1.1B"`) |
| `license` | `str` | SPDX license identifier (e.g. `"Apache-2.0"`) |
| `architecture` | `str` | HuggingFace architecture class (e.g. `"LlamaForCausalLM"`) |
| `tokenizer_family` | `str` | Tokenizer type (e.g. `"SentencePiece"`, `"tokenizers"`) |
| `url` | `str` | Link to live HF model card |
| `tags` | `list[str]` | Categorization tags (e.g. `["tiny", "chat", "base"]`) |
| `resource_envelope` | `ResourceEnvelope` | Embedded resource requirements (see below) |

The catalog is stored as a YAML file (`anvil/data/curated-models.yaml`) loaded at runtime and validated against a Pydantic `CatalogEntry` model. Updates are submitted via PR.

### ResourceEnvelope

Documents the resource requirements for running/fine-tuning a model, with per-backend VRAM:

| Field | Type | Description |
|-------|------|-------------|
| `min_ram_gb` | `float` | Minimum system RAM in GB |
| `min_vram_per_backend` | `dict[str, float]` | Per-backend minimum VRAM in GB, keyed by backend name (e.g. `{"cpu": 0, "cuda": 4.0, "mps": 6.0}`) |
| `supported_methods` | `list[str]` | Supported fine-tuning methods (e.g. `["full", "lora"]`) |

`min_vram_per_backend` enables eligibility badges that reflect the running machine's detected device (reusing `anvil/services/compute/resolve.py`). A value of `0` for `cpu` means no VRAM requirement (RAM is the binding constraint).

## Clarifications

### Session 2026-06-28

- Q: What fields comprise CuratedModelCatalog and ResourceEnvelope? → A: Structured JSON schema with backend-specific envelopes per Option B. Fields documented in Key Entities above.
- Q: How is the curated catalog stored and maintained on disk? → A: YAML file (`anvil/data/curated-models.yaml`) loaded at runtime via a Pydantic `CatalogEntry` model. Updates via PR.
- Q: What HF Hub API interaction pattern should the browser use? → A: `huggingface_hub` library (`HfApi.list_models()` / `HfApi.model_info()`) behind `[finetune]` extra, token optional, with a local cache layer.
- Q: What page structure should the HF view use? → A: Standalone page at `/v1/hf-browser` with search bar, catalog/results list, and detail panel on selection.

## Definition of Done

- Search→inspect→import works for a catalog model; eligibility badges accurate; offline-safe catalog;
  **NMRG (full)**.

## Assumptions

- Importing delegates entirely to spec 040; this spec owns discovery/UI and the catalog, not the
  registry record.
