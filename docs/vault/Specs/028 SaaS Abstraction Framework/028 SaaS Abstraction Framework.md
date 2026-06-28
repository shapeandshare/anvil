---
title: 028 SaaS Abstraction Framework
type: spec
tags:
  - type/spec
  - domain/infrastructure
  - domain/architecture
spec-refs:
  - docs/vault/Specs/028 SaaS Abstraction Framework/
status: draft
created: '2026-06-27'
updated: '2026-06-27'
aliases:
  - 028 SaaS Abstraction Framework
---

# 028 SaaS Abstraction Framework

## Summary

Four core abstraction interfaces (`FileStore`, `EventBus`, `JobQueue`, `ComputeBackend`) decouple business logic from infrastructure, enabling anvil to run in local mode (filesystem, in-process) and SaaS mode (S3, Redis, AWS Batch) with zero cloud dependencies in the base package. This is the foundational feature upon which all SaaS capabilities are built, carrying the highest local-mode regression risk as it refactors existing local providers behind the new interfaces.

## Artifacts

- [[028 SaaS Abstraction Framework - spec|spec]]
- [[028 SaaS Abstraction Framework - plan|plan]]
- [[028 SaaS Abstraction Framework - tasks|tasks]]
- [[028 SaaS Abstraction Framework - research|research]]
- [[028 SaaS Abstraction Framework - data-model|data-model]]
- [[028 SaaS Abstraction Framework - quickstart|quickstart]]

## Parent

- [[Specs/016 SaaS Architecture/016 SaaS Architecture|016 SaaS Architecture (superseded umbrella)]]

## Decisions

- [[Reference/SaaSArchitectureDecisions|SaaS Architecture Decisions]]
- Key decisions: AD-10 (single image, two entrypoints)

## References

- [[Specs/Specs|Specs]]