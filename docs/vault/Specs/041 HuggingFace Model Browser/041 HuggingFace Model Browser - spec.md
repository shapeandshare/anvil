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
| **Depends on** | 040 (import paradigm + `ExternalModel`); HF Hub API (behind `[finetune]` extra) |
| **Invariant risk** | **LOW** — new UI + read-only HF API calls behind the extra |

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

- **FR-007**: The system MUST provide an in-app HuggingFace view to search, browse, and inspect model
  cards, surfacing a curated catalog of very small models (TinyLlama-class) suitable for local
  fine-tuning.
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

- **CuratedModelCatalog**: vetted small models offered for local fine-tuning, with resource envelopes.
- **ResourceEnvelope**: params, min RAM/VRAM, supported methods for a model.

## Definition of Done

- Search→inspect→import works for a catalog model; eligibility badges accurate; offline-safe catalog;
  **NMRG (full)**.

## Assumptions

- Importing delegates entirely to spec 040; this spec owns discovery/UI and the catalog, not the
  registry record.
