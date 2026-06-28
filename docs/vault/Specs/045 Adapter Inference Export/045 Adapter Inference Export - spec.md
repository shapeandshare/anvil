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

## Requirements

- **FR-020**: A fine-tune run MUST be able to return a LoRA adapter artifact distinct from full weights;
  `ComputeResult` MUST represent base+adapter as a first-class result shape.
- **FR-021**: Inference MUST compose a base model with its adapter at load time; the system MUST support
  optionally merging an adapter into standalone weights and exporting the result.
- **FR-021a**: A merged/exported artifact MUST be registered with lineage to its base model and adapter.

## Success Criteria

- **SC-001**: Base + adapter generates fine-tuned samples via the inference service.
- **SC-002**: Merge + export yields a standalone artifact that runs without the adapter attached.
- **SC-003**: `ComputeResult` represents base+adapter explicitly across local and remote runs.
- **SC-004 (NMRG)**: Pre-existing tests pass unmodified; base install unaffected.

## Key Entities

- **Adapter**: LoRA delta artifact, linked to its base model.
- **ComputeResult (adapter shape)**: normalized result carrying base ref + adapter (vs full weights).

## Definition of Done

- Base+adapter inference works; merge+export produces a registered standalone artifact with lineage;
  result shape normalized local vs remote; **NMRG (full)**.

## Assumptions

- Adapters are produced by spec 044; this spec consumes, runs, merges, and exports them.
