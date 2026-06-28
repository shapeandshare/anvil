---
title: 051 GGUF Export - spec
type: spec
tags:
  - type/spec
  - domain/training
  - domain/mlops
status: draft
spec-refs:
  - docs/vault/Specs/051 GGUF Export/
related:
  - '[[051 GGUF Export]]'
  - '[[038 Fine-Tuning Arc]]'
  - '[[Reference/FineTuningArchitectureDecisions]]'
created: '2026-06-28'
updated: '2026-06-28'
---

# Feature Specification: GGUF Export

**Feature Branch**: `051-gguf-export`
**Created**: 2026-06-28
**Status**: Draft
**Parent Spec**: [[Specs/038 Fine-Tuning Arc/038 Fine-Tuning Arc|038 Fine-Tuning Arc (umbrella)]]

> [!NOTE] Deferred — later priority (FT-AD-11)
> GGUF is committed but deferred. This spec is authored now to scope the direction; it is sequenced
> after the v1 arc (039–049) and is not required for any v1 success criterion.

## Overview

Lets a learner **export** anvil models to GGUF so they can be run in the broader llama.cpp ecosystem
(e.g. local desktop inference, Ollama, etc.). Covers exporting both anvil-compatible model weights and
**merged** fine-tuned models (consuming 045's adapter→standalone merge), including quantization choices.
Complements 050 (import/run) and 052 (fine-tune).

### Scope

| Dimension | Scope |
|-----------|-------|
| **Owned FRs** | FR-001..FR-004 (spec-local) |
| **Owned decisions** | FT-AD-11 (GGUF roadmap) |
| **Depends on** | 045 (merge/export pathway), 042 (asset storage); GGUF conversion tooling behind the `[gguf]` extra |
| **Invariant risk** | **LOW** — additive export path behind the extra; existing export (safetensors) unchanged |

---

## User Story

### US — Learner Exports a Model to GGUF (Priority: Later/P1-within-deferred)

A learner exports a fine-tuned (merged) model to a GGUF file at a chosen quantization and uses it
outside anvil.

**Independent Test**: Merge an adapter into standalone weights (045), export to GGUF at a chosen
quantization, and load the produced file in an external llama.cpp-based runner.

**Acceptance Scenarios**:

1. **Given** a merged/standalone model, **When** the learner exports to GGUF, **Then** a valid GGUF file
   is produced at the selected quantization and registered with lineage.
2. **Given** an architecture supported for conversion, **When** export runs, **Then** the GGUF loads in a
   standard llama.cpp-based runtime.
3. **Given** an architecture not supported for GGUF conversion, **When** export is attempted, **Then** it
   fails fast with a clear message.

### Edge Cases

- Adapter not yet merged → require merge first (links 045) or merge as part of export.
- Requested quantization unsupported for the architecture → fail fast naming valid options.
- Char-level native anvil model → out of scope / flagged (GGUF targets the external-family models).

## Requirements (spec-local)

- **FR-001**: The system MUST export eligible models (merged/standalone, allow-list architectures) to
  valid GGUF files at a selectable quantization.
- **FR-002**: Exported GGUF artifacts MUST be registered with lineage to their source model/adapter and
  tracked through asset storage (042), including LakeFS in SaaS.
- **FR-003**: GGUF conversion tooling MUST live behind the `[gguf]` extra; absence MUST fail fast and not
  be importable in a base install.
- **FR-004**: Unsupported architecture/quantization combinations MUST fail fast with actionable
  messaging; the existing safetensors export path MUST be unchanged.

## Success Criteria

- **SC-001**: A learner exports a merged model to GGUF and runs it in an external llama.cpp runtime.
- **SC-002**: Exported GGUF is registered with lineage and tracked as an asset.
- **SC-003 (NMRG)**: Existing safetensors export and the base install are unchanged; pre-existing tests
  pass unmodified.

## Key Entities

- **GGUFArtifact**: an exported GGUF file with quantization + lineage metadata.

## Definition of Done

- Merge→GGUF export produces a loadable file at a chosen quantization, registered with lineage; `[gguf]`
  extra fail-fast; **NMRG (full)**.

## Assumptions

- Import/run (050) and fine-tuning (052) are separate specs; this spec only exports.
- Reuses 045's merge so adapters become standalone weights before conversion.
