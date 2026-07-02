---
title: Spec 032 / LakeFS / Multi-Tenancy NOT Implemented Despite Spec Documents
type: discovery
tags:
  - type/discovery
  - domain/training
  - domain/infrastructure
status: draft
created: '2026-07-02'
updated: '2026-07-02'
spec-refs:
  - docs/vault/Specs/047 SaaS Fine-Tuning Pipeline/
  - docs/vault/Specs/032 SaaS Training Pipeline/
  - docs/vault/Specs/019 LakeFS Content Repo/
---

# Spec 032 / LakeFS / Multi-Tenancy NOT Implemented

## Summary

Spec 047 (SaaS Fine-Tuning Pipeline) assumed the existence of spec 032 (SaaS Training Pipeline), spec 019/042 (LakeFS asset storage), and multi-tenancy. **None of these exist in the ``anvil/`` source code.** They exist only as:

- Spec contract documents under ``docs/vault/Specs/032*/`` and ``docs/vault/Specs/019*/``
- Glossary definition strings in ``anvil/api/v1/learning.py`` (lines 2678–2703)

## Details

| Assumed Foundation | Actual State | Evidence |
|---|---|---|
| ``ResourceSpec`` class | **Does not exist** — only a glossary string | ``learning.py:2678`` |
| ``job_events`` table / ORM | **Does not exist** — not in ``anvil/db/models/`` | 29 ORM models, none named ``JobEvent`` |
| AWS Batch dispatch (boto3, submit_job) | **Does not exist** — no batch client in any compute backend | Existing backends: local_stdlib, local_torch, modal, local_lora only |
| Usage metering / billback table | **Does not exist** — only a glossary string | ``learning.py:2703`` |
| SaaS/Batch compute backend | **Does not exist** — only ``RegistryBackend.SAAS_FINETUNE`` enum value | No ``SaaSBackend`` or ``SaasComputeBackend`` class |
| ``[saas]`` extra (boto3/aioboto3) | **Does not exist** — extras are gpu/compute/vault-health/dev/finetune | ``pyproject.toml`` lines 80-105 |
| LakeFS store (``LakeFSVersionedContentStore``) | **Does not exist** — only ``LocalVersionedContentStore`` | ``versioned_content_store.py`` docstring says "SaaS mode (future)" |
| Multi-tenancy / ``org_id`` | **Does not exist** — no column, filter, or scope in any model/repository/service | ``learning.py`` lines 2683, 2703 are glossary only |

## Related Discovery: LoRAAdapter Rows Never Persisted

During the codebase verification, a pre-existing bug was also found: ``LocalLoraBackend.run()`` saves adapter files to disk at ``data/adapters/lora_{timestamp}/`` but **no ``LoRAAdapter`` DB row is ever created**. ``LoRAAdapterRepository.add()`` has zero callers post-training. ``ComputeResult.adapter_id`` is always ``None``.

## Impact

Spec 047 had to be rescoped as an MVP (Oracle-reviewed) — a thin provider-backed SaaS fine-tune backend rather than the full "extend existing 032 pipeline" originally planned. Full 032/LakeFS/tenancy work is deferred to follow-on specs.

## References

- [[Specs/047 SaaS Fine-Tuning Pipeline/047 SaaS Fine-Tuning Pipeline - spec|047 SaaS Fine-Tuning Pipeline spec]] (Implementation Scope Note)
- [[Specs/047 SaaS Fine-Tuning Pipeline/research|047 research]] (reality-check table)
- [[2026-07-02-spec-047-saas-fine-tuning-pipeline|Session log]]