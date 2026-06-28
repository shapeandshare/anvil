---
title: 031 SaaS Multi-Tenancy RBAC - spec
type: spec
tags:
  - type/spec
  - domain/architecture
spec-refs:
  - docs/vault/Specs/031 SaaS Multi-Tenancy RBAC/
related:
  - '[[031 SaaS Multi-Tenancy RBAC]]'
  - '[[Specs/030 SaaS Authentication/030 SaaS Authentication|030 SaaS Auth]]'
created: '2026-06-27'
updated: '2026-06-27'
status: draft
---

# Feature Specification: SaaS Multi-Tenancy & RBAC

**Spec**: 031 — Multi-Tenancy & RBAC · **Phase**: 4 (US3) · **Gate**: G4
**Owning spec**: [[031 SaaS Multi-Tenancy RBAC]]
**Parent**: [[Specs/016 SaaS Architecture/016 SaaS Architecture|016 SaaS Architecture (superseded umbrella)]]
**Dependencies**: [[Specs/030 SaaS Authentication/030 SaaS Authentication|030 SaaS Auth]] (JWT identity resolution)
**FRs owned**: FR-034, FR-035, FR-036, FR-037, FR-037a, FR-037b, FR-038, FR-038a, FR-038b
**Decisions**: AD-8, AD-14

## User Story 3 — SaaS User Sees Only Their Own Data (Priority: P1)

A user's corpora, datasets, experiments, and models are isolated from other users. No user can see or access another user's data through any API endpoint or the web UI.

**Why this priority**: Multi-tenant data isolation is non-negotiable for a SaaS product. Without this, no user will trust the platform with their data.

**Independent Test**: Create two separate user accounts (User A and User B). User A creates a corpus. Log in as User B — verify User B sees an empty corpus list. User B creates their own corpus and confirms they see only their own.

**Acceptance Scenarios**:

