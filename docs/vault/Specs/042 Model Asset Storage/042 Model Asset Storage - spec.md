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
the same way corpora and datasets are tracked. Assets are immutable, content-addressed blobs stored
through the existing `FileStore` seam: `LocalFileStore` in local mode, and a LakeFS-backed `FileStore`
(AD-17, spec 019) injected by the workbench in SaaS mode, org-scoped. Downloads are
idempotent/resumable and SHA-256-checksummed; upstream licenses are recorded and respected.

> **Note on storage abstraction**: model assets use `FileStore` (blob storage), not the
> `VersionedContentStore` (which serves versioned *corpora* with staging/manifests/lineage). Assets are
> already content-addressed by `sha256` and immutable, so the heavier versioned-content machinery is
> unnecessary (Article XI — Simplicity First).

This spec builds directly on spec 040 (`ExternalModel` registry): a model entry begins life as
`METADATA_ONLY` and this feature transitions it through `ASSETS_PENDING` to `ASSETS_AVAILABLE`
(reusing the existing `AssetState` enum on `ExternalModel.asset_availability`). The new per-file
`ModelAsset` rows track the finer-grained lifecycle of each individual asset file.

### Scope

| Dimension | Scope |
|-----------|-------|
| **Owned FRs** | FR-010, FR-010a, FR-010b, FR-010c, FR-010d, FR-010e, FR-011, FR-011a, FR-012, FR-012a, FR-012b, FR-013, FR-030 (weight formats), FR-033 (format detection / fail-closed) |
| **Owned decisions** | FT-AD-5 (references AD-17), FT-AD-11 (format aspect) |
| **Referenced (not owned)** | FR-032 (architecture allow-list, from 041), FR-009a (`track-only` rule, from 040) |
| **Depends on** | 040 (`ExternalModel`, `AssetState`); the `FileStore` seam (`anvil/storage/`); spec 019 (LakeFS substrate for the SaaS-backed `FileStore`) |
| **In scope now** | Local-mode download + storage via `LocalFileStore`; honouring the SaaS storage *seam* (write through whichever `FileStore` the workbench injects, at the org-prefixed path) |
| **Deferred** | The concrete LakeFS-backed `FileStore` implementation and org-scoped RBAC enforcement are owned by spec 019 / the SaaS track; this spec only ensures the seam is honoured |
| **Invariant risk** | **LOW–MEDIUM** — reuses storage seam; care that large binaries stream and LakeFS pathing matches spec 019 |

---

## User Story

### US — Learner Acquires and Stores a Model's Assets (Priority: P1)

A learner downloads the weights, tokenizer, and config for an imported model; the assets become managed,
tracked artifacts, and the model's metadata flips to "assets available".

**Independent Test**: For a metadata-only model, request download; verify assets land in the managed
store, SHA-256 checksums are recorded, and the model entry's `asset_availability` transitions
`METADATA_ONLY → ASSETS_PENDING → ASSETS_AVAILABLE`. Verify the service writes through the injected
`FileStore` seam (a stub/spy `FileStore` confirms the write path is honoured without a live LakeFS).

**Acceptance Scenarios**:

1. **Given** a metadata-only model, **When** the learner downloads assets, **Then** weights, tokenizer,
   and config are stored as managed, content-addressed assets, per-file SHA-256 hashes are recorded, and
   `asset_availability` becomes `ASSETS_AVAILABLE`.
2. **Given** the workbench is configured with a SaaS `FileStore` (the spec-019 LakeFS seam), **When**
   assets are downloaded, **Then** they are written through that `FileStore` at the org-prefixed path
   (`orgs/{org_id}/models/{model_id}/assets/{sha256}/{filename}`) — without this spec re-implementing
   the LakeFS backend.
3. **Given** an interrupted download, **When** retried, **Then** it resumes/idempotently completes
   without corrupting the tracked entry, and partially-downloaded assets resume from `downloaded_bytes`.
4. **Given** a model whose license forbids redistribution, **When** its assets are stored, **Then** the
   recorded `license` is preserved on the entry so downstream sharing decisions (SaaS, future) can
   enforce the restriction.

### Edge Cases

- Disk/quota exhaustion mid-download → fail cleanly, mark the affected `ModelAsset` as `UNAVAILABLE`,
  revert the model's `asset_availability` to `METADATA_ONLY`, and leave no partial managed artifact.
