---
title: 037 SaaS Resilience DR
type: spec
tags:
  - type/spec
  - domain/infrastructure
  - domain/operations
spec-refs:
  - docs/vault/Specs/037 SaaS Resilience DR/
status: draft
created: '2026-06-27'
updated: '2026-06-27'
aliases:
  - 037 SaaS Resilience DR
---

# 037 SaaS Resilience DR

## Summary

Production hardening for the SaaS deployment: Redis Multi-AZ failover validation, secret-rotation dual-key window for SSE signing secret + Redis auth token, reconciler crash-recovery + dependency-degradation backoff chaos tests, RDS automated snapshots/PITR + S3 versioning final wiring, destroy-time final-snapshot safety, and deploy restore DR. Cross-references specs 033 (CDK constructs) and 034 (deploy CLI) for the underlying construct/command work — this spec owns the resilience validation, chaos testing, and dual-key rotation logic.

## Artifacts

- [[037 SaaS Resilience DR - spec|spec]]
- [[037 SaaS Resilience DR - plan|plan]]
- [[037 SaaS Resilience DR - tasks|tasks]]
- [[037 SaaS Resilience DR - research|research]]
- [[037 SaaS Resilience DR - data-model|data-model]]
- [[037 SaaS Resilience DR - quickstart|quickstart]]

## Parent

- [[Specs/016 SaaS Architecture/016 SaaS Architecture|016 SaaS Architecture (superseded umbrella)]]

## Decisions

- [[Reference/SaaSArchitectureDecisions|SaaS Architecture Decisions]]
- Key decisions: AD-16 (production posture: single-region multi-AZ HA + backup/DR + secret rotation)

## References

- [[Specs/033 SaaS CDK Infrastructure/033 SaaS CDK Infrastructure|033 SaaS CDK Infrastructure]] (constructs for RDS snapshots, S3 versioning, Redis Multi-AZ)
- [[Specs/034 SaaS One-Command Deploy/034 SaaS One-Command Deploy|034 SaaS One-Command Deploy]] (deploy CLI: destroy, restore commands)
- [[Specs/036 SaaS Observability MLflow Proxy/036 SaaS Observability MLflow Proxy|036 SaaS Observability]] (alerting on failover)
- [[Specs/032 SaaS Training Pipeline/032 SaaS Training Pipeline|032 SaaS Training Pipeline]] (reconciler)
- [[Specs/Specs|Specs]]