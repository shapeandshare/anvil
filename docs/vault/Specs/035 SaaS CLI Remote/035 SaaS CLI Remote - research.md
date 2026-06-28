---
title: 035 SaaS CLI Remote - research
type: research
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

# Research: SaaS CLI Remote & Cluster Management

## OAuth2 Device Authorization Grant (RFC 8628)

The CLI authentication uses Cognito's implementation of RFC 8628. The flow:

1. CLI POSTs to Cognito's `device_authorization` endpoint (`https://<cognito-domain>/oauth2/device_authorization`) with `client_id`
2. Cognito returns `device_code`, `user_code`, `verification_uri`, `interval`
3. CLI displays the verification URI and user code; opens the browser
4. User authenticates in the browser; CLI polls the token endpoint at the specified interval
5. On success, CLI receives `access_token`, `refresh_token`, `id_token`, `expires_in`

**References**:
- [RFC 8628 — OAuth 2.0 Device Authorization Grant](https://datatracker.ietf.org/doc/html/rfc8628)
- [Cognito Device Authorization Grant documentation](https://docs.aws.amazon.com/cognito/latest/developerguide/amazon-cognito-user-pools-device-authorization-grant.html)

### Key Considerations

- Cognito device grant requires the app client to have the `device_authorization_grant` OAuth scope enabled
- The `device_authorization` endpoint does NOT require client secret (public client)
- Device code expires after a configurable timeout (default 5–15 minutes); the CLI must handle this and retry
- `interval` from the response controls polling cadence (default 5 seconds)
- The token response includes both `access_token` (JWT, short-lived) and `refresh_token` (long-lived)

## Signed S3 URL Pattern

Push/pull operations use presigned S3 URLs. The pattern mirrors the web UI upload/download flow:

1. CLI authenticates and requests a presigned URL from the cluster API (`POST /v1/corpora/upload` etc.)
2. Cluster API validates auth, generates a presigned S3 PUT URL
3. CLI uploads/downloads directly to/from S3 using the presigned URL
4. CLI notifies the API when the transfer is complete

This avoids proxying large files through the web service. The presigned URLs have a short TTL (default 5 minutes) and are scoped to a single object.

## Credential Storage Security

Credentials are stored at `~/.anvil/credentials/<cluster_name>` with strict `0o600` permissions (owner read/write only). The `~/.anvil/credentials/` directory itself gets `0o700` (owner only). This prevents credential leakage on multi-user systems.

The credential file contains:
```json
{
  "cluster": "prod",
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "id_token": "eyJ...",
  "expires_at": "2026-06-20T13:00:00Z"
}
```

## Cluster Registry Structure

Separate from the deploy config (`~/.anvil/deploy-config.json`). A single machine may manage multiple clusters in different regions. The registry stores no secrets — only JWT cache paths and OAuth configuration references. See `contracts/cluster-registry-schema.md` for the canonical schema and `data-model.md` for the Pydantic model specification.

## Version Negotiation

`GET /v1/version` is the single unauthenticated endpoint on the SaaS API. It enables the CLI to detect incompatible API versions before making any mutating calls. The `min_cli_version` field allows the cluster to express "I speak protocol v1.0 but you need CLI ≥ 1.1.0 to use it" — this covers scenarios where the CLI package needs a security patch or critical fix even if the wire protocol hasn't changed.

## Prior Art in the Codebase

- `anvil deploy` commands in `anvil/deploy/command.py` — pattern for CLI command groups with `[aws]`-extra gating
- `anvil/api/v1/` route registration — pattern for adding new API endpoints
- Existing signed URL patterns in the training and corpus API routes
