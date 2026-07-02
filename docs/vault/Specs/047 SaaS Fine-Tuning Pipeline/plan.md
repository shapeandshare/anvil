# Implementation Plan: 047 SaaS Fine-Tuning Pipeline

**Branch**: `047-saas-fine-tuning-pipeline` | **Date**: 2026-07-02 | **Spec**: [[047 SaaS Fine-Tuning Pipeline - spec]]
**Input**: Feature specification from `docs/vault/Specs/047 SaaS Fine-Tuning Pipeline/047 SaaS Fine-Tuning Pipeline - spec.md`

## Summary

> **Scope corrected 2026-07-02 (MVP, Oracle-reviewed).** Code verification revealed that
> the assumed foundation — spec 032 SaaS pipeline, LakeFS (019/042), and multi-tenancy —
> **does not exist in code** (only spec docs + glossary strings). See the spec's
> "Implementation Scope Note". 047 is therefore delivered as a **thin, testable MVP**, not
> as a build of the absent 032 platform.

Implement a **provider-backed SaaS fine-tune backend** following the proven `ModalBackend`
submit-then-poll pattern behind a minimal injected **SaaS provider seam**. Also fix a
pre-existing correctness bug: neither the local nor SaaS LoRA completion path persists a
`LoRAAdapter` DB row today (`ComputeResult.adapter_id` is always `None`). This MVP makes
both paths persist adapters and returns a real `adapter_id`.

Real AWS Batch dispatch, `ResourceSpec` GPU shapes, durable `job_events`, GPU-hour usage
metering, LakeFS-backed storage, and per-org concurrency/tenancy are **explicitly deferred**
to follow-on specs (see spec's deferral table). The provider seam is the stable integration
point those follow-ons plug into — it MUST stay minimal (YAGNI, Article XI).

## Technical Context

**Language/Version**: Python 3.11+ (existing repo convention, PEP 604, `StrEnum`, `from __future__ import annotations`)  
**Primary Dependencies**: FastAPI, async SQLAlchemy + aiosqlite, Jinja2 (existing); `peft`, `bitsandbytes` (behind `[finetune]` extra, from 044) — reused for the PEFT config schema. **No new runtime dependencies** in the MVP (no `boto3`/`[saas]` extra, no LakeFS client — those arrive with the deferred follow-ons).  
**Storage**: SQLite (anvil-state.db, WAL mode) via async SQLAlchemy for the `LoRAAdapter` row; **existing** `LocalFileStore` for adapter artifacts. (LakeFS deferred.)  
**Testing**: pytest, pytest-asyncio, httpx (e2e client), in-memory SQLite per test session; injected fake `SaasFinetuneProvider` (mirrors `ModalBackend`'s `function_factory` test seam)  
**Target Platform**: macOS/Linux dev; SaaS provider seam is transport-agnostic (real AWS Batch transport deferred)  
**Project Type**: Python package (pip-installable) + FastAPI web service  
**Performance Goals**: No additional latency for the local path (NMRG); SaaS backend follows the existing submit-then-poll cadence (2s poll interval, matching `ModalBackend`)  
**Constraints**: `failed` is the single terminal state; reuse `ModalBackend` remote pattern and existing `LocalFileStore` — introduce nothing beyond the minimal provider seam  
**Scale/Scope**: Local mode fully NMRG; SaaS path behind `_saas_configured()` gate + 046 routing. Per-org concurrency, GPU-hour metering, Batch/LakeFS all deferred.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Simplicity First gate (Article XI — hard MUST)**: Confirm this plan favors
the simplest, most boring solution that meets the requirement:

- [x] **Simplest viable** (§11.1) — the chosen approach is the simplest that
      satisfies the requirement; any added complexity has a concrete, present
      justification (not a hypothetical future one).
- [x] **Boring over novel** (§11.2) — no novel/experimental dependency,
      framework, or pattern is introduced where a simpler proven alternative
      exists; any such choice is recorded in Complexity Tracking below.
- [x] **YAGNI** (§11.3) — no speculative generality, premature abstraction, or
      config knobs without a present consumer.
- [x] **Reuse first** (§11.4) — existing libraries/patterns/abstractions are
      reused before introducing new ones.
- [x] **Testable** (§11.6) — the approach is demonstrably testable; untested or
      untestable paths are not treated as complete (pairs with Article IV TDD).

> Any deviation from the simplest viable solution MUST be recorded in the
> Complexity Tracking table below (§11.5), or this gate fails.

## Project Structure

### Documentation (this feature)

```text
docs/vault/Specs/047 SaaS Fine-Tuning Pipeline/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
└── tasks.md             # Phase 2 output (/speckit.tasks command)
```

### Source Code (repository root)

```text
anvil/
├── services/
│   ├── compute/
│   │   ├── local_lora_backend.py       # Existing — fix: populate adapter_id
│   │   ├── modal_backend.py            # Existing — reference pattern
│   │   ├── resolve.py                  # Fix: real _saas_configured()
│   │   ├── saas_finetune_provider.py   # NEW — minimal provider seam (Protocol)
│   │   └── saas_finetune_backend.py    # NEW — submit-then-poll backend
│   ├── training/
│   │   ├── training.py                 # Fix: remap bug + adapter persistence
│   │   └── adapter_persistence.py      # NEW (or inline) — creates LoRAAdapter row
│   └── _shared/                        # Existing cross-domain types
├── db/
│   ├── models/lora_adapter.py          # Existing — reused as-is
│   └── repositories/
│       └── lora_adapter_repository.py  # Existing add() — now actually called
├── api/
│   └── v1/                             # Optional: SaaS submit route (reuse /training)
└── workbench.py                        # Wire provider + adapter persistence

tests/
├── unit/
│   ├── services/test_adapter_persistence.py   # NEW — local + SaaS row creation
│   └── services/test_saas_finetune_backend.py # NEW — submit/poll/retry/cancel
└── e2e/
    └── test_saas_finetune.py                  # NEW — HTTP submit → adapter tracked
```

**Structure Decision**: Extend existing `services/compute/` and `services/training/`.
Two new files (provider seam + backend). No new top-level directories, no new DB tables in
the MVP (reuse `LoRAAdapter`).

## Complexity Tracking

| Decision | Why Needed (present) | Simpler Alternative Rejected Because |
|----------|----------------------|--------------------------------------|
| New `SaasFinetuneProvider` seam | The SaaS transport must be swappable + testable (fake in tests, real transport later). `ModalBackend` proves this pattern. | Hard-coding a transport now would be untestable and would bake in AWS Batch before it exists — worse than a 3-method Protocol. |
| Fix adapter-persistence inside 047 (not a separate spec) | Same LoRA completion path; a credible SaaS "tracked adapter" result is impossible without it. It's a current correctness gap. | Deferring it would leave 047's core deliverable (a tracked adapter) unverifiable. |

**Deferred (recorded here so scope is auditable):** AWS Batch + `ResourceSpec`, durable
`job_events`, GPU-hour metering, LakeFS stores, per-org concurrency/tenancy. Each is its own
follow-on spec; none is built in this MVP.