- Checksum mismatch on a downloaded file → set that `ModelAsset` to `CHECKSUM_MISMATCH`, discard the
  downloaded bytes, and do not mark the model `ASSETS_AVAILABLE`.
- Asset already present (content-addressed dedup) → skip re-download, link existing content by `sha256`.
- Sharded weights (e.g. `model-00001-of-00002.safetensors` + `model.safetensors.index.json`) → create
  one `ModelAsset` (type `WEIGHTS`) per shard plus the index file; the model is `ASSETS_AVAILABLE` only
  when **all** shards and the index reach `AVAILABLE`.
- Unsupported weight format requested (GGUF, `.bin`/`.pt`, GPTQ/AWQ) → refuse before download with a
  clear message naming the format and pointing to the deferred GGUF roadmap (050–052); no partial entry.
- File extension lies about content (e.g. a pickle renamed `.safetensors`) → detection inspects actual
  file structure, not just the extension, and rejects on mismatch.
- Duplicate download request for the same model while already in progress → reject with a clear
  message referencing the in-flight job; do not enqueue a second job.
- Gated model download with no HF token configured → fail with an actionable message directing the
  user to configure their HF token (via Settings UI or `HF_TOKEN` env var).
- Model is `track-only` (FR-009a — requires remote code or a non-allow-listed architecture) → refuse
  the download entirely; track-only models are never fetched or executed.

## Requirements

### Acquisition & Download

- **FR-010**: The system MUST download model assets (weights, tokenizer files, config) for an imported
  model on explicit request, storing them as managed, content-addressed assets.
- **FR-010a**: Large binary assets MUST be streamed to/from the store, never fully buffered in
  application memory.
- **FR-010b**: Asset download MUST be an async background job — the API endpoint returns a job ID
  immediately; the client polls for completion status. Consistent with existing job infrastructure
  (training jobs, model import).
- **FR-010c**: Concurrent downloads of the same model MUST be prevented via a model-level lock (one
  in-flight download per model at a time). Different models may download in parallel. In SaaS mode,
  a per-org throttled pool (max 3 concurrent downloads) wraps the model-level lock to bound
  resource contention across orgs.
- **FR-010d**: Downloading gated model assets from HuggingFace requires an auth token. The system MUST
  support two mechanisms: (1) a persisted `UserSecret` entry (DB-stored, encrypted, per-user) set via
  the UI, and (2) the `HF_TOKEN` environment variable as fallback. The service resolves token as:
  `UserSecret > HF_TOKEN env var > fail with actionable message if model is gated`.
- **FR-010e**: Progress MUST be reported per-asset via `ModelAsset.status` transitions. The background
  job updates each asset's status from `PENDING → DOWNLOADING → AVAILABLE` (or `CHECKSUM_MISMATCH` /
  `UNAVAILABLE` on failure). Each asset tracks `size_bytes` (total) and `downloaded_bytes` for byte-level
  progress. The job-status API endpoint returns the aggregate: total assets, completed count, per-asset
  detail. The client polls this endpoint rather than receiving push notifications; no new SSE channel
  is introduced.

### Storage

- **FR-011**: Asset storage MUST use the existing storage seam — the `FileStore` abstraction
  (`anvil/storage/`). In local mode this is `LocalFileStore`; in SaaS mode the workbench injects the
  LakeFS-backed `FileStore` (spec 019, AD-17). This spec MUST NOT re-implement the LakeFS backend; it
  consumes whichever `FileStore` the workbench provides.
- **FR-011a**: Asset storage paths MUST follow the hybrid pattern
  `models/{model_id}/assets/{sha256}/{filename}` — model-scoped for traceability and content-hash-based
  for dedup. In SaaS mode the path is prefixed by `orgs/{org_id}/` per the LakeFS convention.

### Tracking & Integrity

- **FR-012**: Asset download MUST be idempotent/resumable. On retry, a partially-downloaded asset MUST
  resume from its recorded `downloaded_bytes` rather than restarting; an already-`AVAILABLE` asset MUST
  be skipped.
- **FR-012a**: For every downloaded file, the system MUST compute a SHA-256 hash during streaming and
  verify it before marking the `ModelAsset` `AVAILABLE`. The hash is recorded in `ModelAsset.sha256` and
  used as the content-address path segment (FR-011a). A mismatch MUST set the asset to
  `CHECKSUM_MISMATCH` and MUST NOT mark the model available.
