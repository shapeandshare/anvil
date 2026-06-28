---
title: 016 SaaS Architecture
type: spec
tags:
  - type/spec
  - domain/infrastructure
  - status/superseded
spec-refs:
  - docs/vault/Specs/016 SaaS Architecture/
status: superseded
created: '2026-06-19'
updated: '2026-06-27'
aliases:
  - 016 SaaS Architecture
---

# 016 SaaS Architecture

> [!WARNING] Superseded — Split into per-feature specs (028–037)
> This umbrella spec has been **superseded** (2026-06-27). The single large SaaS spec was decomposed
> into ten discrete, independently shippable per-feature specs. Delivery tracking now lives in the
> child specs below; the canonical architecture decisions (AD-1..AD-17) moved to a shared reference.
>
> **Superseding notes:**
> - [[Reference/SaaSArchitectureDecisions|SaaS Architecture Decisions (AD-1..AD-17)]] — shared decisions
> - [[Specs/028 SaaS Abstraction Framework/028 SaaS Abstraction Framework|028 SaaS Abstraction Framework]]
> - [[Specs/029 SaaS Dev Stack/029 SaaS Dev Stack|029 SaaS Dev Stack]]
> - [[Specs/030 SaaS Authentication/030 SaaS Authentication|030 SaaS Authentication]]
> - [[Specs/031 SaaS Multi-Tenancy RBAC/031 SaaS Multi-Tenancy RBAC|031 SaaS Multi-Tenancy RBAC]]
> - [[Specs/032 SaaS Training Pipeline/032 SaaS Training Pipeline|032 SaaS Training Pipeline]]
> - [[Specs/033 SaaS CDK Infrastructure/033 SaaS CDK Infrastructure|033 SaaS CDK Infrastructure]]
> - [[Specs/034 SaaS One-Command Deploy/034 SaaS One-Command Deploy|034 SaaS One-Command Deploy]]
> - [[Specs/035 SaaS CLI Remote/035 SaaS CLI Remote|035 SaaS CLI Remote]]
> - [[Specs/036 SaaS Observability MLflow Proxy/036 SaaS Observability MLflow Proxy|036 SaaS Observability MLflow Proxy]]
> - [[Specs/037 SaaS Resilience DR/037 SaaS Resilience DR|037 SaaS Resilience DR]]
>
> The `shippable-features` artifact below is the bridge/MOC explaining the decomposition and the
> recommended delivery order. The original `spec.md`/`plan.md`/`tasks.md`/`data-model.md` are retained
> as historical reference (their content was lifted verbatim into the children, preserving FR numbers).

## Summary

A new user visits anvil.io and either signs in with Google/GitHub or creates a passwordless account via email magic link (Cognito Hosted UI). They are authenticated and redirected to the dashboard. Session management (tokens, refresh, MFA) is handled entirely by Cognito.

## Child Specs (superseding)

- [[Specs/028 SaaS Abstraction Framework/028 SaaS Abstraction Framework|028 SaaS Abstraction Framework]]
- [[Specs/029 SaaS Dev Stack/029 SaaS Dev Stack|029 SaaS Dev Stack]]
- [[Specs/030 SaaS Authentication/030 SaaS Authentication|030 SaaS Authentication]]
- [[Specs/031 SaaS Multi-Tenancy RBAC/031 SaaS Multi-Tenancy RBAC|031 SaaS Multi-Tenancy RBAC]]
- [[Specs/032 SaaS Training Pipeline/032 SaaS Training Pipeline|032 SaaS Training Pipeline]]
- [[Specs/033 SaaS CDK Infrastructure/033 SaaS CDK Infrastructure|033 SaaS CDK Infrastructure]]
- [[Specs/034 SaaS One-Command Deploy/034 SaaS One-Command Deploy|034 SaaS One-Command Deploy]]
- [[Specs/035 SaaS CLI Remote/035 SaaS CLI Remote|035 SaaS CLI Remote]]
- [[Specs/036 SaaS Observability MLflow Proxy/036 SaaS Observability MLflow Proxy|036 SaaS Observability MLflow Proxy]]
- [[Specs/037 SaaS Resilience DR/037 SaaS Resilience DR|037 SaaS Resilience DR]]

## Shared Decisions

- [[Reference/SaaSArchitectureDecisions|SaaS Architecture Decisions (AD-1..AD-17)]]

## Artifacts (historical)

- [[016 SaaS Architecture - data-model|data-model]]
- [[016 SaaS Architecture - plan|plan]]
- [[016 SaaS Architecture - quickstart|quickstart]]
- [[016 SaaS Architecture - research|research]]
- [[016 SaaS Architecture - shippable-features|shippable-features]]
- [[016 SaaS Architecture - spec|spec]]
- [[016 SaaS Architecture - tasks|tasks]]

## References

- [[Specs/Specs|Specs]]
