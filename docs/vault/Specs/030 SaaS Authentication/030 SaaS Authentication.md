---
title: 030 SaaS Authentication
type: spec
tags:
  - type/spec
  - domain/infrastructure
spec-refs:
  - docs/vault/Specs/030 SaaS Authentication/
status: draft
created: '2026-06-27'
updated: '2026-06-27'
aliases:
  - 030 SaaS Authentication
---

# 030 SaaS Authentication

## Summary

App-managed OIDC/JWT authentication via Amazon Cognito User Pools for the anvil SaaS mode. FastAPI validates Cognito JWTs directly using `aws-jwt-verify` (AD-2) — the ALB does NOT perform `authenticate-cognito`. Native email/password users work out of the box; social login (Google, GitHub) is optional and configured post-deploy via BYO OAuth credentials (AD-3). SSE endpoints use short-lived signed query-param tokens. CLI authentication uses the OAuth2 device authorization grant flow (RFC 8628). A local `users` table maps Cognito `sub` (UUID) to a local integer `user_id` created on first login.

## Artifacts

- [[030 SaaS Authentication - data-model|data-model]]
- [[030 SaaS Authentication - plan|plan]]
- [[030 SaaS Authentication - quickstart|quickstart]]
- [[030 SaaS Authentication - research|research]]
- [[030 SaaS Authentication - spec|spec]]
- [[030 SaaS Authentication - tasks|tasks]]

## Parent

[[Specs/016 SaaS Architecture/016 SaaS Architecture|016 SaaS Architecture (superseded umbrella)]]

## Decisions

- [[Reference/SaaSArchitectureDecisions|SaaS Architecture Decisions]] — AD-2 (app-managed OIDC/JWT), AD-3 (native default, BYO social)

## References

- [[Specs/Specs|Specs]]
- [[Specs/028 SaaS Abstraction Framework/028 SaaS Abstraction Framework|028 SaaS Package Structure]]
- [[Specs/029 SaaS Dev Stack/029 SaaS Dev Stack|029 SaaS Abstractions]]