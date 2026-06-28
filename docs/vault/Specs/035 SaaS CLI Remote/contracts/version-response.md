---
title: /v1/version Response Contract
type: reference
tags:
  - type/reference
  - domain/infrastructure
spec-refs:
  - docs/vault/Specs/035 SaaS CLI Remote/
related:
  - '[[035 SaaS CLI Remote]]'
created: '2026-06-27'
updated: '2026-06-27'
status: draft
---

# GET /v1/version Response Contract

The unauthenticated version endpoint every SaaS deployment MUST expose.

## Contract

### Request

```
GET /v1/version
```

No authentication required. No request body. No query parameters.

### Response

**Status**: `200 OK`

**Content-Type**: `application/json`

**Body**:

```json
{
  "api_version": "1.0",
  "anvil_version": "1.2.3",
  "min_cli_version": "1.1.0"
}
```

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `api_version` | `string` (semver major.minor) | Yes | API wire protocol version. Incremented on breaking changes to the API surface that the CLI consumes. |
| `anvil_version` | `string` (semver) | Yes | The anvil package version currently deployed on this cluster. |
| `min_cli_version` | `string` (semver) | Yes | The minimum CLI version that can safely communicate with this cluster. SHOULD default to the same as `anvil_version` for first-party clusters. |

### CLI Behavior

1. On `anvil remote cluster add <url>`: the CLI calls `GET {url}/v1/version` immediately after resolving the cluster URL. The response is cached in `~/.anvil/clusters.json` under the `api_version` field.
2. Before every remote data operation (`push`, `pull`, `ls`, `login`): the CLI loads the cached `min_cli_version` from the registry and compares it against the installed anvil package version.
3. If the CLI version < `min_cli_version`, the operation is refused with:
   ```
   Error: anvil CLI v1.0.0 is below cluster minimum v1.1.0.
   Upgrade with: pip install --upgrade anvil
   ```
4. If the endpoint is unreachable (network error, timeout), the CLI warns but proceeds (assumes compatibility).

### Error Responses

| Status | Condition |
|--------|-----------|
| `404` | No route registered (pre-v1.0 cluster). CLI should proceed assuming compatibility. |
| `503` | Cluster is starting up or degraded. CLI should retry with backoff. |

## Pydantic Model

```python
from pydantic import BaseModel


class VersionResponse(BaseModel):
    """Response from GET /v1/version."""

    api_version: str       # e.g. "1.0"
    anvil_version: str     # e.g. "1.2.3"
    min_cli_version: str   # e.g. "1.1.0"
```
