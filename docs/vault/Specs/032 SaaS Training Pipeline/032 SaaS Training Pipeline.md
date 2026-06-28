---
title: 032 SaaS Training Pipeline
type: spec
tags:
  - type/spec
  - domain/training
  - domain/operations
  - domain/infrastructure
spec-refs:
  - docs/vault/Specs/032 SaaS Training Pipeline/
status: draft
created: '2026-06-27'
updated: '2026-06-27'
aliases:
  - 032 SaaS Training Pipeline
---

# 032 SaaS Training Pipeline

## Summary

The core product experience in SaaS mode: a logged-in user uploads a text corpus, configures hyperparameters, starts training, and watches the loss curve stream live in the browser via SSE. On completion, the model is available for download. This spec owns the durable training pipeline — `S3FileStore`, `RedisEventBus` (delivery-only), `BatchJobQueue` (per-shape job defs, fair-share by `org_id`, infra-only retry, timeout, multi-node), `BatchComputeBackend` (three-plane, never polls pod), `TrainingJob` + append-only `JobEvent` (idempotent `(job_id,sequence)`, metric throttling FR-043a) + `UsageRecord` models, compute worker (`_saas/compute_worker.py`), stateless reconciler (60s/300s, dependency backoff FR-044a), SSE with `Last-Event-ID` replay (AD-5) + polling fallback (FR-045a/b) + server-signaled degradation (FR-045r), per-org quota (FR-045j), and usage metering (AD-9, FR-046). Local mode is unchanged — the in-process flow keeps streaming via `InProcessEventBus` with no behavioral change.

## Artifacts

- [[032 SaaS Training Pipeline - spec|spec]]
- [[032 SaaS Training Pipeline - plan|plan]]
- [[032 SaaS Training Pipeline - tasks|tasks]]
- [[032 SaaS Training Pipeline - data-model|data-model]]
- [[032 SaaS Training Pipeline - research|research]]
- [[032 SaaS Training Pipeline - quickstart|quickstart]]

## Parent

[[Specs/016 SaaS Architecture/016 SaaS Architecture|016 SaaS Architecture (superseded umbrella)]]

## Decisions

[[Reference/SaaSArchitectureDecisions|SaaS Architecture Decisions]] — AD-1, AD-4, AD-5, AD-9, AD-11

## References

- [[Specs/Specs|Specs]]
- [[Specs/028 SaaS Abstraction Framework/028 SaaS Abstraction Framework|028 SaaS Abstraction Framework]]
- [[Specs/029 SaaS Dev Stack/029 SaaS Dev Stack|029 SaaS Dev Stack]]
- [[Specs/030 SaaS Authentication/030 SaaS Authentication|030 SaaS Authentication]]
- [[Specs/031 SaaS Multi-Tenancy RBAC/031 SaaS Multi-Tenancy RBAC|031 SaaS Multi-Tenancy]]