---
title: 046 Fine-Tune Compute Routing - spec
type: spec
tags:
  - type/spec
  - domain/training
  - domain/operations
status: draft
spec-refs:
  - docs/vault/Specs/046 Fine-Tune Compute Routing/
related:
  - '[[046 Fine-Tune Compute Routing]]'
  - '[[038 Fine-Tuning Arc]]'
  - '[[Reference/FineTuningArchitectureDecisions]]'
created: '2026-06-28'
updated: '2026-07-01'
---

# Feature Specification: Fine-Tune Compute Routing & Adapter Results

**Feature Branch**: `046-fine-tune-compute-routing`
**Created**: 2026-06-28
**Status**: Draft
**Parent Spec**: [[Specs/038 Fine-Tuning Arc/038 Fine-Tuning Arc|038 Fine-Tuning Arc (umbrella)]]

## Overview

Makes a fine-tune a first-class job in the compute layer so the **same** configuration runs locally or
offloads to SaaS, decided by size — not by a separate workflow. Extends `anvil/services/compute/` with a
fine-tune job type, `ResourceSpec`-based sizing, `resolve.py` routing (local vs SaaS) under the D4
degraded-mode rules, and adapter-aware result normalization across local and remote backends. D4 degraded-mode semantics are defined in [[Decisions/ADR-015-pluggable-compute-backends|ADR-015]].

### Scope

| Dimension | Scope |
|-----------|-------|
| **Owned FRs** | FR-022 |
| **Owned decisions** | FT-AD-6 (references AD-1 for SaaS Batch shapes) |
| **Depends on** | 044 (local backend), 045 (adapter results); `anvil/services/compute/{resolve.py,registry.py,result.py}` |
| **Invariant risk** | **LOW** — extends the existing resolution/registry layer; no native path change |

---

## User Story

### US — One Fine-Tune Config, Routed by Size (Priority: P2)

A learner submits a fine-tune; the resolver picks the local backend if it fits the host envelope, or the
SaaS backend if it does not (when SaaS is configured) — honoring explicit selections under D4.

**Independent Test**: Submit a small fine-tune and verify it resolves to the local backend; submit one
classified as over-local and verify it routes to SaaS (auto) or raises if local was explicitly required.

**Acceptance Scenarios**:

1. **Given** `auto`, **When** a fine-tune fits the local envelope, **Then** it runs on the local backend.
2. **Given** `auto`, **When** a fine-tune exceeds the local envelope and SaaS is configured, **Then** it
   routes to the SaaS backend rather than failing.
3. **Given** an explicit local selection (`local-cpu`/`local-gpu`) that cannot be honored, **When**
   submitted, **Then** the system raises `ComputeBackendUnavailable` (D4) rather than silently offloading.
4. **Given** either backend, **When** the run completes, **Then** the adapter result is normalized
   identically (FT-AD-7) regardless of where it executed.

### Edge Cases

- SaaS not configured but model too large for local → `auto` reports the gap; explicit local
  (`local-cpu`/`local-gpu`) raises `ComputeBackendUnavailable` with guidance.
- `ResourceSpec` for a fine-tune underestimates need → sizing must derive from base-model params +
  method, not just dataset size.
- Mixed availability (GPU present but insufficient VRAM) → classified as over-local for that model.
- SaaS mid-job failure → surfaced as `ComputeResult` error; no retry or failover. SaaS reliability and
  job durability are owned by spec 047.

## Requirements

- **FR-022**: Fine-tunes MUST be dispatched through a dedicated `resolve_fine_tune()` function in the
  compute resolution layer (`resolve.py`), which selects local vs SaaS by `ResourceSpec`/base-model size
  under the D4 degraded-mode rules (auto/local fall back; explicit unavailable selection raises). The
  existing `resolve_backend()` for native training MUST remain unchanged for its non-fine-tune paths
  (NMRG). Today `resolve_backend()` already contains a `method in ("lora","qlora")` branch
  (`resolve.py:111-119`) that routes fine-tunes to the local torch backend **only** — a local-only gap
  with no SaaS option. `resolve_fine_tune()` MUST own the size-based local-vs-SaaS decision; the
  existing lora/qlora branch in `resolve_backend()` MUST delegate to `resolve_fine_tune()` rather than
  duplicating routing logic (no second parallel routing path — Constitution §11.4).
