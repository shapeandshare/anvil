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
| **Depends on** | 040 (import service `workbench.model_imports.submit_import(...)`, `ExternalModel`, `RunnableStatus`, `_ALLOWED_ARCHITECTURES`, `_ACCEPTED_FORMATS`, and the existing `POST /v1/models/import` route); `huggingface_hub` library (behind `[finetune]` extra, token optional) for `HfApi.list_models()` / `HfApi.model_info()`; `detect_gpu()` (`anvil/gpu.py`) + `psutil` (core) for resource detection; **PyYAML — NOT currently a declared dependency**, must be added to core deps (see FR-007b) |
| **Forward dependency** | spec 049 (architecture-differences lesson) — link target only; not yet implemented, must degrade gracefully |
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
3. **Given** a selected model, **When** the learner clicks import, **Then** the existing spec 040 import
   flow is invoked (`POST /v1/models/import` with `source="huggingface"`, `identifier=<hf_id>`), creating
   a metadata entry. Architecture is auto-derived by the import service from the model config — NOT passed
   by this UI.
4. **Given** a model outside the curated catalog, **When** inspected, **Then** it is still import-able
   but clearly flagged "not offered for local fine-tuning".

### Edge Cases

- HF API unavailable → the curated catalog (static metadata) still renders; live search degrades
  gracefully.
- A catalog model's upstream card changes (params/license) → catalog metadata is the display source of
  truth, with a link to the live card.
- Machine has no GPU → only the RAM check applies; VRAM-based eligibility is skipped and the badge reflects
  CPU-only viability honestly.
- Machine is Apple Silicon (MPS) → `detect_gpu()` reports system RAM as a unified-memory proxy; eligibility
  is best-effort and the UI notes this caveat.
- spec 049 lesson not yet implemented → the architecture-differences link is omitted/"coming soon", never
  a broken link.

## Requirements

- **FR-007**: The system MUST provide a dedicated in-app HuggingFace view at `/v1/hf-browser` to search,
  browse, and inspect model cards, surfacing a curated catalog of very small models (TinyLlama-class)
  suitable for local fine-tuning. The view consists of a search bar, a catalog/results list, and a
  detail panel on selection.
- **FR-008**: The catalog MUST mark, per model, whether it is eligible for local fine-tuning based on a
  documented resource envelope (params, min RAM/VRAM, supported methods).
- **FR-008a**: Local-eligibility MUST be computed against the running host's detected resources, reusing
  the existing `detect_gpu()` function (`anvil/gpu.py`, returns `GpuInfo` with `backend`,
  `memory_total_gb`, `memory_available_gb`) for GPU detection and `psutil.virtual_memory()` (psutil is a
  **core** dependency) for system RAM. Eligibility compares: (a) `min_ram_gb` against detected total
  system RAM; (b) `min_vram_per_backend[detected_backend]` against detected GPU `memory_total_gb`. On a
  CPU-only host (no GPU detected), only the RAM check applies. **Caveat**: MPS hosts report system RAM as
  a VRAM proxy (Apple unified memory) — eligibility on MPS is best-effort, documented as such in the UI.
- **FR-007a**: The curated catalog MUST be maintained as in-repo metadata (not solely a live API call)
  so the view is useful offline and stable across upstream card changes.
- **FR-007b**: PyYAML is **not** currently a declared dependency (only a transitive one via mlflow et al.).
  Because the catalog loader runs at base install, PyYAML MUST be added to `[project.dependencies]` in
  `pyproject.toml` (justified per the constitution's lean-dependency rule: a small, ubiquitous, pure-data
  parser already present transitively). The catalog loader MUST NOT rely on an undeclared transitive dep.
- **FR-032**: The browser MUST publish the concrete runnable **architecture allow-list** and accepted
  weight format so eligibility is transparent. The allow-list and accepted-format values MUST be the
  **same single source of truth used by spec 040's import service** (`_ALLOWED_ARCHITECTURES = {"LlamaForCausalLM"}`
  and `_ACCEPTED_FORMATS = {"safetensors"}` in `anvil/services/model_import/model_import_service.py`) —
  this spec MUST NOT define a second, parallel allow-list. A model outside the allow-list or in an
  unsupported format MUST be shown as **track-but-not-run** (import-able as metadata; fine-tune/inference
  disabled), reusing the existing `RunnableStatus` enum (`RUNNABLE` / `TRACK_ONLY`). Where the
  architecture-differences lesson (spec 049) is available, a link MUST be shown; until spec 049 ships,
  this link is a forward dependency and MUST degrade gracefully (omitted or shown as "coming soon"),
  never producing a broken link.

## Success Criteria

- **SC-001**: A learner completes search → inspect → import for a catalog model without leaving the app.
- **SC-002**: Each catalog model displays an accurate local-eligibility badge from its envelope.
- **SC-003**: The view degrades gracefully when the HF API is unavailable (catalog still renders).
- **SC-004**: The runnable architecture allow-list and accepted format are visible in the browser; a
  non-allow-list or unsupported-format model is clearly shown as track-but-not-run. The lesson link
  appears when spec 049 is available and is gracefully omitted otherwise.
