---
title: 040 External Model Registry - spec
type: spec
tags:
  - type/spec
  - domain/training
  - domain/tracking
status: draft
spec-refs:
  - docs/vault/Specs/040 External Model Registry/
related:
  - '[[040 External Model Registry]]'
  - '[[038 Fine-Tuning Arc]]'
  - '[[Reference/FineTuningArchitectureDecisions]]'
created: '2026-06-28'
updated: '2026-06-28'
---

# Feature Specification: External Model Registry & Import Paradigm

**Feature Branch**: `040-external-model-registry`
**Created**: 2026-06-28
**Status**: Draft
**Parent Spec**: [[Specs/038 Fine-Tuning Arc/038 Fine-Tuning Arc|038 Fine-Tuning Arc (umbrella)]]

## Overview

The foundation of Track B: a **source-agnostic** way to bring external models into anvil as tracked
metadata entries. Importing creates a registry record (name, source, architecture family, parameter
count, license, tokenizer family, revision SHA) **before** any weights are downloaded. HuggingFace Hub
is the first source; a generic local-file/path source is the second.

### Scope

| Dimension | Scope |
|-----------|-------|
| **Owned FRs** | FR-005, FR-006, FR-009 |
| **Owned decisions** | FT-AD-4 |
| **Depends on** | Model registry (spec 003); `huggingface_hub` (behind `[finetune]` extra) for the HF source |
| **Invariant risk** | **LOW** — all new modules; `huggingface_hub` only touched when a source is queried |

---

## User Story

### US — Learner Imports an External Model as Tracked Metadata (Priority: P1)

A learner imports a model (from HuggingFace or a local path) and sees a complete, tracked metadata entry
in anvil's registry — without yet downloading gigabytes of weights.

**Independent Test**: Import a TinyLlama-class model by identifier; verify a registry entry is created
with all FR-006 fields and marked "metadata only (assets not downloaded)". Repeat via the local-file
source and verify identical tracking.

**Acceptance Scenarios**:

1. **Given** a source identifier, **When** the learner imports, **Then** a metadata entry is created
   with name, source + identifier, architecture family, parameter count, license, tokenizer family, and
   revision SHA.
2. **Given** an import, **When** it completes, **Then** the entry is marked "metadata only" (no assets).
3. **Given** a local model file/path, **When** imported via the generic source, **Then** it is tracked
   identically to an HF import (source-agnostic).
4. **Given** an already-imported model, **When** re-imported at a different revision, **Then** the
   revision is tracked distinctly (no silent overwrite).

### Edge Cases

- Source unreachable / rate-limited → fail gracefully with a retryable error; no partial entry.
- Model card missing required fields (e.g., license) → record "unknown" explicitly, flag for review.
- Architecture/tokenizer family unrecognized → tracked but flagged not-runnable (links to 049).

## Requirements

- **FR-005**: The system MUST support importing external models via a source-agnostic `ModelSource`
  abstraction, with HuggingFace Hub as the first source and local-file/path import as the second.
- **FR-006**: Importing a model MUST create a tracked metadata entry recording at minimum: display name,
  source + source identifier, architecture family, parameter count, license, tokenizer family, and
  revision/commit SHA — created BEFORE any asset download.
- **FR-009**: External-model metadata MUST be tracked in the existing model registry alongside anvil's
  own trained models (extending spec 003), distinguishable by origin.
- **FR-005a**: `ModelSource` MUST be a structural interface (consistent with the compute-backend
  protocol style) so additional sources can register without changing the registry layer.
- **FR-006a**: Re-importing the same model at a different revision MUST create a distinct, linkable
  version rather than overwriting prior metadata.
- **FR-009a**: Each metadata entry MUST record a **runnable status** derived from the weight format
  (FR-030) and architecture allow-list (FR-032): `runnable` or `track-only` (with a reason). This flag
  is the single source of truth that downstream features (041 display, 044 fine-tune, 045 inference)
  consult to enable or refuse execution — so allow-list enforcement is recorded once, not re-derived.

## Success Criteria

- **SC-001**: A learner imports a TinyLlama-class model and sees a complete metadata entry before any
  weights download.
- **SC-002**: The source abstraction has ≥2 working implementations (HF Hub, local file).
- **SC-003**: External and native models are both visible in the registry, distinguishable by origin.
- **SC-004 (NMRG)**: Pre-existing tests pass unmodified; base install imports no `huggingface_hub`.

## Key Entities

- **ExternalModel**: tracked metadata record (name, source+id, architecture family, params, license,
  tokenizer family, revision SHA, asset availability, local-eligibility, **runnable status**
  (`runnable`/`track-only` + reason)).
- **ModelSource**: abstraction over where a model comes from (HF Hub, local path, future sources).

## Definition of Done

- Import creates a complete metadata entry (FR-006 fields) before download; ≥2 source implementations;
  origin-distinguishable registry listing; **NMRG (full)**.

## Assumptions

- Asset download is a separate, explicit step (spec 042).
- Local-eligibility determination and the curated catalog live in spec 041.