- **FR-012b**: The model-level `ExternalModel.asset_availability` field (existing `AssetState` enum)
  MUST transition `METADATA_ONLY → ASSETS_PENDING` when a download job starts, to `ASSETS_AVAILABLE`
  only when **all** of the model's `ModelAsset` rows reach `AVAILABLE`, and back to `METADATA_ONLY` if
  the job fails leaving no usable asset set.
- **FR-013**: The system MUST record each model's upstream `license` (already captured at import, spec
  040) and preserve it on the entry so storage and downstream sharing decisions can respect it.
  Enforcement of sharing restrictions is a SaaS concern (deferred); this spec guarantees the license is
  recorded and available.

### Format Safety (fail-closed)

- **FR-030**: Asset acquisition MUST accept **safetensors** as the only weight/serialization format in
  v1, and MUST reject PyTorch pickle (`.bin`/`.pt`), GGUF, and pre-quantized GPTQ/AWQ checkpoints with a
  clear, actionable message naming the format and pointing to the deferred GGUF roadmap (specs 050–052).
- **FR-033**: Asset acquisition MUST **fail closed**: detect declared vs actual format from config and
  on-disk file structure (not the extension alone), verify against the accepted formats (FR-030) and the
  runnable architecture allow-list (FR-032, surfaced from 041) BEFORE any load/store of model weights,
  and record the rejection reason on the model entry. It MUST NEVER best-effort load an unsupported
  format or architecture.
- **FR-033a**: Loading any imported model MUST run with `trust_remote_code` disabled — only built-in,
  allow-listed architectures (FR-032, from 041) are executed, so custom remote modeling code is never
  fetched or run. A model that *requires* remote code is `track-only` (FR-009a, from 040) and its assets
  MUST NOT be downloaded or executed.

## Success Criteria

- **SC-001**: A learner downloads a model's assets; each file is tracked with a SHA-256 hash, and the
  model's `asset_availability` transitions to `ASSETS_AVAILABLE`.
- **SC-002**: When the workbench is configured with a SaaS `FileStore`, assets are written through that
  seam at the org-prefixed content-addressed path — verified with a spy/stub `FileStore` (the concrete
  LakeFS backend is exercised by spec 019, not here).
- **SC-003**: An interrupted download resumes cleanly from `downloaded_bytes` with no corruption.
- **SC-004**: An unsupported weight format (GGUF/`.bin`/GPTQ) is refused before download with a clear
  message; a content/extension mismatch is detected and rejected.
- **SC-005 (NMRG)**: Pre-existing tests pass unmodified; local-mode asset storage uses `FileStore` with
  no cloud deps in a base install.
- **SC-006**: A failed download leaves no partial managed artifact and reverts `asset_availability` to
  `METADATA_ONLY`; the model remains in a clean, re-downloadable state.

## Clarifications

### Session 2026-06-28

- Q: How are ModelAsset entities modeled in the DB? → A: Separate ModelAsset SQLAlchemy model.
- Q: Sync or async download? → A: Async background job.
- Q: Storage pathing scheme for assets? → A: Hybrid — `models/{model_id}/assets/{sha256}/{filename}`.
- Q: Concurrent download handling across modes? → A: Local = model-level lock; SaaS = per-org throttled pool (max 3) + model-level lock.
- Q: How are HF tokens for gated models managed? → A: New UserSecret model (DB, encrypted) + HF_TOKEN env var fallback.
- Q: How is download progress reported to the user? → A: Per-asset ModelAsset.status driving aggregate progress via job-status polling.

### Session 2026-06-28 (critical review)

- Corrected UserSecret encryption: AES-256-GCM via `cryptography` (NOT a "secrets-based approach"; `secrets` is key-gen only).
- Integrated the existing `AssetState` enum: added FR-012b for `ExternalModel.asset_availability` transitions (`METADATA_ONLY → ASSETS_PENDING → ASSETS_AVAILABLE`).
- Fixed terminology drift `total_bytes` → `size_bytes`.
- Reordered FRs into Acquisition / Storage / Tracking / Format-Safety groups; FR-033 now precedes FR-033a.
- Added FR-012a (explicit SHA-256 compute + verify) and SC-006 (clean failure / revert).
- Added edge cases for sharded weights and track-only models; fixed "assets unavailable" → revert to `METADATA_ONLY`.
- Clarified SaaS scope: consume the `FileStore` seam now; LakeFS backend deferred to spec 019.

