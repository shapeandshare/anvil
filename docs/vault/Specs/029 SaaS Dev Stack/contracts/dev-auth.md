---
title: 029 SaaS Dev Stack - Dev Auth Contract
type: reference
tags:
  - type/reference
  - domain/infrastructure
created: '2026-06-27'
updated: '2026-06-27'
status: draft
---

# Dev Auth Contract — SaaS Dev Stack

## Purpose

The dev auth contract defines how the docker compose dev stack replaces production Cognito JWT authentication with a lightweight API key bypass. This enables SaaS-mode route development without an AWS account or real Cognito pool.

## Contract

### Enabling Dev Auth

Dev auth is activated by the `ANVIL_DEV_MODE=true` environment variable. When this variable is absent or set to `false`, the production Cognito JWT middleware is used exclusively.

### Authentication Flow

```
Client → Authorization: Bearer <ANVIL_DEV_API_KEY>
           ↓
anvil-web checks ANVIL_DEV_MODE == "true"
           ↓
anvil-web validates ANVIL_DEV_API_KEY matches
           ↓
Resolves identity to dev admin user
           ↓
Request proceeds with dev user context
```

### API Key Validation

- The key is read from `ANVIL_DEV_API_KEY` env var
- Default value if unset: `anvil-dev-key-change-me`
- The key MUST be sent in the `Authorization` header as `Bearer <key>`
- Mismatched or missing key returns `401 Unauthorized`
- The key validation is constant-time (no timing side channel)

### Resolved Dev Identity

When dev auth is active, the `get_current_user` dependency returns:

| Field | Value |
|-------|-------|
| `id` | `1` |
| `cognito_sub` | `dev-user-0000` |
| `email` | `dev@anvil.dev` |
| `display_name` | `Dev Admin` |
| `is_cluster_admin` | `true` |
| `org_id` | `1` (Dev Org) |

### Middleware Location

`anvil/_saas/auth/dev_setup.py`

### API

```python
def get_dev_auth_dependency() -> Callable:
    """Returns a FastAPI Depends callable that validates the dev API key
    and returns the dev admin user identity.

    Only active when ANVIL_DEV_MODE=true.
    """

def get_current_user_for_dev(token: str = Depends(oauth2_scheme)) -> User:
    """Validates the bearer token against ANVIL_DEV_API_KEY and returns
    the dev admin User object.
    """
```

### Safety Guards

1. Dev auth MUST be gated on `ANVIL_DEV_MODE=true` — never activate in production
2. The module MUST NOT be importable from the local entrypoint (`anvil.api.app:app`) — only from the SaaS entrypoint
3. The default API key (`anvil-dev-key-change-me`) is documented as unsafe for production — operators deploying SaaS MUST NOT set `ANVIL_DEV_MODE=true`
4. The `ANVIL_DEV_MODE` env var is NEVER auto-detected — it must be explicitly set

### Integration with App Factory

The SaaS app factory (`anvil._saas.app:app`) checks `ANVIL_DEV_MODE` at startup:

```python
def create_app() -> FastAPI:
    app = FastAPI(...)
    if os.environ.get("ANVIL_DEV_MODE", "").lower() == "true":
        from anvil._saas.auth.dev_setup import get_dev_auth_dependency
        app.dependency_overrides[get_current_user] = get_dev_auth_dependency()
    else:
        from anvil._saas.auth.verify_jwt import get_current_user_jwt
        app.dependency_overrides[get_current_user] = get_current_user_jwt
    ...
```

## Example Usage

```python
# curl command using dev auth
curl -H "Authorization: Bearer anvil-dev-key-change-me" \
  http://localhost:8080/v1/corpora

# Expected: 200 OK with list of corpora (including seeded demo data)
```

## See Also

- [[029 SaaS Dev Stack - spec|029 spec — FR-012b]]
- [[029 SaaS Dev Stack - quickstart|029 quickstart — Dev auth section]]
- [[Specs/016 SaaS Architecture/016 SaaS Architecture - spec|016 spec — FR-019 (app-managed OIDC/JWT)]]
- [[Reference/SaaSArchitectureDecisions|SaaS Architecture Decisions — AD-2]]