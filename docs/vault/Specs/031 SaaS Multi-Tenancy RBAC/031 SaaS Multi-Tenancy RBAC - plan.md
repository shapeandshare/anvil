---
title: 031 SaaS Multi-Tenancy RBAC - plan
type: plan
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

# Implementation Plan: SaaS Multi-Tenancy & RBAC

**Spec**: 031 · **Phase**: 4 (US3) · **Gate**: G4
**Dependencies**: Phase 3 (Auth) — org/role resolution needs validated JWT identity
**Input**: Spec `031 SaaS Multi-Tenancy RBAC - spec.md`, data-model.md, contracts/

## Summary

Add full RBAC multi-tenancy: Organization/Team/Membership/TeamMembership/User models, Role enum + permission matrix, `org_id`/`team_id`/`created_by` ownership columns on existing resources, Alembic migration, org-scoped repository queries, RBAC resolution middleware, service-layer permission guard, `is_cluster_admin` flag + cluster-admin action matrix (FR-037a/b), local-mode auth bypass (FR-038b, org_id=None → no filter → all rows), org/team/member management API, cross-org isolation tests.

## Technical Context

**Language**: Python 3.11+
**Dependencies**: SQLAlchemy[asyncio] (existing), FastAPI (existing), Pydantic (existing)
**Storage**: SQLite (local), PostgreSQL (SaaS)
**Key patterns**: `org_id: int | None` parameter on all repository methods; local mode passes `None` → no scoping. Ownership columns nullable for existing rows.

## Implementation Phasing

### Step 1 — RBAC Models (T024–T028)

Create ORM models: Organization, Team, Membership, TeamMembership, User (with `is_cluster_admin` flag). Each model gets its own file under `anvil/db/models/`.

### Step 2 — Role Enum & Permission Matrix (T029)

Define `Role` enum and permission matrix in `anvil/services/auth/role.py`. The matrix maps actions to minimum required role. Effective role = team `role_override` if present, else org `Membership.role`.

### Step 3 — Ownership Columns + Migration (T030–T031)

Add `org_id`/`team_id`/`created_by` columns to `Corpus` and `Dataset` models. Create Alembic migration for all RBAC tables + ownership columns. All new FK columns are nullable for existing local DB compatibility.

### Step 4 — Scoped Repositories (T032)

Update `CorpusRepository` and `DatasetRepository` (and any resource repository) to accept `org_id: int | None`. When `org_id` is None (local mode), no org filter is applied. When `is_cluster_admin` is true, the org filter is also bypassed (cross-org read).

### Step 5 — RBAC Middleware + Guard (T033–T034)

Implement RBAC resolution middleware in `anvil/_saas/auth/rbac.py` — resolves org/team/effective-role from JWT. Implement service-layer permission guard in `anvil/services/auth/guard.py` — checks action against resource owner and caller's role.

### Step 6 — Org/Team/Member API (T035)

Implement CRUD API for organizations, teams, and memberships at `anvil/api/v1/organizations.py`. Includes invite, role assignment, removal.

### Step 7 — Storage Scoping (T036)

Update storage paths — SaaS uses `{org_id}/...` prefix.

### Step 8 — Cross-Org Isolation Tests (T037)

Add cross-org RBAC negative tests at `tests/integration/test_rbac_isolation.py` + the dedicated local-mode "returns all rows" test at `tests/integration/test_local_mode_no_scoping.py`.

## Complexity Tracking

| Item | Justification |
|------|---------------|
| RBAC complexity (org/team/role) added in v1 | User requirement; Oracle review confirmed retrofitting `tenant_id` post-launch is painful (HIGH finding). First-class now. |
| Cluster admin two-tier model (read-wide, write-narrow) | `is_cluster_admin` boolean on `users` table. Elevates READ/LIST scoping (cross-org visibility) + a fixed cluster-operation action matrix (FR-037b), but does NOT bypass the org-role guard for tenant-data WRITES. Resolves the read-vs-write authority conflict. Local mode has implicit full access (no auth). |
| Ownership columns nullable | Required so existing local DB migrates without breaking demo bootstrap. The absence of an org_id means "unfiltered" in local mode per FR-038b. |

## Dependency Changes

No new runtime dependencies. The `anvil/services/auth/` package and `anvil/db/models/` RBAC models use only existing project dependencies (SQLAlchemy, Pydantic, FastAPI).

## References

- [[031 SaaS Multi-Tenancy RBAC - spec|spec]]
- [[031 SaaS Multi-Tenancy RBAC - tasks|tasks]]
- [[031 SaaS Multi-Tenancy RBAC - data-model|data-model]]
- [[Reference/SaaSArchitectureDecisions|SaaS Architecture Decisions]] (AD-8, AD-14)
