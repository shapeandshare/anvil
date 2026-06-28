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

- Spot interruption mid-fine-tune → retry/checkpoint-resume per the existing pipeline's handling.
- Base asset not yet in LakeFS for the org → fail fast directing to asset acquisition (042).
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

## Success Criteria

- **SC-001**: An over-local fine-tune runs on SaaS, streams metrics, and returns a tracked, org-scoped
  adapter from LakeFS.
- **SC-002**: Usage is metered for the fine-tune (billback-ready), derived from `job_events`.
- **SC-003**: Base assets are sourced from LakeFS, not re-downloaded from the upstream source.
- **SC-004 (NMRG)**: Local mode is unaffected; pre-existing tests pass unmodified.

## Key Entities

- **SaaS FineTune job**: a Batch GPU job executing PEFT against a LakeFS-sourced base model.
- **Adapter (SaaS)**: org-scoped adapter artifact stored in LakeFS and registered.

## Definition of Done

- Over-local fine-tune runs on SaaS end-to-end (LakeFS base → GPU PEFT → metered → tracked adapter);
  local mode untouched; **NMRG (full)** for local.

## Assumptions

- Builds entirely on the SaaS body of work (028/032) and LakeFS (019/AD-17); introduces no new
  infrastructure primitives.