- **SC-005 (NMRG)**: Pre-existing tests pass unmodified; base install imports no HF client.
- **SC-006**: The allow-list and accepted-format values displayed match spec 040's
  `_ALLOWED_ARCHITECTURES` / `_ACCEPTED_FORMATS` exactly (single source of truth — no duplicate constant).

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

> **Boundary note (vs. spec 040 `ExternalModel`)**: This `CatalogEntry` is a **pre-import, curation-time recommendation** (a static "shopping list" of vetted models with resource guidance). The spec 040 `ExternalModel` ORM is a **post-import registry record** created when the user actually imports. They share field names (`architecture`, `license`, `tokenizer_family`) by design, but `CatalogEntry` is read-only bundled metadata and `ExternalModel` is mutable DB state. This spec MUST NOT write to `ExternalModel` directly — it only triggers the spec 040 import flow.

### ResourceEnvelope

Documents the resource requirements for running/fine-tuning a model, with per-backend VRAM:

| Field | Type | Description |
|-------|------|-------------|
| `min_ram_gb` | `float` | Minimum system RAM in GB |
| `min_vram_per_backend` | `dict[str, float]` | Per-backend minimum VRAM in GB, keyed by backend name (e.g. `{"cpu": 0, "cuda": 4.0, "mps": 6.0}`) |
| `supported_methods` | `list[str]` | Supported fine-tuning methods (e.g. `["full", "lora"]`) |

`min_vram_per_backend` enables eligibility badges that reflect the running machine's detected device. Detection reuses `detect_gpu()` (`anvil/gpu.py`) for the GPU backend + VRAM (`GpuInfo.memory_total_gb`) and `psutil.virtual_memory().total` for system RAM. A value of `0` for `cpu` means no VRAM requirement (RAM is the binding constraint). On CPU-only hosts the VRAM check is skipped; on MPS, VRAM is approximated by unified system RAM (best-effort).

## Clarifications

### Session 2026-06-28

- Q: What fields comprise CuratedModelCatalog and ResourceEnvelope? → A: Structured JSON schema with backend-specific envelopes per Option B. Fields documented in Key Entities above.
- Q: How is the curated catalog stored and maintained on disk? → A: YAML file (`anvil/data/curated-models.yaml`) loaded at runtime via a Pydantic `CatalogEntry` model. Updates via PR.
- Q: What HF Hub API interaction pattern should the browser use? → A: `huggingface_hub` library (`HfApi.list_models()` / `HfApi.model_info()`) behind `[finetune]` extra, token optional, with a local cache layer.
- Q: What page structure should the HF view use? → A: Standalone page at `/v1/hf-browser` with search bar, catalog/results list, and detail panel on selection.

### Session 2026-06-28 (codebase-verification review)

- Correction: Import API is `workbench.model_imports.submit_import(source, identifier, *, revision, name)` (property is `model_imports`, plural) — NOT `model_import.create_job(hf_id, architecture)`. Architecture is auto-derived by the import service, not passed.
- Correction: An existing `POST /v1/models/import` route (spec 040) already performs imports; the browser reuses it instead of defining a new `/v1/hf-browser/import` endpoint.
- Correction: Allow-list and accepted format reuse spec 040's `_ALLOWED_ARCHITECTURES` / `_ACCEPTED_FORMATS` and the `RunnableStatus` enum — no duplicate constants/enums (Article XI §11.4).
- Correction: Eligibility uses `detect_gpu()` (`anvil/gpu.py`) + `psutil` (core dep), not a non-existent `workbench.compute.device` property; `anvil/services/compute/resolve.py` only returns a device *type*, not RAM/VRAM quantities.
- Correction: PyYAML is only a transitive dep today — must be added to core `[project.dependencies]` (FR-007b).
- Correction: The architecture-differences lesson (spec 049) is not implemented; its link is a forward dependency and must degrade gracefully.

## Definition of Done

- Search→inspect→import works for a catalog model; eligibility badges accurate; offline-safe catalog;
  **NMRG (full)**.

## Assumptions

- Importing delegates entirely to spec 040 via the existing `workbench.model_imports.submit_import(...)`
  service and the existing `POST /v1/models/import` route; this spec owns discovery/UI and the catalog,
  not the registry record or import logic.
- The runnable allow-list and accepted weight format are owned by spec 040; this spec only *displays*
  them and MUST reference the same constants (no copy).
- `psutil` (core dep) and `detect_gpu()` (`anvil/gpu.py`) provide sufficient host-resource detection;
  MPS VRAM is approximated by unified system RAM and eligibility on MPS is best-effort.
- PyYAML will be promoted from transitive to a declared core dependency (FR-007b).
