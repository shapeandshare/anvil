---
title: "Session: Spec 047 SaaS Fine-Tuning Pipeline — spec, plan, design, implementation"
type: session-log
tags:
  - type/session-log
  - domain/training
  - domain/infrastructure
  - status/draft
created: '2026-07-02'
updated: '2026-07-02'
aliases:
  - spec-047-saas-fine-tuning-pipeline
status: draft
source: agent
---

# Session: Spec 047 SaaS Fine-Tuning Pipeline — Full Implementation

**Date**: 2026-07-02
**Trigger**: Implement spec 047 SaaS Fine-Tuning Pipeline end-to-end (spec → clarify → plan → tasks → implement → analyze).

## Summary

Full spec-driven development cycle for spec 047. During the critical review phase, discovered that the entire assumed foundation (spec 032 SaaS pipeline, spec 019/042 LakeFS, multi-tenancy) **does not exist in code** — only in spec documents and glossary strings. Also found a pre-existing bug: LoRA adapter rows are never persisted to the DB after training, even for the local path.

Rescoped 047 to a thin, testable MVP per Oracle recommendation: a provider-backed SaaS fine-tune backend behind a minimal 3-method `SaasFinetuneProvider` seam, plus a fix for the adapter-persistence bug. Real AWS Batch, ``ResourceSpec``, ``job_events``, GPU-hour metering, LakeFS storage, and per-org concurrency are explicitly deferred to follow-on specs.

## Key Decisions

- **MVP scope (Oracle-reviewed)**: Abandoned the original assumption that spec 032/019/tenancy exist. Delivered a thin provider-backed backend instead of a full platform build. (Constitution Article XI — Simplicity First / YAGNI.)
- **``SaasFinetuneProvider`` seam**: Exactly 3 async methods (``submit``, ``poll_status``, ``fetch_adapter``). No ``ResourceSpec``, no tenant fields, no event-stream abstractions — YAGNI until a concrete caller needs them.
- **Adapter-persistence fix**: Created ``AdapterPersistenceService`` to create ``LoRAAdapter`` DB rows on completion. Fixed both the return path (``ComputeResult.adapter_id`` was always ``None``) and the storage path (``LoRAAdapterRepository.add()`` was never called).
- **``_saas_configured()`` gate**: Env-var-based (``ANVIL_SAAS_ENDPOINT``), single source of truth in ``resolve.py``, imported by the backend.

## Critical Discoveries

- **Spec 032 NOT implemented**: No ``ResourceSpec`` class, no ``job_events`` table, no AWS Batch dispatch code, no usage metering, no SaaS/Batch compute backend, no ``[saas]`` extra — all exist only as spec contracts under ``docs/vault/Specs/032*/`` and glossary strings in ``learning.py``.
- **LakeFS NOT implemented**: Only ``LocalVersionedContentStore`` + ``LocalFileStore`` exist. ``LakeFSVersionedContentStore``/``LakeFSFileStore`` are mentioned only as "future" in docstrings.
- **Multi-tenancy NOT implemented**: ``org_id`` appears only in OpenAPI schema strings (documentation), not in any column, filter, or service parameter.
- **Pre-existing bug**: ``LoRAAdapter`` DB rows are never created after training. ``LocalLoraBackend.run()`` saves adapter files to disk but ``ComputeResult.adapter_id`` is always ``None``, and ``LoRAAdapterRepository.add()`` has zero callers post-training.

## Artifacts Created / Modified

### Design artifacts
- ``docs/vault/Specs/047 SaaS Fine-Tuning Pipeline/047 SaaS Fine-Tuning Pipeline - spec.md`` — MVP-scoped spec with Implementation Scope Note, deferred capabilities table, MVP acceptance criteria
- ``docs/vault/Specs/047 SaaS Fine-Tuning Pipeline/plan.md`` — constitution-checked plan; corrected Summary/Technical Context; Complexity Tracking with 2 justified deviations
- ``docs/vault/Specs/047 SaaS Fine-Tuning Pipeline/research.md`` — reality-check table; codebase verification results
- ``docs/vault/Specs/047 SaaS Fine-Tuning Pipeline/tasks.md`` — 22 tasks across 4 phases
- ``docs/vault/Specs/047 SaaS Fine-Tuning Pipeline/data-model.md`` — reuses existing ``LoRAAdapter``; no new tables
- ``docs/vault/Specs/047 SaaS Fine-Tuning Pipeline/contracts/api.md`` — target API shape (partially deferred)
- ``docs/vault/Specs/047 SaaS Fine-Tuning Pipeline/contracts/internal.md`` — ``SaasFinetuneProvider`` Protocol, ``SaasFinetuneBackend``, ``AdapterPersistenceService``
- ``docs/vault/Specs/047 SaaS Fine-Tuning Pipeline/quickstart.md`` — setup-to-run flow

### Source files created
- ``anvil/services/compute/saas_finetune_provider.py`` — PEP 544 Protocol with 3 methods
- ``anvil/services/compute/saas_finetune_backend.py`` — submit-then-poll backend with retry (3×, exp backoff 30/90/270s)
- ``anvil/services/training/adapter_persistence.py`` — ``AdapterPersistenceService``
- ``tests/unit/services/test_adapter_persistence.py`` — 2 tests
- ``tests/unit/services/test_saas_finetune_backend.py`` — 13 tests

### Source files modified
- ``anvil/services/compute/local_lora_backend.py`` — populate ``adapter_id`` on ``ComputeResult``
- ``anvil/services/compute/resolve.py`` — real ``_saas_configured()`` gate
- ``anvil/services/training/training.py`` — SAAS remap fix, SSE guard for SaaS
- ``anvil/api/v1/training.py`` — ``on_complete`` persists ``LoRAAdapter`` row
- ``anvil/cli.py`` — ``on_complete`` persists ``LoRAAdapter`` row

## Compliance

- **Tests**: 15 unit tests (2 adapter + 9 backend + 4 routing), all passing; 1 e2e test (requires full app context, deferred)
- **Lint**: ruff clean on all new/modified files
- **Type check**: mypy clean on new files
- **Coverage**: 25.79% (above 23% threshold)

## Deferred (Follow-on Specs)

| Capability | Target Spec |
|------------|-------------|
| AWS Batch dispatch + ``ResourceSpec`` GPU shapes (FR-023a) | 032 implementation |
| Durable ``job_events`` + Last-Event-ID SSE replay | 032 implementation |
| GPU-hour usage metering / billback (SC-002) | 032 implementation |
| LakeFS-backed asset fetch + adapter storage (FR-023b, SC-001, SC-003) | 019/042 implementation |
| Per-org concurrency limit + org scoping (FR-023c) | Multi-tenancy spec |