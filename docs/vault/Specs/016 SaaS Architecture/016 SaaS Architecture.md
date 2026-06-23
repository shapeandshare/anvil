---
title: 016 SaaS Architecture
type: spec
tags:
  - type/spec
  - domain/infrastructure
spec-refs:
  - docs/vault/Specs/016 SaaS Architecture/
status: draft
created: '2026-06-19'
updated: '2026-06-22'
aliases:
  - 016 SaaS Architecture
---

# 016 SaaS Architecture

## Summary

A new user visits anvil.io and either signs in with Google/GitHub or creates a passwordless account via email magic link (Cognito Hosted UI). They are authenticated and redirected to the dashboard. Session management (tokens, refresh, MFA) is handled entirely by Cognito.

## Artifacts

- [[016 SaaS Architecture - data-model|data-model]]
- [[016 SaaS Architecture - plan|plan]]
- [[016 SaaS Architecture - quickstart|quickstart]]
- [[016 SaaS Architecture - research|research]]
- [[016 SaaS Architecture - spec|spec]]
- [[016 SaaS Architecture - tasks|tasks]]

## References

- [[Specs/Specs|Specs]]
