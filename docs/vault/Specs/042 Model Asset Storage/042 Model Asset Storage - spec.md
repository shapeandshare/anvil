---
title: 042 Model Asset Storage - spec
type: spec
tags:
  - type/spec
  - domain/training
  - domain/content
status: draft
spec-refs:
  - docs/vault/Specs/042 Model Asset Storage/
related:
  - '[[042 Model Asset Storage]]'
  - '[[038 Fine-Tuning Arc]]'
  - '[[Reference/FineTuningArchitectureDecisions]]'
created: '2026-06-28'
updated: '2026-06-28'
---

# Feature Specification: Model Asset Acquisition & Storage (LakeFS-ready)

**Feature Branch**: `042-model-asset-storage`
**Created**: 2026-06-28
**Status**: Draft
**Parent Spec**: [[Specs/038 Fine-Tuning Arc/038 Fine-Tuning Arc|038 Fine-Tuning Arc (umbrella)]]

## Overview

Makes imported models *usable* by downloading and **tracking their assets** (weights, tokenizer, config)
the same way corpora and datasets are tracked. Local mode stores via the existing `FileStore`; SaaS mode
stores via the `VersionedContentStore` (LakeFS, AD-17, spec 019), org-scoped. Downloads are
idempotent/resumable and checksummed; upstream licenses are recorded and respected.

### Scope

| Dimension | Scope |
|-----------|-------|
| **Owned FRs** | FR-010, FR-011, FR-012, FR-013, FR-030 (weight formats), FR-033 (format detection / fail-closed) |
| **Owned decisions** | FT-AD-5 (references AD-17), FT-AD-11 (format aspect) |
| **Depends on** | 040 (`ExternalModel`); storage seam (`anvil/storage/`, `VersionedContentStore`); spec 019 (LakeFS) |
| **Invariant risk** | **LOW–MEDIUM** — reuses storage seam; care that large binaries stream and LakeFS pathing matches spec 019 |

---

## User Story

### US — Learner Acquires and Stores a Model's Assets (Priority: P1)

A learner downloads the weights, tokenizer, and config for an imported model; the assets become managed,
tracked artifacts, and the model's metadata flips to "assets available".

**Independent Test**: For a metadata-only model, click download; verify assets land in the managed store,
checksums recorded, entry shows "assets available"; in SaaS/dev-stack mode, verify objects are written
through `VersionedContentStore` (LakeFS) and org-scoped.

**Acceptance Scenarios**:

1. **Given** a metadata-only model, **When** the learner downloads assets, **Then** weights, tokenizer,
   and config are stored as managed, content-addressed assets and the entry shows "assets available".
2. **Given** SaaS mode, **When** assets are downloaded, **Then** they are written via the
   `VersionedContentStore` (LakeFS) and RBAC-scoped to the org.
3. **Given** an interrupted download, **When** retried, **Then** it resumes/idempotently completes
   without corrupting the tracked entry.
4. **Given** a model whose license forbids redistribution, **When** stored under SaaS, **Then** sharing
   is restricted per the recorded license.

### Edge Cases

- Disk/quota exhaustion mid-download → fail cleanly, mark entry "assets unavailable", leave no partial
  managed artifact.
- Checksum mismatch on a downloaded file → reject and flag corruption, do not mark available.
- Asset already present (content-addressed dedup) → skip re-download, link existing content.
- Unsupported weight format requested (GGUF, `.bin`/`.pt`, GPTQ/AWQ) → refuse before download with a
  clear message naming the format and pointing to the deferred GGUF roadmap (050–052); no partial entry.
- File extension lies about content (e.g. a pickle renamed `.safetensors`) → detection inspects actual
  file structure, not just the extension, and rejects on mismatch.

## Requirements

- **FR-010**: The system MUST download model assets (weights, tokenizer files, config) for an imported
  model on explicit request, storing them as managed, content-addressed assets.
- **FR-011**: Asset storage MUST use the existing storage seam: local `FileStore` in local mode and the
  `VersionedContentStore` (LakeFS, AD-17) in SaaS mode — RBAC-scoped to the owning org in SaaS.
- **FR-012**: Asset download MUST be idempotent/resumable and MUST update the model's metadata entry to
  reflect asset availability and integrity (checksums).
- **FR-013**: The system MUST record and respect each model's upstream license for storage and sharing
  decisions.
- **FR-010a**: Large binary assets MUST be streamed to/from the store, never fully buffered in
  application memory.
- **FR-030**: Asset acquisition MUST accept **safetensors** as the only weight/serialization format in
  v1, and MUST reject PyTorch pickle (`.bin`/`.pt`), GGUF, and pre-quantized GPTQ/AWQ checkpoints with a
  clear, actionable message naming the format and pointing to the deferred GGUF roadmap (specs 050–052).
- **FR-033a**: Loading any imported model MUST run with `trust_remote_code` disabled — only built-in,
  allow-listed architectures (FR-032) are executed, so custom remote modeling code is never fetched or
  run. A model that *requires* remote code is `track-only` (FR-009a), never executed.
- **FR-033**: Asset acquisition MUST **fail closed**: detect declared vs actual format from config and
  on-disk file structure (not the extension alone), verify against the accepted formats (FR-030) and the
  runnable architecture allow-list (FR-032, surfaced from 041) BEFORE any load/store of model weights,
  and record the rejection reason on the model entry. It MUST NEVER best-effort load an unsupported
  format or architecture.

## Success Criteria

- **SC-001**: A learner downloads a model's assets and they are tracked, checksummed, and marked
  available.
- **SC-002**: In SaaS mode the same assets are stored in LakeFS and org-scoped.
- **SC-003**: An interrupted download resumes cleanly with no corruption.
- **SC-004**: An unsupported weight format (GGUF/`.bin`/GPTQ) is refused before download with a clear
  message; a content/extension mismatch is detected and rejected.
- **SC-005 (NMRG)**: Pre-existing tests pass unmodified; local-mode asset storage uses `FileStore` with
  no cloud deps in a base install.

## Key Entities

- **ModelAsset**: a managed, content-addressed artifact (weights/tokenizer/config) belonging to a model.

## Definition of Done

- Download → tracked, checksummed assets; SaaS writes through `VersionedContentStore`; interrupted
  download resumes; licenses recorded/enforced; unsupported formats refused fail-closed with clear
  messaging; **NMRG (full)**.

## Assumptions

- The `VersionedContentStore`/LakeFS substrate from spec 019 / AD-17 is the SaaS storage backend; this
  spec consumes it rather than defining it.
