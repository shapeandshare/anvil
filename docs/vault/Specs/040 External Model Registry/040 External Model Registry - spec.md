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

Import is async job-based: submitting an import creates a tracking job, the caller polls via the job ID,
and upon completion the metadata entry is created in the registry. The import action is surfaced through
three entry points: a CLI command (`anvil import`), a REST API endpoint (`POST /v1/models/import`), and
a Python SDK method (`client.import_model(...)`). Spec 041 adds the in-app UI on top of the API
endpoint.

### Scope

| Dimension | Scope |
|-----------|-------|
| **Owned FRs** | FR-005, FR-006, FR-009 |
| **Owned decisions** | FT-AD-4 |
| **Depends on** | Model registry (spec 003); `huggingface_hub` (behind `[finetune]` extra) for the HF source |
| **Invariant risk** | **LOW** — all new modules; `huggingface_hub` only touched when a source is queried |

---

## Clarifications

### Session 2026-06-28

- Q: Is re-importing the same source+identifier+revision an error, idempotent, or always-creates? → A: Idempotent — returns existing entry without error.
- Q: What's the minimum viable user-facing entry point for 040? → A: CLI (`anvil import`), REST API endpoint (`POST /v1/models/import`), and Python SDK method (`client.import_model(...)`) — all three.
- Q: How should HF Hub gated (auth-required) models be handled? → A: Optional `HF_TOKEN` env var; if set, used for gated models; otherwise public-only.
- Q: Should import be synchronous or async? → A: Async job-based — creates a tracking job for metadata resolution; caller polls via job ID.
- Q: How should import errors be classified? → A: Rich typed error codes aligned with the HF Hub API error taxonomy (network, auth, rate-limit, not-found, invalid-identifier, parse-failure).

## User Story

### US — Learner Imports an External Model as Tracked Metadata (Priority: P1)

A learner imports a model (from HuggingFace or a local path) and sees a complete, tracked metadata entry
in anvil's registry — without yet downloading gigabytes of weights.

**Independent Test**: Submit an import for a TinyLlama-class model by identifier; verify a job ID is
returned; poll until complete; verify a registry entry is created with all FR-006 fields and marked
"metadata only (assets not downloaded)". Repeat via the local-file source and verify identical tracking.

**Acceptance Scenarios**:

1. **Given** a source identifier, **When** the learner submits an import, **Then** a job is created and a
   job ID is returned immediately.
2. **Given** an in-progress import job, **When** the learner polls the job status, **Then** the status
   reflects progress (queued / resolving / complete / failed).
3. **Given** a completed import job, **When** the learner retrieves the result, **Then** a metadata entry
   is visible with name, source + identifier, architecture family, parameter count, license, tokenizer
   family, and revision SHA, and is marked "metadata only" (no assets).
4. **Given** a local model file/path, **When** imported via the generic source, **Then** it is tracked
   identically to an HF import (source-agnostic).
5. **Given** an already-imported model, **When** re-imported at a different revision, **Then** the
   revision is tracked distinctly (no silent overwrite).
6. **Given** an already-imported model, **When** re-imported at the same revision, **Then** the existing
   entry is returned unchanged (idempotent, not an error).

### Edge Cases

- Source unreachable / rate-limited → fail with a typed error code (`network_error` / `rate_limited`);
  no partial entry.
- Model card missing required fields (e.g., license) → record "unknown" explicitly, flag for review
  (`parse_failure` with details).
- Architecture/tokenizer family unrecognized → tracked but flagged not-runnable (links to 049).
- Gated HF model requiring authentication → if `HF_TOKEN` env var is set, use it; otherwise fail with a
  clear message advising the user to set `HF_TOKEN`.
- Import job fails mid-resolution → job status marked "failed" with a typed error code
  (e.g., `network_error`, `auth_required`, `rate_limited`, `not_found`, `invalid_identifier`,
  `parse_failure`); no partial entry is created; retry allowed.

## Requirements

- **FR-005**: The system MUST support importing external models via a source-agnostic `ModelSource`
  abstraction, with HuggingFace Hub as the first source and local-file/path import as the second.
- **FR-006**: Importing a model MUST create a tracked metadata entry recording at minimum: display name,
  source + source identifier, architecture family, parameter count, license, tokenizer family, and
  revision/commit SHA — created BEFORE any asset download.
- **FR-009**: External-model metadata MUST be tracked in a dedicated `external_models` table,
  alongside anvil's own MLflow-registered models, distinguishable by origin.
- **FR-005a**: `ModelSource` MUST be a structural interface (consistent with the compute-backend
  protocol style) so additional sources can register without changing the registry layer.
- **FR-005b**: The HF Hub source MUST respect the `HF_TOKEN` environment variable when querying gated
  models; if unset, only public models are importable.
- **FR-005c**: Import MUST be async job-based — submitting an import returns a job ID; the caller polls
  for completion; the metadata entry is created only after the job resolves successfully.
- **FR-005d**: Import failures MUST use typed error codes aligned with the HF Hub API error taxonomy
  (`network_error`, `auth_required`, `rate_limited`, `not_found`, `invalid_identifier`,
  `parse_failure`). The job status records the error code and a human-readable message.
- **FR-006a**: Re-importing the same model at a different revision MUST create a distinct, linkable
  version rather than overwriting prior metadata. Re-importing the same source+identifier+revision
  MUST be idempotent (return existing entry, not an error).
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

- Import creates a tracking job that, on completion, produces a metadata entry (FR-006 fields) before
  download; job polling works end-to-end; ≥2 source implementations; origin-distinguishable registry
  listing; import available via CLI (`anvil import`), REST API (`POST /v1/models/import`), and Python
  SDK (`client.import_model(...)`); **NMRG (full)**.

## Assumptions

- Asset download is a separate, explicit step (spec 042).
- Local-eligibility determination and the curated catalog live in spec 041.
