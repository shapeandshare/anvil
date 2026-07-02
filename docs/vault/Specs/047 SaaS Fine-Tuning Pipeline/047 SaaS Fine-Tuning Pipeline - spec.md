---
title: 047 SaaS Fine-Tuning Pipeline - spec
type: spec
tags:
  - type/spec
  - domain/training
  - domain/infrastructure
status: draft
spec-refs:
  - docs/vault/Specs/047 SaaS Fine-Tuning Pipeline/
related:
  - '[[047 SaaS Fine-Tuning Pipeline]]'
  - '[[038 Fine-Tuning Arc]]'
  - '[[Reference/FineTuningArchitectureDecisions]]'
created: '2026-06-28'
updated: '2026-06-28'
---

# Feature Specification: SaaS Fine-Tuning Pipeline

**Feature Branch**: `047-saas-fine-tuning-pipeline`
**Created**: 2026-06-28
**Status**: Draft
**Parent Spec**: [[Specs/038 Fine-Tuning Arc/038 Fine-Tuning Arc|038 Fine-Tuning Arc (umbrella)]]

## Overview

Runs larger fine-tunes in SaaS on the **existing** training pipeline (spec 032) — durable `job_events`,
SSE/poll metrics, usage metering, AWS Batch GPU compute — extended to fetch base model assets from
**LakeFS** (spec 019 / AD-17), execute PEFT on GPU, and return a tracked, org-scoped adapter. No parallel
infrastructure: this is the SaaS-side backend behind the routing established in 046.

### Scope

| Dimension | Scope |
|-----------|-------|
| **Owned FRs** | FR-023 |
| **Owned decisions** | references AD-1 (Batch), AD-4 (`job_events`), AD-9 (metering), AD-17 (LakeFS) |
| **Depends on** | 046 (routing), 044 (PEFT engine), 045 (adapter results); spec 032 (SaaS pipeline), 019 (LakeFS), 042 (assets in LakeFS) |
| **Invariant risk** | **LOW** — SaaS-only path behind the SaaS entrypoint; local mode unaffected |

---

## Clarifications

### Session 2026-07-02

- Q: What state machine should the SaaS FineTune job follow? → A: 5-state pipeline (`pending → running → completing → completed | failed`), consistent with the existing 032 `job_events` pattern.
- Q: What is the concurrent fine-tune limit per org? → A: Configurable per-org concurrency limit, default 1.
- Q: How to handle base asset version mismatch between LakeFS and the fine-tune config? → A: Fail fast with a clear error message; no silent auto-upgrade.
- Q: What is the metering granularity for billback? → A: Per job with GPU-hour tracking, derived from `job_events`.
- Q: What are the retry limits and backoff policy for spot interruptions? → A: 3 retries with exponential backoff (30s / 90s / 270s); `failed` is the single terminal state for both retry-exhausted and fatally-failed jobs.

---

## User Story

### US — Learner Offloads a Larger Fine-Tune to SaaS (Priority: P2)

A learner whose model/dataset exceeds local limits submits the same fine-tune to SaaS; it runs on GPU,
streams metrics like SaaS training, and returns a tracked adapter.

**Independent Test**: With SaaS mode configured, submit a fine-tune classified over-local; verify it
dispatches to the SaaS compute backend, the base model is fetched from LakeFS, metrics stream via the
existing pipeline, usage is metered, and a tracked adapter is stored in LakeFS, org-scoped.

**Acceptance Scenarios**:

1. **Given** SaaS mode and an over-local fine-tune, **When** submitted, **Then** it runs on the SaaS
   (Batch GPU) backend.
2. **Given** a SaaS fine-tune, **When** it runs, **Then** the base model is fetched from LakeFS, metrics
   stream via the existing `job_events`/SSE pipeline, and the adapter is stored and registered.
3. **Given** a completed SaaS fine-tune, **When** the learner views usage, **Then** the run is metered for
   billback (AD-9), derived from `job_events`.
4. **Given** local mode, **When** anything in this spec ships, **Then** local behavior is unchanged.

### Edge Cases

- Spot interruption mid-fine-tune → up to 3 retries with exponential backoff (30s / 90s / 270s); exhausts into `failed` terminal state.
- Base asset not yet in LakeFS for the org → fail fast directing to asset acquisition (042).
- Base asset version mismatch (LakeFS version differs from fine-tune config) → fail fast with a clear error; no silent auto-upgrade.
- Adapter artifact write contention → idempotent storage keyed by job, consistent with 032's artifact
  handling.

## Requirements

- **FR-023**: SaaS fine-tuning MUST reuse the existing SaaS training pipeline (spec 032) — durable
  `job_events`, SSE/poll metrics, usage metering — fetching base assets from LakeFS and returning a
  tracked adapter.
- **FR-023a**: The SaaS fine-tune compute job MUST express its requirement as a `ResourceSpec` (GPU shape)
  consumed by AWS Batch (AD-1), consistent with how SaaS training jobs are dispatched.
- **FR-023b**: The produced adapter MUST be stored in LakeFS and registered org-scoped, reusing the asset
  governance from spec 042.
- **FR-023c**: SaaS fine-tune dispatch MUST enforce a configurable per-org concurrency limit (default 1).
  New submissions beyond the limit MUST be rejected with a clear error until a running job completes.

## Success Criteria

> **Full-vision criteria** (SC-001…SC-003) require the deferred infrastructure. The **MVP
> criteria** (SC-M1…SC-M3) are what this spec's task list actually delivers and verifies.