## Key Entities

- **ModelAsset**: a managed, content-addressed artifact (one weight shard, tokenizer file, or config
  file) belonging to a model. One row per file. Represented as a separate SQLAlchemy model:
  - `id` — primary key
  - `external_model_id` — foreign key to `ExternalModel` (ON DELETE CASCADE)
  - `asset_type` — enum (`WEIGHTS`, `TOKENIZER`, `CONFIG`)
  - `filename` — original filename (e.g. `model-00001-of-00002.safetensors`, `config.json`)
  - `storage_path` — relative path within the store; set when `AVAILABLE`
  - `sha256` — content-address hash (SHA-256); set when `AVAILABLE`
  - `size_bytes` — total file size in bytes
  - `downloaded_bytes` — bytes downloaded so far (for resumability and progress)
  - `source_url` — upstream URL for resume (nullable)
  - `format` — format string (e.g. `"safetensors"`, `"json"`, `"tokenizer"`)
  - `status` — enum (`PENDING`, `DOWNLOADING`, `AVAILABLE`, `UNAVAILABLE`, `CHECKSUM_MISMATCH`)
  - `created_at`, `updated_at` — timestamps (via `TimestampMixin`)

  Per-asset `status` drives aggregate progress: the job endpoint returns total asset count and
  completed count; the UI derives percentage from `(completed / total)`. Byte-level detail from
  `downloaded_bytes` / `size_bytes` is available per-asset for richer UI display.

- **AssetDownloadJob**: tracks one asset-download job for a model (mirrors the existing `ModelImportJob`
  pattern). Fields: `id`, `external_model_id` (FK), `status` (`AssetDownloadJobStatus`:
  `QUEUED`/`DOWNLOADING`/`COMPLETE`/`FAILED`), `error_code`, `error_message`, `started_at`,
  `finished_at`, `created_at`, `updated_at`.

- **`ExternalModel.asset_availability`** (existing, from spec 040): this feature drives the existing
  `AssetState` enum field — `METADATA_ONLY → ASSETS_PENDING → ASSETS_AVAILABLE` (see FR-012b). No new
  column is added to `ExternalModel`; this spec only writes to the existing field.

- **UserSecret**: an encrypted, per-user secret value (e.g. HuggingFace token) stored in the app DB.
  New ORM model with `id`, `user_id`, `key` (unique per `user_id`, e.g. `"hf_token"`),
  `encrypted_value`, `created_at`, `updated_at`. Values are encrypted at rest with **AES-256-GCM** via
  the `cryptography` library (already a transitive dependency). The master key is read from
  `ANVIL_MASTER_SECRET`, or auto-generated and persisted with `0600` permissions on first boot —
  mirroring the existing `ApiKeyStore` key-management pattern (NOT plaintext; the `secrets` module is
  used only for key generation, not for the encryption itself).

## Definition of Done

- Download → per-file SHA-256-checksummed, content-addressed assets stored via the `FileStore` seam;
  `ExternalModel.asset_availability` transitions correctly (`METADATA_ONLY → ASSETS_PENDING →
  ASSETS_AVAILABLE`, reverting on failure); interrupted downloads resume from `downloaded_bytes`;
  sharded weights handled (all shards + index required for availability); HF token resolved via
  `UserSecret > HF_TOKEN`; unsupported formats and `track-only` models refused fail-closed with clear
  messaging; `license` recorded; **NMRG (full)**.

## Assumptions

- The `FileStore` seam (`anvil/storage/`) is the storage abstraction. In local mode `LocalFileStore` is
  used; in SaaS mode the workbench injects a LakeFS-backed `FileStore` (spec 019 / AD-17). This spec
  consumes whichever `FileStore` is injected and does **not** implement the LakeFS backend itself.
- `ExternalModel`, its `license`/`runnable_status` fields, and the `AssetState` enum already exist
  (spec 040); this spec extends the registry with asset download, not the registry schema itself.
- The architecture allow-list (FR-032) and `track-only` rule (FR-009a) are owned by specs 041/040; this
  spec references them to gate downloads but does not redefine them.
