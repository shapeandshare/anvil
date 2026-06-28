---
title: 035 SaaS CLI Remote - data-model
type: data-model
tags:
  - type/spec
  - domain/infrastructure
  - domain/tooling
spec-refs:
  - docs/vault/Specs/035 SaaS CLI Remote/
related:
  - '[[035 SaaS CLI Remote]]'
created: '2026-06-27'
updated: '2026-06-27'
status: draft
---

# Data Model: SaaS CLI Remote & Cluster Management

This data model covers the local CLI-side storage: the cluster registry (`~/.anvil/clusters.json`), cached credentials (`~/.anvil/credentials/`), and the `GET /v1/version` response contract.

---

## Cluster Registry (`~/.anvil/clusters.json`)

The cluster registry holds metadata about known SaaS deployments. It is managed by `anvil remote cluster *` commands and auto-populated by `anvil deploy init` ([[Specs/034 SaaS One-Command Deploy/034 SaaS One-Command Deploy|034]]). See `contracts/cluster-registry-schema.md` for the full JSON schema.

### Top-Level Structure

| Field | Type | Description |
|-------|------|-------------|
| `active` | `str \| null` | Name of the active/default cluster. `null` if no active cluster set. |
| `clusters` | `[ClusterEntry]` | Array of known clusters. |

### ClusterEntry

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | `str` | Yes | User-assigned alias (unique across entries) |
| `url` | `str` | Yes | CloudFront URL or custom domain |
| `api_url` | `str` | Yes | API base path (typically `{url}/v1`) |
| `region` | `str` | Yes | AWS region the cluster is deployed in |
| `auth_method` | `enum("deploy", "device_grant")` | Yes | How to authenticate with this cluster |
| `cognito_domain` | `str` | Yes* | Cognito domain for device-grant auth. Required when `auth_method = "device_grant"`. |
| `cognito_client_id` | `str` | Yes* | Cognito app client ID. Required when `auth_method = "device_grant"`. |
| `api_version` | `str` | Yes | API version reported by `GET /v1/version` |
| `deployed_at` | `str` (ISO 8601) | Yes | When the cluster was deployed (or when it was added to the registry) |
| `last_login` | `str` (ISO 8601) \| `null` | No | Most recent successful login timestamp |

### AuthMethod Enum

```python
from enum import StrEnum

class AuthMethod(StrEnum):
    DEPLOY = "deploy"          # deploy-time admin credentials (auto-populated by anvil deploy init)
    DEVICE_GRANT = "device_grant"  # Cognito OAuth2 device authorization grant (RFC 8628)
```

### Validation Rules

- `name` MUST be unique across all entries
- `name` MUST match `^[a-zA-Z0-9_-]+$` (no spaces or special characters)
- `url` MUST be a valid HTTPS URL
- `region` MUST be a valid AWS region identifier
- When `auth_method = "device_grant"`, `cognito_domain` and `cognito_client_id` are required
- When `auth_method = "deploy"`, `cognito_domain` and `cognito_client_id` should be absent (admin credentials live in deploy config, not the registry)

---

## Credential Storage (`~/.anvil/credentials/`)

### Directory Layout

```
~/.anvil/
├── clusters.json          # Cluster registry (0600)
├── credentials/           # Credential cache directory (0700)
│   ├── prod               # JWT cache for "prod" cluster (0600)
│   ├── staging-eu         # JWT cache for "staging-eu" cluster (0600)
│   └── ...                # One file per cluster
└── deploy-config.json     # Deploy config (separate, managed by spec 034)
```

### Credential File Schema

Each credential file is named after the cluster alias and contains:

| Field | Type | Description |
|-------|------|-------------|
| `cluster` | `str` | Cluster name (matches registry entry name) |
| `access_token` | `str` | Cognito access token (JWT) |
| `refresh_token` | `str` | Cognito refresh token |
| `id_token` | `str` | Cognito ID token (JWT) |
| `expires_at` | `str` (ISO 8601) | Access token expiry timestamp |

### Permission Model

| Path | Permissions | Enforced By |
|------|-------------|-------------|
| `~/.anvil/credentials/` | `0700` (owner only) | CredentialStore on create |
| `~/.anvil/credentials/<name>` | `0600` (owner read/write) | CredentialStore on write |

---

## GET /v1/version Response

See `contracts/version-response.md` for the full contract. Summary:

| Field | Type | Description |
|-------|------|-------------|
| `api_version` | `str` (semver) | API wire protocol version |
| `anvil_version` | `str` (semver) | Deployed anvil package version |
| `min_cli_version` | `str` (semver) | Minimum CLI version required |

```python
from pydantic import BaseModel

class VersionResponse(BaseModel):
    api_version: str       # e.g. "1.0"
    anvil_version: str     # e.g. "1.2.3"
    min_cli_version: str   # e.g. "1.1.0"
```

---

## RemoteResourceType Enum

Used by `anvil remote ls` and push/pull commands to identify resource types:

```python
from enum import StrEnum

class RemoteResourceType(StrEnum):
    CORPORA = "corpora"
    DATASETS = "datasets"
    EXPERIMENTS = "experiments"
    MODELS = "models"
```
