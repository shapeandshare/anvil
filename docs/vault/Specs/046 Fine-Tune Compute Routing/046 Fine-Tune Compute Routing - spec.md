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
updated: '2026-06-28'
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
degraded-mode rules, and adapter-aware result normalization across local and remote backends.

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
3. **Given** an explicit local selection that cannot be honored, **When** submitted, **Then** the system
   raises `ComputeBackendUnavailable` (D4) rather than silently offloading.
4. **Given** either backend, **When** the run completes, **Then** the adapter result is normalized
   identically (FT-AD-7) regardless of where it executed.

### Edge Cases

- SaaS not configured but model too large for local → `auto` reports the gap; explicit local raises with
  guidance.
- `ResourceSpec` for a fine-tune underestimates need → sizing must derive from base-model params +
  method, not just dataset size.
- Mixed availability (GPU present but insufficient VRAM) → classified as over-local for that model.

## Requirements

- **FR-022**: Fine-tunes MUST be dispatched through the existing compute resolution layer (`resolve.py`),
  which selects local vs SaaS by `ResourceSpec`/base-model size under the D4 degraded-mode rules
  (auto/local fall back; explicit unavailable selection raises).
- **FR-022a**: A fine-tune's `ResourceSpec` MUST be derived from base-model parameter count, method
  (`full`/`lora`/`qlora`), and quantization — making "too large for local" a computed decision, not a
  guess.
- **FR-022b**: Adapter-bearing `ComputeResult`s MUST normalize identically across local and SaaS
  backends so downstream code is backend-agnostic.

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

## Assumptions

- The SaaS backend implementation/pipeline is owned by spec 047; this spec owns the routing decision and
  result normalization.
