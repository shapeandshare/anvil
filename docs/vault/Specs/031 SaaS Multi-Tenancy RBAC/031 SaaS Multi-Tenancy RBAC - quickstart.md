---
title: 031 SaaS Multi-Tenancy RBAC - quickstart
type: quickstart
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

# Quickstart: SaaS Multi-Tenancy & RBAC Development

## Prerequisites

- Phase 3 (Auth) complete — Cognito JWT identity resolution available
- Local development via `make run` (local mode) or `docker compose up` (SaaS emulation)
- Alembic migration framework available

## Code Layout

```
anvil/db/models/
├── organization.py        # T024 — Organization ORM model
├── team.py                # T025 — Team ORM model
├── membership.py          # T026 — Membership (User↔Organization with role)
├── team_membership.py     # T027 — TeamMembership (User↔Team with role override)
└── user.py                # T028 — User model with is_cluster_admin flag

anvil/services/auth/
├── role.py                # T029 — Role enum + permission matrix
└── guard.py               # T034 — Service-layer permission guard

anvil/_saas/auth/
└── rbac.py                # T033 — RBAC resolution middleware

anvil/api/v1/
└── organizations.py       # T035 — Org/team/member management API
```

## Development Workflow

### 1. Create Models (T024–T028)

```bash
# Create ORM models in parallel (they have no cross-dependencies)
# T024: anvil/db/models/organization.py
# T025: anvil/db/models/team.py
# T026: anvil/db/models/membership.py
# T027: anvil/db/models/team_membership.py
# T028: anvil/db/models/user.py + is_cluster_admin migration
```

### 2. Define Role Enum (T029)

```python
# anvil/services/auth/role.py
class OrgRole(StrEnum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"
    VIEWER = "viewer"
```

### 3. Migration (T030–T031)

```bash
# Add ownership columns to Corpus/Dataset, create RBAC tables
alembic revision --autogenerate -m "add rbac tables and ownership columns"
alembic upgrade head
```

### 4. Scoped Repositories (T032)

```python
# Repository methods accept org_id: int | None
async def list_corpora(self, org_id: int | None = None) -> list[Corpus]:
    query = select(Corpus)
    if org_id is not None:
        query = query.where(Corpus.org_id == org_id)
    # ... execute
```

### 5. Middleware + Guard (T033–T034)

```python
# Middleware resolves from JWT:
# - org_id, user_id, is_cluster_admin, effective_role

# Guard checks action against role matrix:
guard.require(ctx, Action.DELETE, resource_owner_org_id=org_id)
```

### 6. Management API (T035)

Endpoints at `/v1/organizations/`:
- `POST /v1/organizations` — create org
- `GET /v1/organizations` — list orgs (scoped or cross-org for cluster admin)
- `POST /v1/organizations/{id}/members` — invite member
- `PUT /v1/organizations/{id}/members/{user_id}/role` — assign role
- `DELETE /v1/organizations/{id}/members/{user_id}` — remove member
- `POST /v1/organizations/{id}/teams` — create team
- `DELETE /v1/organizations/{id}/teams/{team_id}` — delete team

### 7. Testing (T037)

```bash
# Cross-org isolation tests
pytest tests/integration/test_rbac_isolation.py -v

# Local mode no-scoping test
pytest tests/integration/test_local_mode_no_scoping.py -v
```

## Verification

Run the full Gate G4 checklist:
```bash
make test           # all existing tests pass
make lint           # zero new lint errors
make typecheck      # mypy --strict clean
pytest tests/integration/test_rbac_isolation.py -v   # cross-org isolation
pytest tests/integration/test_local_mode_no_scoping.py -v  # local mode unfiltered
```

## References

- [[031 SaaS Multi-Tenancy RBAC]]
- [[031 SaaS Multi-Tenancy RBAC - spec|spec]]
- [[031 SaaS Multi-Tenancy RBAC - plan|plan]]
- [[031 SaaS Multi-Tenancy RBAC - tasks|tasks]]
- [[031 SaaS Multi-Tenancy RBAC - data-model|data-model]]
- [[Specs/030 SaaS Authentication/030 SaaS Authentication - quickstart|030 SaaS Auth quickstart]]