1. **Given** two registered users with data, **When** either user views their dashboard, **Then** they see only their own corpora, datasets, experiments, and models.
2. **Given** a user makes an API call, **When** the request is processed, **Then** all database queries are scoped by `org_id` (resolved from the user's membership) and filtered by team/role visibility.
3. **Given** one user's training job is running, **When** another user starts a job, **Then** both jobs run concurrently in separate compute pods with no data cross-contamination.

## Requirements

### RBAC & Multi-Tenancy

- **FR-034**: The system MUST implement a two-tier admin hierarchy with org-scoped RBAC beneath it. The tiers are:
  1. **Cluster admin** — a system-level principal with cross-org **read** visibility and a fixed cluster-operation action matrix (FR-037a/b). Cluster admins view all orgs/jobs/experiments, perform cluster operations (suspend orgs, cancel jobs, manage cluster admins), and manage the deployment (update, destroy, configure). They do NOT get blanket write access to tenant data. A user is a cluster admin by virtue of the `is_cluster_admin` boolean flag on their `users` row, not by org membership.
  2. **Org-scoped RBAC** (below): `Organization` (top-level isolation/billing boundary) → `Team` (group within an org) → `User` (member of org/teams). A regular user belongs to exactly one organization but MAY belong to multiple teams within it.
- **FR-035**: The system MUST support org-scoped roles `owner`, `admin`, `member`, `viewer` assigned at the organization level and optionally overridden at the team level. Additionally, the `is_cluster_admin` boolean on the `users` table provides read-wide cross-org visibility plus the cluster-operation action matrix (FR-037a/b) — it does NOT bypass the org-role guard for tenant-data writes. A user MAY be both a cluster admin and an org member simultaneously. Role determines permitted actions (create/read/update/delete/manage-members).
- **FR-036**: Every resource (corpus, dataset, training job, model) MUST be owned by `org_id` (required), `team_id` (optional), and `created_by` user_id. Repository **read/list** queries MUST be scoped by `org_id` for regular users and unfiltered (cross-org) for cluster admins (FR-037a). Repository **write/mutate** operations remain gated by the org-role guard for all users, including cluster admins (FR-037b) — the cross-org read elevation does NOT extend to writes.
- **FR-037**: Authorization MUST be enforced at three layers: (1) a FastAPI middleware that resolves the caller's org/team/role and `is_cluster_admin` flag from the validated JWT, (2) a service-layer permission guard that checks the action against the resource owner and the caller's role, and (3) the cluster-admin elevation described in FR-037a. No DB query may return cross-org data for non-cluster-admin users.
- **FR-037a — Cluster admin scope (read-wide, write-narrow)**: The `is_cluster_admin` flag elevates a caller for **org-ID scoping** (read/list visibility) but does NOT grant a blanket bypass of all permission checks. Precisely:
  - **Read/list operations**: a cluster admin bypasses `org_id` scoping — repository queries return cross-org data. This is the "read-wide" capability.
  - **Write/mutate operations**: a cluster admin is evaluated against an explicit **cluster-admin action matrix**, NOT the org role matrix and NOT an unconditional allow. Destructive tenant-data operations (delete corpus/dataset/model/job in an org the admin is not an owner of) are NOT permitted by the cluster-admin flag alone.
  - This resolves the apparent conflict: there is no "skip all checks" path. The flag changes the *scoping predicate* (which rows are visible) and grants a *fixed set of cluster-operation permissions* (FR-038a), but tenant-data mutation still flows through the org-role guard.
- **FR-037b — Cluster-admin action matrix**: The set of actions a cluster admin MAY perform purely by virtue of `is_cluster_admin` (without org membership) MUST be explicitly enumerated and is limited to:
  - READ/LIST any resource in any org (corpora, datasets, jobs, models, experiments, usage, members)
  - Suspend/reactivate an organization (org lifecycle, not data deletion)
  - Create and remove other cluster admins (up to a configurable limit)
  - Cluster operations: view health, view logs, restart cluster services, view cross-org usage/billing
  - Cancel any running training job (operational safety — runaway job mitigation)
  - Actions NOT in this matrix (e.g., delete a corpus, modify a dataset, change an org's settings) require the cluster admin to ALSO hold the appropriate org role. A cluster admin who is not a member of Org B cannot delete Org B's corpus.
- **FR-038**: An organization owner/admin MUST be able to invite users, create teams, assign roles, and remove members via API. The first admin (created at deploy) is created as a cluster admin AND org owner of the default org.
- **FR-038a — Cluster admin capabilities**: A cluster admin MUST be able to (per the FR-037b action matrix):
  - View and list all organizations, their members, and their resources (cross-org read)
  - Access the MLflow proxy across all orgs (read)
  - View all jobs, experiments, models, and usage across the cluster (read)
  - Access the operations page and System Actions (health, logs, service control) for the entire deployment
  - Suspend/reactivate organizations and cancel runaway jobs (cluster operations)
  - Invite new cluster admins (self-service, up to a configurable limit)
  - A cluster admin MUST NOT delete or mutate tenant data (corpora, datasets, models) in an org where they do not hold an org `owner`/`admin` role. Cluster admin scope is cross-org observation, org lifecycle, and cluster operations — NOT tenant data ownership. (Enforced by FR-037b, not merely advisory.)
- **FR-038b — Local mode auth bypass**: In local mode (`ANVIL_MODE` unset or `local`), the system MUST NOT require JWT authentication. All API routes and UI pages MUST be accessible without authentication. All repository queries MUST return unfiltered data (no org scoping). All documented cluster admin capabilities (FR-038a) are implicitly available to the local-mode user — the `is_cluster_admin` flag and org roles are not consulted in local mode. This preserves the existing single-user experience where `anvil serve` works immediately with no auth setup.

### Key Entities

- **Cluster admin**: A system-level principal identified by `users.is_cluster_admin = true`. Has **read-wide** cross-org visibility (all resources, jobs, experiments, MLflow data) and a fixed **cluster-operation action matrix** (FR-037b: org suspend/reactivate, cancel any job, manage cluster admins, view health/logs). Does NOT have blanket write access to tenant data — deleting/mutating another org's corpora/datasets/models requires an explicit org role in that org. Manages deployment lifecycle (update, destroy, configure) via the deploy CLI. Distinct from org-scoped RBAC roles — a single user may be both a cluster admin and an org member. The deploy-created user is the initial cluster admin.
- **Organization**: The top-level tenant and billing boundary. Owns all resources. Has one owner, many admins/members. Cluster admins can view all organizations regardless of membership.
- **Team**: A group of users within an organization. Resources MAY be scoped to a team. A user may belong to multiple teams.
- **Role**: One of `owner`, `admin`, `member`, `viewer` — scoped to an organization. The `is_cluster_admin` flag on the user is separate and provides system-level access that bypasses all org-scoped role checks. A cluster admin may also hold any org role simultaneously.
- **User**: An authenticated account managed by Cognito, identified by Cognito `sub` (UUID). Local `users` table maps `cognito_sub` → integer `user_id`. Carries an `is_cluster_admin` boolean (default `false`). Belongs to one organization, zero or more teams. In local mode, authentication is bypassed and all operations run as an implicit admin.
- **Membership**: The association of a User to an Organization (with role) and to Teams (with optional role override).

## Success Criteria

- **SC-014**: A user in one organization can never read, list, or mutate any resource owned by another organization, verified by automated cross-org RBAC negative tests.
- **SC-020**: A cluster admin (created by `anvil deploy init`) can log in and **view** resources across all organizations, access the MLflow proxy across all experiments, and use the operations page — without being an explicit member of any org. A cluster admin who is NOT an org member of Org B is **denied** when attempting to delete/mutate Org B's tenant data (read-wide, write-narrow per FR-037a/b). A non-admin user in Org A cannot see Org B's data. In local mode (`anvil serve`), the user has full access without authentication.

## Acceptance Gate G4 — RBAC + Data Isolation

| ID | Criterion | Verification | Pass Condition |
|----|-----------|--------------|----------------|
| G4.1 | Org/Team/Role/User schema migrated including `is_cluster_admin` column | AWS API: query `information_schema` | All RBAC tables present, `users.is_cluster_admin` exists |
| G4.2 | User in Org A cannot see Org B data | API canary: two orgs, cross-access attempt | 403/empty for cross-org |
| G4.3 | Role permissions enforced (viewer cannot delete) | API canary: viewer attempts delete | 403 returned |
| G4.4 | Cluster admin reads cross-org but cannot write foreign tenant data | API canary: admin with `is_cluster_admin=true` lists cross-org (returns data) AND attempts delete in a non-member org (denied) | Cross-org read returns data; foreign-org delete → 403 |
| G4.5 | Storage paths scoped by org_id | Inspect S3 keys after upload | Keys under `{org_id}/...` |
| G4.6 | Local mode allows all operations without auth | `make run` + API calls without JWT | 200, all data returned unfiltered |

## Local-Mode Regression Gate (LMRG)

This spec inherits the **standard Local-Mode Regression Gate** from Feature 4 of the shippable-features breakdown. The definition of Done for all work in this spec includes ALL of:

```bash
make test            # all pre-existing tests pass UNMODIFIED (SC-007)
make lint            # zero new lint errors
make typecheck       # mypy --strict clean; no SaaS imports leaking into non-SaaS modules
pip install .        # clean install
anvil serve          # boots; UI at :8080 works end-to-end (upload → train → SSE → export)
```

Plus the **import-isolation assertion**:

```bash
python - <<'PY'
import importlib, sys
import anvil.api.app          # local entrypoint must import with zero cloud deps
for forbidden in ("boto3", "redis", "aws_jwt_verify", "opentelemetry", "prometheus_client"):
    assert forbidden not in sys.modules, f"{forbidden} loaded by local entrypoint"
print("import isolation OK")
PY
```

### Dedicated local-mode "returns all rows" test

Per the shippable-features breakdown (Feature 4), the following pytest MUST be added:

```python
# tests/integration/test_local_mode_no_scoping.py
import pytest

@pytest.mark.asyncio
async def test_local_mode_returns_unfiltered_data(client):
    """In local mode (no auth, org_id=None) every resource list returns all rows (FR-038b)."""
    r = await client.get("/v1/corpora")
    assert r.status_code == 200          # no 401 — auth not required locally
    # Demo bootstrap seeds corpora; local mode must see them with no org filter applied.
    assert len(r.json()["corpora"]) > 0
```

The new ownership columns MUST be **nullable** (or default to a local sentinel org) so the existing local DB migrates without breaking demo bootstrap.

## Edge Cases

- **Repository queries in local mode**: Repositories accept `org_id: int | None`; local mode passes `None` → no `WHERE org_id` filter → all rows returned, preserving the single-user experience.
- **Cluster admin as org member**: A user MAY be both a cluster admin and an org member simultaneously. The cluster-admin elevation and org-role guard compose: a cluster-admin org-member gets both cross-org read AND the org role's write permissions in their own org. In a foreign org, they get cross-org read only (no write).
- **Team role override**: A user's role in a team is the `TeamMembership.role_override` if present, otherwise the `Membership.role` at the org level. This is resolved at the middleware layer and cached per-request.
- **Ownership column nullability**: `org_id`/`team_id`/`created_by` columns on `Corpus`, `Dataset` and other resources MUST be nullable so existing local DB rows (which have no org) migrate without error. Local mode ignores these columns in queries.

## Architecture Decisions (AD-8, AD-14)

See [[Reference/SaaSArchitectureDecisions|SaaS Architecture Decisions]] for the canonical full text.

### AD-8: Multi-Tenancy — Full RBAC (Cluster Admin + Organization → Team → User → Role)

**Decision**: Two-tier admin model from v1. `is_cluster_admin` is a boolean flag on the `users` table providing **read-wide, write-narrow** system access: it bypasses `org_id` scoping for READ/LIST operations and grants a fixed cluster-operation action matrix (FR-037b), but does NOT bypass the org-role guard for tenant-data WRITES. Below that, `Organization` is the top-level billing/isolation boundary. `Team` groups users within an org. `Role` (owner/admin/member/viewer) governs permissions within an org. All resources are owned by `org_id` (+ optional `team_id` + `created_by` user_id). Authorization is a middleware + service-layer guard; the cluster-admin elevation changes the read-scoping predicate and adds cluster-operation permissions — it is NOT a blanket "skip all checks" bypass.

### AD-14: Two-Tier Admin — Read-Wide, Write-Narrow

**Decision**: The `is_cluster_admin` flag is read-wide, write-narrow — cross-org read + a fixed cluster-operation action matrix, but tenant-data writes still gated by org role (FR-034–FR-038b). Local mode is implicit admin, no auth.

**Key clarification**: the cluster-admin elevation is NOT a blanket bypass. It widens the read scoping predicate (cross-org visibility) and grants a fixed cluster-operation matrix (suspend orgs, cancel jobs, manage cluster admins, view health/logs), but destructive tenant-data mutation in a foreign org still requires an explicit org role there.

## References

- [[031 SaaS Multi-Tenancy RBAC]]
- [[031 SaaS Multi-Tenancy RBAC - plan|plan]]
- [[031 SaaS Multi-Tenancy RBAC - tasks|tasks]]
- [[031 SaaS Multi-Tenancy RBAC - data-model|data-model]]
- [[Reference/SaaSArchitectureDecisions|SaaS Architecture Decisions]] (AD-8, AD-14)
- [[Specs/016 SaaS Architecture/016 SaaS Architecture - shippable-features|016 shippable-features (Feature 4)]]
- [[Decisions/ADR-030-saas-architecture|ADR-030]]
