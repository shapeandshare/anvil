---
title: 031 SaaS Multi-Tenancy RBAC - research
type: research
tags:
  - type/spec
  - domain/architecture
spec-refs:
  - docs/vault/Specs/031 SaaS Multi-Tenancy RBAC/
related:
  - '[[031 SaaS Multi-Tenancy RBAC]]'
created: '2026-06-27'
updated: '2026-06-27'
status: draft
---

# Research: SaaS Multi-Tenancy & RBAC

**Parent spec**: 031 SaaS Multi-Tenancy RBAC
**Source**: Derived from the 016 umbrella spec Phase 0 research and Oracle review findings.

## Key Research Findings

### 1. RBAC Model — Tenant ID First-Class from v1

The Oracle architecture review for the umbrella spec (ADR-030) identified retrofitting `tenant_id` after launch as a HIGH-risk finding. The binding decision is full RBAC from v1:

- `Organization` is the top-level tenant/isolation boundary
- `Team` groups users within an org
- `Role` (owner/admin/member/viewer) governs permissions at org and team level
- `is_cluster_admin` provides cross-org read visibility without blanket write access

**Finding**: The two-tier admin model (read-wide, write-narrow) resolves a blocking authority conflict — the deploy operator needs application-level cross-org visibility for operational reasons, but that visibility must not become an accidental "god mode" that can silently destroy any tenant's data.

### 2. Local-Mode Auth Bypass

The review confirmed that local mode must remain authentication-free (FR-038b). The key architectural insight: repositories accept `org_id: int | None` as a parameter. Local mode passes `None`, which results in no `WHERE org_id` filter — all rows are returned. This is the simplest model that satisfies both local and SaaS modes.

### 3. Ownership Column Nullability

Existing local databases have no org/team data. All new ownership columns (`org_id`, `team_id`, `created_by`) MUST be nullable so the Alembic migration does not break existing rows. The absence of an `org_id` on a row means "visible in local mode" — foreign-key constraints are optional (no org FK in local mode).

### 4. Effective Role Resolution

The effective role is resolved at the middleware layer per-request and cached:
- If `TeamMembership.role_override` is set → use that
- Otherwise → use `Membership.role` at the org level
- In local mode → no role resolution (bypass all checks)

This is documented in the data-model and the permission matrix.

## References

- [[031 SaaS Multi-Tenancy RBAC]]
- [[031 SaaS Multi-Tenancy RBAC - data-model|data-model]]
- [[Reference/SaaSArchitectureDecisions|SaaS Architecture Decisions]] (AD-8, AD-14)
- [[Decisions/ADR-030-saas-architecture|ADR-030]]
