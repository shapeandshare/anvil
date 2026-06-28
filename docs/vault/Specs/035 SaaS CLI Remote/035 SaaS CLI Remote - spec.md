---
title: 035 SaaS CLI Remote - spec
type: spec
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

# Feature Specification: SaaS CLI Remote & Cluster Management

**Plan phase**: 11 (US9) · **Tasks**: T094–T099
**Branch**: `035-saas-cli-remote`
**Created**: 2026-06-27 · **Status**: Draft

## Scope

This spec owns the `anvil remote` CLI command group: cluster management, device-grant authentication, and data sync (push/pull/ls) between a local anvil installation and one or more SaaS deployments. It also owns `GET /v1/version` API-version negotiation.

### Owned Functional Requirements

- **FR-014** (full) — `anvil remote` command group
- **FR-014a** — Cluster registry at `~/.anvil/clusters.json`
- **FR-014b** — Active/default cluster concept
- **FR-014c** — API version negotiation via `GET /v1/version`
- **FR-021** (device-grant aspect) — CLI authentication via Cognito device authorization grant (RFC 8628). Note: shared with [[Specs/030 SaaS Authentication/030 SaaS Authentication|030 SaaS Auth]]; this spec owns the CLI-side device-grant client, 030 owns the server-side Cognito pool and token endpoint configuration.

### Architecture Decision

- **AD-15** — Multi-cluster CLI: registry at `~/.anvil/clusters.json` (+region, +api_version), cluster management commands, version negotiation, auto-add on deploy init, auto-remove on deploy destroy.

### Dependencies

- **034 SaaS Deploy** — auto-populates cluster registry on `anvil deploy init`; removes entry on `anvil deploy destroy`
- **030 SaaS Auth** — Cognito User Pool, device-grant OAuth endpoints, JWT validation

---

## User Story 9 — Local User Uses CLI to Push/Pull Data from SaaS

A local user has `anvil` installed and wants to upload a corpus from their local machine to a SaaS deployment. They run `anvil remote cluster add`, then `anvil remote login`, then `anvil remote push corpus ./my-data/`. Later, they pull a trained model with `anvil remote pull model 42`.

**Why this priority (P3)**: The CLI bridge connects local workflows to cloud compute. Important for power users, but the web UI upload/download is the primary path.

### Independent Test

Install anvil locally, add a dev cluster via `anvil remote cluster add`, run `anvil remote login` against the dev cluster, run `anvil remote push corpus ./test-data/`, verify the corpus appears in the web UI, run `anvil remote pull model 1`, and verify the file is downloaded locally.

### Acceptance Scenarios

1. **Given** a user with a local anvil install, **When** they run `anvil remote cluster add https://dev.anvil.io`, **Then** the guided wizard prompts for an alias, authenticates (device grant or deploy credentials), calls `GET /v1/version` for version negotiation, and saves the cluster config to `~/.anvil/clusters.json`.
2. **Given** one or more clusters configured, **When** the user runs `anvil remote cluster list`, **Then** all clusters are listed with alias, URL, status (connected/disconnected), and last login time.
3. **Given** a configured cluster, **When** the user runs `anvil remote cluster remove <name>`, **Then** the entry is deleted from the registry and cached credentials are cleaned up.
4. **Given** a configured cluster, **When** the user runs `anvil remote cluster configure <name> --key region --value eu-west-1`, **Then** the registry entry is updated.
5. **Given** a user with a configured cluster, **When** they run `anvil remote login <cluster>`, **Then** the CLI opens a browser for Cognito device authorization grant (RFC 8628), polls the token endpoint, and caches the JWT in `~/.anvil/credentials` (0600 permissions).
6. **Given** an authenticated CLI session, **When** the user runs `anvil remote logout <cluster>`, **Then** the cached credentials for that cluster are deleted.
7. **Given** an authenticated CLI session, **When** the user runs `anvil remote push <cluster> corpus ./my-corpus/`, **Then** the files are uploaded to S3 via signed URLs and a corpus is created in the SaaS database.
8. **Given** an authenticated CLI session, **When** the user runs `anvil remote pull <cluster> model 42`, **Then** a signed S3 URL is generated and the model artifacts are downloaded locally.
9. **Given** an authenticated CLI session, **When** the user runs `anvil remote ls <cluster> corpora`, **Then** the remote corpora list is fetched and displayed.
10. **Given** a single configured cluster, **When** the user runs a remote data command without specifying `<cluster>`, **Then** it defaults to the active cluster (FR-014b).

---

## Requirements

### Functional Requirements

**FR-014** — CLI MUST support remote cluster management and data commands:

