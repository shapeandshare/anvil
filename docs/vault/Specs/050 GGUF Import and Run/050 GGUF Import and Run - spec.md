---
title: 050 GGUF Import and Run - spec
type: spec
tags:
  - type/spec
  - domain/training
  - domain/mlops
status: draft
spec-refs:
  - docs/vault/Specs/050 GGUF Import and Run/
related:
  - '[[050 GGUF Import and Run]]'
  - '[[038 Fine-Tuning Arc]]'
  - '[[Reference/FineTuningArchitectureDecisions]]'
created: '2026-06-28'
updated: '2026-06-28'
---

# Feature Specification: GGUF Import & Run

**Feature Branch**: `050-gguf-import-and-run`
**Created**: 2026-06-28
**Status**: Draft
**Parent Spec**: [[Specs/038 Fine-Tuning Arc/038 Fine-Tuning Arc|038 Fine-Tuning Arc (umbrella)]]

> [!NOTE] Deferred — later priority (FT-AD-11)
> GGUF is a **committed but deferred** first-class type. v1 of the Fine-Tuning Arc (039–049) rejects
> GGUF on import (FR-030). This spec is authored now to commit the direction and scope; it is sequenced
> **after** the v1 arc and is not required for any v1 success criterion. Promote from deferred to
> active when the v1 arc has shipped.

## Overview

Makes GGUF a recognized, runnable type: import a GGUF model (from HuggingFace or a local file) as a
tracked model, and run inference on it. GGUF comes from the llama.cpp ecosystem and needs a **different
runtime** than `transformers`/`peft` — so this introduces a GGUF inference backend behind the existing
inference/compute seams, gated by a new optional extra. It reuses the import paradigm (040), asset
storage (042), and the architecture/format gating (FT-AD-11) — extending the accepted-format set to
include GGUF once this ships.

### Scope

| Dimension | Scope |
|-----------|-------|
| **Owned FRs** | FR-001..FR-005 (spec-local) |
| **Owned decisions** | FT-AD-11 (GGUF roadmap), reuses FT-AD-4/FT-AD-5/FT-AD-7 |
| **Depends on** | 040 (import), 042 (assets); a GGUF runtime (e.g. `llama-cpp-python`) behind a new `[gguf]` extra |
| **Invariant risk** | **LOW** — new backend + extra; v1 paths and the dependency-free base install are untouched |

---

## User Story

### US — Learner Imports and Runs a GGUF Model (Priority: Later/P1-within-deferred)

A learner imports a GGUF model and generates text from it inside anvil.

**Independent Test**: Import a small GGUF model, download its asset, and run inference producing text —
verifying the GGUF runtime is used and the model is tracked like any other.

**Acceptance Scenarios**:

1. **Given** a GGUF model identifier or file, **When** the learner imports it, **Then** a tracked
   metadata entry is created (reusing 040), recording the GGUF format and quantization.
2. **Given** an imported GGUF model with assets, **When** the learner runs inference, **Then** the GGUF
   runtime backend generates text and samples appear in the UI.
3. **Given** the `[gguf]` extra is absent, **When** a GGUF run is attempted, **Then** the system fails
   fast with an install hint, never silently degrading.
4. **Given** GGUF support is shipped, **When** a GGUF asset is acquired, **Then** the format gate
   (FR-030/FR-033) accepts GGUF instead of rejecting it.

### Edge Cases

- Unsupported GGUF quantization level → fail fast naming the unsupported quant.
- Embedded GGUF tokenizer differs from the abstraction's expectations → handled by the GGUF runtime,
  recorded as its own tokenizer-serialization variant (extends 043).
- Very large GGUF beyond local memory → guided to a larger/SaaS path (consistent with FT-AD-8 envelope).

## Requirements (spec-local)

- **FR-001**: The system MUST import GGUF models via the existing `ModelSource` paradigm (040),
  recording GGUF format + quantization metadata.
- **FR-002**: The system MUST provide a GGUF inference backend (separate runtime from
  `transformers`/`peft`) integrated behind the existing inference/compute seam.
- **FR-003**: GGUF runtime dependencies MUST live in a new optional `[gguf]` extra; absence MUST fail
  fast and MUST NOT be importable in a base install.
- **FR-004**: When this ships, the format gate (FR-030/FR-033) MUST be extended to accept GGUF (declared
  vs actual detection) rather than reject it.
- **FR-005**: GGUF assets MUST be tracked through the same governance/storage as other model assets
  (042), including under LakeFS in SaaS.

## Success Criteria

- **SC-001**: A learner imports a GGUF model and generates text from it within anvil.
- **SC-002**: Missing `[gguf]` extra fails fast with an install hint.
- **SC-003 (NMRG)**: v1 arc behavior and the base install are unchanged; pre-existing tests pass
  unmodified.

## Key Entities

- **GGUFModel**: a tracked model whose weight format is GGUF (with quantization metadata).
- **GGUFRuntimeBackend**: the inference backend executing GGUF models.

## Definition of Done

- Import → run inference on a GGUF model; `[gguf]` extra fail-fast; format gate accepts GGUF; **NMRG
  (full)**.

## Assumptions

- Export to GGUF (051) and fine-tuning GGUF (052) are separate specs; this spec only imports and runs.
- A maintained GGUF runtime (e.g. `llama-cpp-python`) is available as an optional dependency.
