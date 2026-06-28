---
title: 029 SaaS Dev Stack
type: spec
tags:
  - type/spec
  - domain/infrastructure
spec-refs:
  - docs/vault/Specs/029 SaaS Dev Stack/
status: draft
created: '2026-06-27'
updated: '2026-06-27'
aliases:
  - 029 SaaS Dev Stack
---

# 029 SaaS Dev Stack

## Summary

A developer clones the repo and runs `docker compose up` to start PostgreSQL, Redis, MinIO, MLflow, and the anvil web service with hot-reload. They can make changes to the code and see them reflected immediately. This is the fastest iteration loop for SaaS feature development — intentionally shipped second despite being plan phase 10, so every subsequent SaaS feature gets a ~2-minute feedback loop instead of requiring a `cdk deploy` per iteration.

## Artifacts

- [[029 SaaS Dev Stack - data-model|data-model]]
- [[029 SaaS Dev Stack - plan|plan]]
- [[029 SaaS Dev Stack - quickstart|quickstart]]
- [[029 SaaS Dev Stack - research|research]]
- [[029 SaaS Dev Stack - spec|spec]]
- [[029 SaaS Dev Stack - tasks|tasks]]

## Parent

[[Specs/016 SaaS Architecture/016 SaaS Architecture|016 SaaS Architecture (superseded umbrella)]]

## Decisions

[[Reference/SaaSArchitectureDecisions|SaaS Architecture Decisions]]

## References

- [[Specs/Specs|Specs]]