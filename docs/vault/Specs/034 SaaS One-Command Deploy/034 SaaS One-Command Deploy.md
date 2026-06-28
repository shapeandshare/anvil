---
title: 034 SaaS One-Command Deploy
type: spec
tags:
  - type/spec
  - domain/infrastructure
spec-refs:
  - docs/vault/Specs/034 SaaS One-Command Deploy/
status: draft
created: '2026-06-27'
updated: '2026-06-27'
aliases:
  - 034 SaaS One-Command Deploy
---

# 034 SaaS One-Command Deploy

## Summary

A user runs a single command to deploy the full anvil SaaS stack into their own AWS account with no Node.js, CDK CLI, or manual console steps required. The same CLI handles lifecycle operations (destroy, update, config, restore) and includes a 3-layer automated verification loop (`anvil deploy verify`) that validates infrastructure, API flows, and browser behavior. Cluster-registry auto-add/remove ensures the local CLI stays in sync with the deployments it manages.

## Artifacts

- [[034 SaaS One-Command Deploy - data-model|data-model]]
- [[034 SaaS One-Command Deploy - plan|plan]]
- [[034 SaaS One-Command Deploy - quickstart|quickstart]]
- [[034 SaaS One-Command Deploy - research|research]]
- [[034 SaaS One-Command Deploy - spec|spec]]
- [[034 SaaS One-Command Deploy - tasks|tasks]]

## Parent

[[Specs/016 SaaS Architecture/016 SaaS Architecture|016 SaaS Architecture (superseded umbrella)]]

## Decisions

[[Reference/SaaSArchitectureDecisions|SaaS Architecture Decisions]] — AD-3, AD-6, AD-7

## References

- [[Specs/Specs|Specs]]