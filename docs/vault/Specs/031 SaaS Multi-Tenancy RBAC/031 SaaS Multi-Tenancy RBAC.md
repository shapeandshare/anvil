---
title: 031 SaaS Multi-Tenancy RBAC
type: spec
tags:
  - type/spec
  - domain/architecture
spec-refs:
  - docs/vault/Specs/031 SaaS Multi-Tenancy RBAC/
status: draft
created: '2026-06-27'
updated: '2026-06-27'
aliases:
  - 031 SaaS Multi-Tenancy RBAC
---

# 031 SaaS Multi-Tenancy RBAC

## Summary

Full RBAC multi-tenancy with data isolation — the core SaaS trust property. Organization is the top-level tenant boundary. Team groups users within an org. Role (owner/admin/member/viewer) governs permissions within an org. A two-tier admin model provides `is_cluster_admin` (read-wide, write-narrow) for operational visibility without blanket write access. All resources are owned by `org_id` (+ optional `team_id` + `created_by`). In local mode the auth bypass (FR-038b) ensures queries return unfiltered data and all operations are available without authentication. This is Feature 4 of the SaaS shippable-features breakdown — the first feature delivering real multi-tenant value.

## Artifacts

- [[031 SaaS Multi-Tenancy RBAC - data-model|data-model]]
- [[031 SaaS Multi-Tenancy RBAC - plan|plan]]
- [[031 SaaS Multi-Tenancy RBAC - quickstart|quickstart]]
- [[031 SaaS Multi-Tenancy RBAC - research|research]]
- [[031 SaaS Multi-Tenancy RBAC - spec|spec]]
- [[031 SaaS Multi-Tenancy RBAC - tasks|tasks]]

## Parent

[[Specs/016 SaaS Architecture/016 SaaS Architecture|016 SaaS Architecture (superseded umbrella)]]

## Decisions

[[Reference/SaaSArchitectureDecisions|SaaS Architecture Decisions]] — specifically AD-8 (Multi-Tenancy — Full RBAC) and AD-14 (Two-Tier Admin — Read-Wide, Write-Narrow).

## References

- [[Specs/Specs|Specs]]
- [[Reference/SaaSArchitecture|SaaSArchitecture]]
- [[Specs/030 SaaS Authentication/030 SaaS Authentication|030 SaaS Auth]] (dependency — provides JWT identity resolution)