- `anvil remote cluster add <url>` — guided wizard to connect to a running SaaS cluster. Prompts for cluster alias, authenticates via Cognito device grant (or deploy credentials for the initial admin), and saves the cluster configuration to the local cluster registry.
- `anvil remote cluster list` — list all configured clusters with their status (connected/disconnected) and URL.
- `anvil remote cluster remove <name>` — remove a cluster configuration from the registry.
- `anvil remote cluster configure <name> [--key value]` — update cluster alias, URL, or credential settings.
- `anvil remote login <cluster>` — authenticate to a specific cluster via Cognito device authorization grant (RFC 8628), caching the JWT.
- `anvil remote logout <cluster>` — clear cached credentials for a cluster.
- `anvil remote push <cluster> corpus <path>` — upload a corpus to the specified cluster.
- `anvil remote push <cluster> dataset <path>` — upload a dataset.
- `anvil remote pull <cluster> model <id>` — download a model artifact from the cluster.
- `anvil remote pull <cluster> experiment <id>` — download experiment data.
- `anvil remote ls <cluster> <corpora|datasets|experiments>` — list resources on the cluster.
- If a single cluster is configured, the `<cluster>` argument SHOULD be optional and default to that cluster.

**FR-014a — Cluster registry**: The CLI MUST maintain a cluster registry at `~/.anvil/clusters.json` containing an array of cluster objects, each with: `name` (alias), `url` (CloudFront URL), `api_url` (API base path), `region` (AWS region the cluster is deployed in), `auth_method` ("deploy" or "device_grant"), `cognito_domain` (for device grant), `api_version` (the cluster's reported API version, see FR-014c), `deployed_at`, and `last_login`. The `anvil deploy init` command MUST automatically add the newly deployed cluster to the registry as a cluster entry named after the stack, with `auth_method: "deploy"`, the deployment `region`, and the admin credentials cached. Region-scoped credential resolution (e.g., per-region Cognito pools) MUST use the `region` field.

**FR-014b — Active cluster concept**: The CLI SHOULD support an active/default cluster concept. When a cluster is specified via `--cluster` flag or `ANVIL_ACTIVE_CLUSTER` env var, remote data commands omit the `<cluster>` argument. If zero clusters are configured, remote data commands MUST fail with a clear message directing the user to run `anvil remote cluster add` or `anvil deploy init`.

**FR-014c — API version negotiation**: Every SaaS deployment MUST expose its API version via an unauthenticated `GET /v1/version` endpoint returning `{api_version, anvil_version, min_cli_version}`. The CLI MUST call this on `cluster add` and before each remote operation, caching `api_version` in the registry. If the CLI's own version is below the cluster's `min_cli_version`, the CLI MUST refuse the operation with a clear "upgrade your anvil CLI" message rather than failing with an opaque API error. This prevents silent breakage when `anvil deploy update` rolls a newer API to a cluster while operators run older CLIs.

**FR-021 (device-grant aspect)** — CLI authentication MUST use Cognito's OAuth2 device authorization grant (RFC 8628) — the CLI opens a browser for the user to authenticate, then polls the token endpoint. No hardcoded API keys, no custom token endpoints. The device-grant flow requires the cluster's Cognito domain (stored in the registry entry) and the Cognito app client ID.

### Cluster Registry Schema

The cluster registry is a local-only file at `~/.anvil/clusters.json`, separate from the deploy config (`~/.anvil/deploy-config.json`). It stores no secrets — only JWT cache paths and OAuth configuration references. Actual credentials reside in `~/.anvil/credentials/` with `0600` permissions.

```json
{
  "active": "prod",
  "clusters": [
    {
      "name": "prod",
      "url": "https://models.example.com",
      "api_url": "https://models.example.com/v1",
      "region": "us-east-1",
      "auth_method": "device_grant",
      "cognito_domain": "auth.models.example.com",
      "cognito_client_id": "xxxxxxxxxxxxxxxxxx",
      "api_version": "1.0",
      "deployed_at": "2026-06-19T00:00:00Z",
      "last_login": "2026-06-20T12:00:00Z"
    },
    {
      "name": "staging-eu",
      "url": "https://staging.anvil.io",
      "api_url": "https://staging.anvil.io/v1",
      "region": "eu-west-1",
      "auth_method": "device_grant",
      "cognito_domain": "auth.staging.anvil.io",
      "cognito_client_id": "yyyyyyyyyyyyyyyyyy",
      "api_version": "1.0",
      "deployed_at": "2026-06-18T00:00:00Z",
      "last_login": null
    }
  ]
}
```

### `GET /v1/version` Response Contract

```
GET /v1/version
Content-Type: application/json

200 OK
{
  "api_version": "1.0",
  "anvil_version": "1.2.3",
  "min_cli_version": "1.1.0"
}
```

- **`api_version`**: Semantic version of the API protocol. Incremented on breaking changes.
- **`anvil_version`**: The anvil package version deployed on this cluster.
- **`min_cli_version`**: The minimum CLI version that can safely communicate with this cluster. CLI refuses operations if its version is below this.

### Credential Storage

Cached credentials live at `~/.anvil/credentials/` — one file per cluster, named after the cluster alias, with strict `0600` permissions:

```json
{
  "cluster": "prod",
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "expires_at": "2026-06-20T13:00:00Z",
  "id_token": "eyJ..."
}
```

The credentials directory and its contents MUST be created with `0o600` (owner read/write only) to prevent credential leakage on multi-user systems.

### Local-Mode Regression Gate

The `anvil remote` command group is gated on the `[aws]` extra. In a base (`pip install anvil`) install:

- `anvil remote` MUST fail with a clear "install anvil[aws]" message — never crash with `ImportError`.
- All existing local CLI verbs (`anvil serve`, `anvil train`, etc.) MUST be unaffected.
- `anvil serve` and the web UI MUST continue to work without any `[aws]` dependencies.

All of these MUST pass:

```bash
make test            # all pre-existing tests pass UNMODIFIED
make lint            # zero new lint errors
make typecheck       # mypy --strict clean; no SaaS imports leaking
pip install .        # clean install (no [aws])
anvil remote         # fails with actionable error
anvil serve          # boots; UI at :8080 works end-to-end
```

Plus the import-isolation assertion:

```bash
python - <<'PY'
import importlib, sys
import anvil.api.app
for forbidden in ("boto3", "redis", "aws_jwt_verify"):
    assert forbidden not in sys.modules, f"{forbidden} loaded by local entrypoint"
print("import isolation OK")
PY
```

## Edge Cases

- **No clusters configured**: `anvil remote ls` and other data commands fail with "No clusters configured. Run `anvil remote cluster add` or `anvil deploy init`."
- **CLI version too old**: Version negotiation refuses the operation: "anvil CLI v1.0.0 is below cluster minimum v1.1.0. Upgrade with `pip install --upgrade anvil`."
- **Token expired**: CLI detects expired JWT and re-runs device-grant flow transparently, prompting the user to re-authenticate in the browser.
- **Device grant timeout**: If the user does not complete the browser flow within the device-code expiry (typically 5–15 minutes), the CLI reports the timeout and instructs the user to retry.
- **Network error during push/pull**: The CLI retries with exponential backoff (handled by boto3/botocore). On exhaustion, a clear error with the S3 key and cluster name is emitted.
- **Cluster unreachable**: `anvil remote cluster add` and all data commands fail fast if the cluster URL is unreachable, with a clear "Cannot reach {url}" message.
- **Version endpoint unreachable**: If `GET /v1/version` fails, `cluster add` warns but proceeds (assumes compatibility). Remote data commands fail if version cannot be confirmed.
- **Corrupt registry file**: The CLI validates `~/.anvil/clusters.json` on load and falls back to an empty registry with a warning on parse failure.
- **Credential file permissions wrong**: The CLI warns if `~/.anvil/credentials/` has permissions less restrictive than `0700` or any file has permissions less restrictive than `0600`.
- **Single cluster auto-default**: If only one cluster exists in the registry, data commands default to it without requiring the `<cluster>` argument.

## Non-Goals

- **No anvil remote run**: In v1, the CLI cannot submit training jobs remotely. Training is initiated via the web UI only.
- **No anvil remote shell**: No interactive SSH-like session to a cluster.
- **No multi-region credential federation**: Credentials are per-cluster; the CLI does not federate tokens across clusters.
- **No batch/pipeline sync**: Push and pull are single-shot operations, not continuous sync. For that, use the web UI or API directly.

## Gate Criteria

| Gate | Description | Verification |
|------|-------------|--------------|
| G9a | Cluster registry CRUD | `cluster add/list/remove/configure` all work; `~/.anvil/clusters.json` reflects changes |
| G9b | Device-grant login | `login` opens browser, polls token, caches JWT at `~/.anvil/credentials/<cluster>` 0600 |
| G9c | Push/pull/ls | Push creates remote resource; pull downloads artifact; ls lists remote resources |
| G9d | Version negotiation | `GET /v1/version` returns expected shape; CLI refuses if `min_cli_version` > installed version |
| G9e | Active cluster | Single cluster auto-defaults; `ANVIL_ACTIVE_CLUSTER` overrides |
| G9f | Local-mode gate | Base install: `anvil remote` fails cleanly; `anvil serve` and local CLI verbs unaffected |

## Complexity Tracking

| Item | Justification |
|------|---------------|
| `[aws]`-extra gating | New `anvil remote` command group; same pattern as `anvil deploy`. Base install must fail cleanly without the extra. |
| Device-grant flow | OAuth2 RFC 8628 — opens browser, polls token endpoint, stores JWT. Shared auth surface with spec 030. |
| Cluster registry file management | Read/write `~/.anvil/clusters.json` with JSON validation. Separate from deploy config. |
| Version negotiation | `GET /v1/version` call on every remote operation; min-version cache in registry. Adds latency per operation but prevents silent breakage. |