- **FR-022a**: A fine-tune's `ResourceSpec` MUST be derived from base-model parameter count, method
  (`full`/`lora`/`qlora`), and quantization — making "too large for local" a computed decision, not a
  guess. The formula is: `VRAM = base_params * method_multiplier * quantization_factor + overhead`,
  where `full=2×`, `lora=1.2×`, `qlora=0.6×` of the base parameter size on RAM. The envelope check
  compares this computed VRAM against available host memory (GPU VRAM or system RAM).
- **FR-022b**: Adapter-bearing `ComputeResult`s MUST normalize identically across local and SaaS
  backends so downstream code is backend-agnostic.
- **FR-022c**: SaaS fine-tune progress tracking MUST follow the existing submit-then-poll pattern (D3,
  ADR-015): the backend polls remote job status internally during `run()`, reports via
  `progress_callback`, and the orchestrator feeds signals into the existing SSE stream. No separate
  external status endpoint is needed for v1.
- **FR-022d**: The SaaS backend identity MUST be added to the compute enums so routing results are
  representable: `ComputeBackend.SAAS = "saas"` (user-facing selection),
  `ComputeBackendResult.SAAS = "saas"` (result provenance), and `RegistryBackend.SAAS_FINETUNE =
  "saas-finetune"` (registry key). The existing enum members
  (`auto`/`local-cpu`/`local-gpu`/`modal`, `local`/`modal`, `local-stdlib`/`local-torch`/`local-lora`/`modal`)
  MUST remain unchanged (NMRG). `resolve_fine_tune()` accepts the user-facing `compute_backend` values
  `auto`, `local-cpu`, `local-gpu`, and `saas`; there is no bare `"local"` value — "run locally" is
  expressed via `local-cpu`/`local-gpu` (or `auto`).

## Success Criteria

- **SC-001**: A fine-tune routes to the correct backend by computed size.
- **SC-002**: D4 semantics are honored (auto/local fall back; explicit-unavailable raises).
- **SC-003**: Adapter results normalize identically local vs remote.
- **SC-004 (NMRG)**: Pre-existing tests pass unmodified; native training/routing unchanged.

## Key Entities

- **ResourceSpec (fine-tune)**: computed compute requirement for a fine-tune job.
- **FineTune job type**: first-class job kind in the compute registry/resolution layer.

## Definition of Done

- Size-based routing works with D4 semantics; adapter results normalized across backends; **NMRG (full)**.

## Clarifications

### Session 2026-07-01

- Q: What are the D4 degraded-mode rules referenced in FR-022 and SC-002? → A: D4 is defined in ADR-015 (Pluggable Compute Backends) — implicit selection silently falls back (e.g., auto local→SaaS), explicit unavailable selection raises `ComputeBackendUnavailable`. Updated to wikilink ADR-015.
- Q: How is the fine-tune ResourceSpec "too large for local" computed? → A: Per-method VRAM formula — `VRAM = base_params * method_multiplier * quantization_factor + overhead`. Full=2×, LoRA=1.2×, QLoRA=0.6× of base param size on RAM. The envelope check compares compute VRAM vs available host memory (GPU VRAM or system RAM).
- Q: What happens when SaaS is configured but fails mid-job? → A: Report failure via `ComputeResult` error; don't retry or failover. SaaS reliability/durability is owned by spec 047. Mid-job SaaS failure is surfaced as a `ComputeResult` error consistent with D4 semantics.
- Q: How does the user track progress of a SaaS fine-tune? → A: Internal poll inside `SaaSBackend.run()`, matching the existing Modal submit-then-poll pattern (D3). The backend polls remote job status, reports via `progress_callback`; the orchestrator feeds signals into the existing SSE stream. No new external status endpoint for v1.
- Q: How does fine-tune routing extend `resolve.py`? → A: New `resolve_fine_tune()` function in `resolve.py`. The public function is `resolve_backend()` (not `resolve()`); its existing `method in ("lora","qlora")` branch (`resolve.py:111-119`) currently routes fine-tunes to local-only and MUST delegate to `resolve_fine_tune()` (no duplicate routing path).
- Q: Do `ComputeBackend`/`ComputeBackendResult` have `"local"`/`"saas"` values today? → A: No. Existing members are `auto`/`local-cpu`/`local-gpu`/`modal` (user-facing) and `local`/`modal` (result). This spec ADDS `SAAS` to both plus `SAAS_FINETUNE` to `RegistryBackend` (FR-022d). There is no bare `"local"` user-facing value — local is `local-cpu`/`local-gpu`/`auto`.

## Assumptions

- The SaaS backend implementation/pipeline is owned by spec 047; this spec owns the routing decision and
  result normalization.