**Full vision (partially DEFERRED):**

- **SC-001** *(partially deferred — LakeFS/org)*: An over-local fine-tune runs on SaaS,
  streams metrics, and returns a tracked, org-scoped adapter from LakeFS.
- **SC-002** *(DEFERRED — metering/job_events)*: Usage is metered per-job with GPU-hour
  tracking (billback-ready), derived from `job_events`.
- **SC-003** *(DEFERRED — LakeFS)*: Base assets are sourced from LakeFS, not re-downloaded
  from the upstream source.

**MVP (delivered by this spec):**

- **SC-M1**: A LoRA/QLoRA fine-tune submitted with `compute_backend="saas"` (SaaS configured)
  routes to `SaasFinetuneBackend`, runs submit-then-poll via the injected provider seam,
  streams metrics via the existing SSE pipeline, and returns a `ComputeResult` with a
  non-null `adapter_id`.
- **SC-M2**: On completion, BOTH local and SaaS LoRA runs persist a `LoRAAdapter` DB row
  (fixes the pre-existing bug where no row was ever created).
- **SC-M3 (NMRG)**: Local mode is unaffected; pre-existing tests pass unmodified.

## Key Entities

- **SaaS FineTune job**: PEFT executed via the `SaasFinetuneProvider` seam (submit-then-poll).
  Full vision: a Batch GPU job against a LakeFS-sourced base model with a 5-state lifecycle
  (`pending → running → completing → completed | failed`). *MVP: the transport is an injected
  provider (fake in tests); Batch + LakeFS are deferred.*
- **Adapter**: reuses the existing `LoRAAdapter` ORM row. *MVP: stored via `LocalFileStore`;
  LakeFS + org-scoping deferred.*

## Definition of Done

**MVP (this spec):**

- LoRA/QLoRA with `compute_backend="saas"` routes to `SaasFinetuneBackend`, runs
  submit-then-poll via the provider seam, streams metrics, and returns a `ComputeResult` with
  a real `adapter_id`.
- Both local and SaaS LoRA completion persist a `LoRAAdapter` row (pre-existing bug fixed).
- `make test` / `make typecheck` / `make lint` / `make vault-audit` pass.
- **NMRG (full)** for local (non-LoRA and existing LoRA behavior otherwise unchanged).

**Full vision (DEFERRED to follow-on specs):** over-local fine-tune end-to-end (LakeFS base
→ Batch GPU PEFT → metered → LakeFS-tracked, org-scoped adapter).

## Assumptions

- Builds entirely on the SaaS body of work (028/032) and LakeFS (019/AD-17); introduces no new
  infrastructure primitives.

## Implementation Scope Note (MVP — 2026-07-02)

**Reality check (verified against `anvil/` source):** The infrastructure this spec's
original prose assumes does **not exist in code**. The following are absent and exist
only as spec documents / glossary strings:

- Spec 032 SaaS training pipeline: no `ResourceSpec` class, no `job_events` table, no
  AWS Batch dispatch, no usage-metering table/service, no Batch/SaaS compute backend.
- Spec 019/042 LakeFS: no `LakeFSVersionedContentStore` / `LakeFSFileStore` — only the
  local `LocalVersionedContentStore` + `LocalFileStore` exist.
- Multi-tenancy: no `org_id` column, filter, or scoping anywhere.
- **Pre-existing bug**: even the LOCAL LoRA path never persists a `LoRAAdapter` DB row
  (`LoRAAdapterRepository.add()` has zero callers post-training; `ComputeResult.adapter_id`
  is always `None`).

**Decision (Oracle-reviewed):** Implement 047 as a **thin, testable MVP** — a
provider-backed SaaS fine-tune backend following the proven `ModalBackend`
submit-then-poll pattern behind a minimal injected **SaaS provider seam**. Also fix the
adapter-persistence bug so BOTH local and SaaS runs persist a `LoRAAdapter` row.

### In Scope (047 MVP)

- Fix adapter-persistence: local + SaaS LoRA completion creates a `LoRAAdapter` DB row and
  populates a real `ComputeResult.adapter_id`.
- Minimal `SaasFinetuneProvider` seam (async: `submit`, `poll_status`, `fetch_adapter`).
- `SaasFinetuneBackend` (registers as `RegistryBackend.SAAS_FINETUNE`) using submit-then-poll.
- Real `_saas_configured()` gate (env-based) + correct routing (`ComputeBackendResult.SAAS`
  → `RegistryBackend.SAAS_FINETUNE`) — including fixing the training.py remap bug where the
  LoRA remap only fires inside the `LOCAL` branch.
- Adapter artifacts persisted via the **existing** `LocalFileStore` seam.

### Explicitly DEFERRED (follow-on specs — not built here)

| Deferred capability | Follow-on |
|---------------------|-----------|
| Real AWS Batch dispatch + `ResourceSpec` GPU shapes (FR-023a) | Spec 032 impl |
| Durable `job_events` + Last-Event-ID SSE replay | Spec 032 impl |
| Usage metering / GPU-hour billback (SC-002, AD-9) | Spec 032 impl |
| LakeFS-backed asset fetch + adapter storage (FR-023b, SC-001, SC-003) | Spec 019/042 impl |
| Per-org concurrency limit + org scoping (FR-023c) | Multi-tenancy spec |

The provider seam is the stable integration point these follow-ons plug into. It MUST NOT
grow speculative surface (no `ResourceSpec`, tenant fields, or event-stream abstractions
until a concrete caller needs them — YAGNI, Constitution Article XI).
