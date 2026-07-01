---
title: 045 Adapter Inference Export - spec
type: spec
tags:
  - type/spec
  - domain/training
  - domain/mlops
status: draft
spec-refs:
  - docs/vault/Specs/045 Adapter Inference Export/
related:
  - '[[045 Adapter Inference Export]]'
  - '[[038 Fine-Tuning Arc]]'
  - '[[Reference/FineTuningArchitectureDecisions]]'
created: '2026-06-28'
updated: '2026-06-28'
---

# Feature Specification: Adapter Inference, Merge & Export

**Feature Branch**: `045-adapter-inference-export`
**Created**: 2026-06-28
**Status**: Draft
**Parent Spec**: [[Specs/038 Fine-Tuning Arc/038 Fine-Tuning Arc|038 Fine-Tuning Arc (umbrella)]]

## Overview

Closes the loop on external fine-tuning: represent a LoRA **adapter** as a first-class result shape,
run inference by composing base + adapter at load time, and optionally **merge** an adapter into
standalone weights and **export** it. Extends `ComputeResult` (which already normalizes local-model vs
remote-artifact) with a third "base + adapter" shape, and extends the inference service.

### Scope

| Dimension | Scope |
|-----------|-------|
| **Owned FRs** | FR-020, FR-021 |
| **Owned decisions** | FT-AD-7 |
| **Depends on** | 044 (produces adapters); `anvil/services/compute/result.py`; inference service; export (`anvil/services/training/export.py`) |
| **Out of scope** | Adapter comparison/diff; non-LoRA adapter types (DoRA, IA3, etc.) |
| **Invariant risk** | **LOW** — additive result shape and inference path |

---

## User Story

### US — Learner Runs, Merges, and Exports a Fine-Tuned Model (Priority: P2)

A learner generates samples from a fine-tuned model (base + adapter), optionally merges the adapter into
standalone weights, and exports the result so it runs without the adapter attached.

**Independent Test**: Load a base model plus its adapter, generate text reflecting the fine-tuning, then
merge+export and verify the exported artifact runs standalone.

**Acceptance Scenarios**:

1. **Given** a base model and adapter, **When** the learner runs inference, **Then** the adapter is
   composed onto the base at load time and samples reflect the fine-tuning.
2. **Given** an adapter, **When** the learner merges and exports, **Then** a standalone weights artifact
   is produced and registered.
3. **Given** a `ComputeResult` from a PEFT run, **When** it is consumed downstream, **Then** the
   base+adapter shape is represented explicitly (not coerced into monolithic weights).

### Edge Cases

- Adapter and base mismatch (different base model) → reject composition with a clear error.
- Merge requested for a quantized base → handle dtype/precision correctly or fail fast with guidance.
- Export of a license-restricted base → respect the recorded license (links 042/040).
- Requested `adapter_id` does not exist for the given base model → clear error message.
- Merge or export failure mid-operation → clean up partial output atomically; no partial artifact left behind.

## Requirements

- **FR-020**: A fine-tune run MUST be able to return a LoRA adapter artifact distinct from full weights;
  `ComputeResult` MUST represent base+adapter as a first-class result shape.
- **FR-021**: Inference MUST compose a base model with a named adapter at load time (adapter selected by
  `adapter_id`); the system MUST support optionally merging an adapter into standalone weights and
  exporting the result. Merge+export MUST fail atomically — no partial artifact on failure.
- **FR-021a**: A merged/exported artifact MUST be registered as a new standalone model with full lineage
  to its base model (`external_model_id`) and the adapter (identified by the existing scoped key
  `(external_model_id, adapter_id)`) that was merged. The adapter artifact MUST persist as a distinct entity.

## Success Criteria

- **SC-001**: Base + adapter generates fine-tuned samples via the inference service.
- **SC-002**: Merge + export yields a standalone artifact that runs without the adapter attached.
- **SC-003**: `ComputeResult` represents base+adapter explicitly across local and remote runs.
- **SC-004 (NMRG)**: Pre-existing tests pass unmodified; base install unaffected.

## Key Entities

- **Adapter**: LoRA delta artifact, linked to its base model. Identified by the existing scoped key
  `(external_model_id, adapter_id)` on the `LoRAAdapter` ORM (spec 044) — `adapter_id` is auto-generated
  as `run_{run_id}` and unique within a base model. There is **no separate `version` column**; multiple
  adapters per base model are distinguished by distinct `adapter_id` values. Inference selects by
  `adapter_id` — no default fallback. Lifecycle:
  `created → (inference) → (merge+export) [adapter persists as distinct artifact]`.
- **Standalone Model**: Output of merge+export — a new registered model with full lineage
  to its base model and the adapter that was merged. Removes the adapter dependency.
- **ComputeResult (adapter shape)**: normalized result carrying base ref + adapter (vs full weights).

## Definition of Done

- Base+adapter inference works; merge+export produces a registered standalone artifact with lineage;
  result shape normalized local vs remote; **NMRG (full)**.

## Assumptions

- Adapters are produced by spec 044; this spec consumes, runs, merges, and exports them.

## Pre-Existing State (verified against codebase 2026-07-01)

Spec 044 already delivered infrastructure this spec builds ON — the following EXIST and are MODIFIED, not created:

- **`POST /v1/inference/generate`** (`anvil/api/v1/inference.py:362`) — fully wired, accepts `adapter_id`,
  calls `InferenceService.load_model(model_id, adapter_id)` then `generate()`. **Gap**: `load_model()`
  only resolves the adapter *path* (`_resolve_adapter_path`); it does **not** compose the adapter, and
  `generate()` ignores `adapter_path` entirely. Adapter composition is the real work of FR-021 inference.
- **`GET/POST /v1/models/{model_id}/adapters...`** (`anvil/api/v1/adapters.py`) — list, detail (404 with
  available IDs), and `POST .../{adapter_id}/merge` all exist.
- **`AdapterMergeService.merge()`** (`anvil/services/training/merge_service.py`) — currently **destructive**
  (deletes adapter files, sets `merged_at`). FR-021a requires making this **non-destructive**.
- **`AdapterMergeService` constructor** takes only `(LoRAAdapterRepository, LocalFileStore)` and is
  instantiated inline in the route (NOT exposed on `AnvilWorkbench`). Adding lineage registration
  (FR-021a) requires injecting a `TrackingService` dependency and wiring it.
- **`ExternalModel.license`** is a direct column (not `metadata["license"]`) — use it for license checks.
- **`LlamaModel.load(path)`** takes a filesystem path, not a weights dict — HF→anvil conversion must
  write a temp JSON file (or add a new `from_weights_dict` factory).

## Clarifications

### Session 2026-07-01

- Q: How should a LoRA adapter be uniquely identified — by run ID alone, or by a composite key? → A: Scoped key `(external_model_id, adapter_id)` on the existing `LoRAAdapter` ORM (spec 044); `adapter_id` = `run_{run_id}`, unique within a base model. No separate `version` column — multiple adapters per base are distinguished by distinct `adapter_id`.
- Q: Should inference support loading a specific adapter by name, or one adapter per base? → A: Inference selects adapter by name — user specifies which to compose; no default.
- Q: Does merge+export consume the adapter or produce a new standalone model? → A: Adapter persists; merge+export creates a new standalone registered model with full lineage `(base, adapter)`.
- Q: Which should be declared out-of-scope? → A: Adapter comparison/diff and non-LoRA adapter types (DoRA, IA3) are out-of-scope.
- Q: How should partial or failed merge+export be handled? → A: Atomic failure — clean up partial output and report the error.
