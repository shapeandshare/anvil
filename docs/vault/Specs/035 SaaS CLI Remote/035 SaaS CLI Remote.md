---
title: 035 SaaS CLI Remote
type: spec
tags:
  - type/spec
  - domain/infrastructure
  - domain/tooling
spec-refs:
  - docs/vault/Specs/035 SaaS CLI Remote/
status: draft
created: '2026-06-27'
updated: '2026-06-27'
aliases:
  - 035 SaaS CLI Remote
---

# 035 SaaS CLI Remote & Cluster Management

## Summary

A local anvil user connects to a SaaS deployment via `anvil remote` CLI commands — authenticating via Cognito device authorization grant (RFC 8628), managing a multi-cluster registry at `~/.anvil/clusters.json`, and syncing data (corpora, datasets, models, experiments) via signed S3 URLs. API-version negotiation via `GET /v1/version` prevents silent breakage when clusters run newer APIs than the local CLI. Spec 035 owns FR-014, FR-014a, FR-014b, FR-014c, and the CLI-auth aspect of FR-021 (device grant — shared with spec 030).

## Artifacts

- [[035 SaaS CLI Remote - spec|spec]]
- [[035 SaaS CLI Remote - plan|plan]]
- [[035 SaaS CLI Remote - tasks|tasks]]
- [[035 SaaS CLI Remote - research|research]]
- [[035 SaaS CLI Remote - data-model|data-model]]
- [[035 SaaS CLI Remote - quickstart|quickstart]]

## Parent

[[Specs/016 SaaS Architecture/016 SaaS Architecture|016 SaaS Architecture (superseded umbrella)]]

## Decisions

- AD-15 — Multi-cluster CLI: `~/.anvil/clusters.json` registry + `GET /v1/version` negotiation

## References

- [[Reference/SaaSArchitectureDecisions|SaaS Architecture Decisions]]
- [[Specs/030 SaaS Authentication/030 SaaS Authentication|030 SaaS Auth]] — shared FR-021 device-grant flow
- [[Specs/034 SaaS One-Command Deploy/034 SaaS One-Command Deploy|034 SaaS Deploy]] — auto-populates cluster registry
- [[Specs/Specs|Specs]]
