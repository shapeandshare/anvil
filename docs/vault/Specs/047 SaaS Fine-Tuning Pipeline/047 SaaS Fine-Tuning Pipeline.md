---
title: 047 SaaS Fine-Tuning Pipeline
type: spec
tags:
  - type/spec
  - domain/training
  - domain/infrastructure
spec-refs:
  - docs/vault/Specs/047 SaaS Fine-Tuning Pipeline/
status: draft
created: '2026-06-28'
updated: '2026-06-28'
aliases:
  - 047 SaaS Fine-Tuning Pipeline
---

# 047 SaaS Fine-Tuning Pipeline

Offload track of the [[Specs/038 Fine-Tuning Arc/038 Fine-Tuning Arc|Fine-Tuning Arc]]: run larger
fine-tunes on the existing SaaS training pipeline (032) — Batch GPU, durable `job_events`, SSE, metering
— with base assets from LakeFS (019/AD-17) and a tracked, org-scoped adapter returned.

## Owned

- **FRs**: FR-023 (+ FR-023a, FR-023b)
- **Decisions**: references AD-1, AD-4, AD-9, AD-17

## Dependencies

- [[Specs/046 Fine-Tune Compute Routing/046 Fine-Tune Compute Routing|046 Fine-Tune Compute Routing]] (routing)
- [[Specs/032 SaaS Training Pipeline/032 SaaS Training Pipeline|032 SaaS Training Pipeline]] (pipeline)
- [[Specs/019 LakeFS Content Repo/019 LakeFS Content Repo|019 LakeFS Content Repo]] (assets/adapters)
- [[Specs/044 Local LoRA Fine-Tuning/044 Local LoRA Fine-Tuning|044 Local LoRA Fine-Tuning]] (PEFT engine)

## Artifacts

- [[047 SaaS Fine-Tuning Pipeline - spec|spec]]

## References

- [[Specs/038 Fine-Tuning Arc/038 Fine-Tuning Arc|038 Fine-Tuning Arc]]
- [[Reference/SaaSArchitectureDecisions|SaaS Architecture Decisions]]
- [[Reference/FineTuningArchitectureDecisions|Fine-Tuning Architecture Decisions]]
- [[Specs/Specs|Specs]]
