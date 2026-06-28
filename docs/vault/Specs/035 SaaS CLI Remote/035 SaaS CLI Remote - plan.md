---
title: 035 SaaS CLI Remote - plan
type: plan
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

# Implementation Plan: SaaS CLI Remote & Cluster Management

**Branch**: `035-saas-cli-remote` | **Date**: 2026-06-27 | **Spec**: docs/vault/Specs/035 SaaS CLI Remote/035 SaaS CLI Remote - spec.md
**Input**: Feature specification from superseded `docs/vault/Specs/016 SaaS Architecture/016 SaaS Architecture - spec.md` (FR-014 family, US9), plan.md (Phase 11), tasks.md (T094–T099), shippable-features.md (Feature 8).

---

## Summary

Add a new `anvil remote` CLI command group that lets local anvil users connect to one or more SaaS deployments, authenticate via Cognito device authorization grant, manage a local cluster registry at `~/.anvil/clusters.json`, and sync data (corpora, datasets, models, experiments) via signed S3 URLs. API-version negotiation via `GET /v1/version` prevents the CLI from silently failing against newer clusters.

The feature splits into four sub-components: (A) cluster registry CRUD, (B) device-grant authentication, (C) data sync (push/pull/ls), and (D) version negotiation. All are gated on the `[aws]` extra (boto3, redis, aws-jwt-verify).

---

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: `boto3` (S3 signed URLs), `aws-jwt-verify` (Cognito JWT validation for CLI), `httpx` (HTTP client for API calls) — all existing `[aws]` extras
**Storage**: `~/.anvil/clusters.json` (cluster registry), `~/.anvil/credentials/` (per-cluster JWT cache, 0600)
**Target Mode**: Local CLI connecting to remote SaaS clusters; no SaaS-side code changes beyond `GET /v1/version` endpoint
**Constraints**: `[aws]`-extra gated; local mode unchanged; credentials stored with strict 0600 permissions; no changes to `anvil serve` or existing CLI verbs

---

## Constitution Check

### Article I — Zero-Dependency Core
- `anvil/core/` is untouched. ✓

### Article II — TDD Mandatory
- Unit tests for cluster registry read/write, version parsing, credential storage permissions
- E2E tests (HTTP client against dev cluster) for push/pull/ls and device-grant flow

### Article X — Domain-Driven Package Decomposition
- CLI remote code lives in a new `anvil/cli/remote/` package or alongside existing CLI entry points. ✓

### Additional Constraints
- **Enum over magic strings**: `AuthMethod("deploy" | "device_grant")`, `RemoteResourceType("corpora" | "datasets" | "experiments")` as StrEnum
- **Pydantic BaseModel**: Cluster registry entries, credential payloads, version response DTO
- **One class per file**: ClusterRegistry, DeviceGrantAuth, RemoteSync each get their own file
- **No type-error suppression**: `mypy --strict` applies

---

## Project Structure

### Documentation (this feature)

```text
docs/vault/Specs/035 SaaS CLI Remote/
├── 035 SaaS CLI Remote.md           # Index note
├── 035 SaaS CLI Remote - spec.md    # This file
├── 035 SaaS CLI Remote - plan.md    # This file
├── 035 SaaS CLI Remote - tasks.md   # Tasks
├── 035 SaaS CLI Remote - research.md
├── 035 SaaS CLI Remote - data-model.md
├── 035 SaaS CLI Remote - quickstart.md
└── contracts/
    ├── cluster-registry-schema.md
    └── version-response.md
```

### Source Code (repository root)

```text
# New CLI command group — gated on [aws] extra
anvil/cli/
├── __init__.py
├── remote.py                  # `anvil remote` Typer/Click command group
├── cluster_commands.py        # `cluster add/list/remove/configure` subcommands
├── auth_commands.py           # `login/logout` subcommands
├── sync_commands.py           # `push/pull/ls` subcommands
└── remote/
    ├── __init__.py
    ├── cluster_registry.py    # ClusterRegistry — read/write ~/.anvil/clusters.json
    ├── device_grant.py        # DeviceGrantAuth — OAuth2 RFC 8628 client
    ├── credential_store.py    # CredentialStore — read/write ~/.anvil/credentials/<cluster>
    ├── version_negotiation.py # VersionNegotiator — GET /v1/version + min-version check
    └── sync.py                # RemoteSync — push/pull/ls via signed S3 URLs

# API endpoint (SaaS-side, new)
anvil/api/v1/version.py        # GET /v1/version endpoint (unauthenticated, returns api_version, anvil_version, min_cli_version)
```

---

## Phasing

### Phase A — Cluster Registry (T094a, T094b)
ClusterRegistry class, CredentialStore class, anvil remote cluster commands, `~/.anvil/clusters.json` schema, `~/.anvil/credentials/` layout with 0600 enforcement.

### Phase B — Device-Grant Authentication (T094c, T095)
DeviceGrantAuth (RFC 8628 browser-open + poll + JWT cache), anvil remote login/logout, credential refresh on expiry.

### Phase C — Data Sync (T096–T099)
RemoteSync for push/pull/ls using signed S3 URLs, integration with existing API routes for corpus/dataset/model CRUD. Each resource type (corpora, datasets, experiments) gets parallel implementation.

### Phase D — Version Negotiation (T094d)
GET /v1/version endpoint on the SaaS API, VersionNegotiator in the CLI, min-version check before every remote operation, api_version caching in the registry.

---

## Complexity Tracking

| Item | Justification |
|------|---------------|
| `[aws]`-extra gating | Same pattern as `anvil deploy`. Base install must fail cleanly. |
| Device-grant flow | OAuth2 RFC 8628 with browser-dance. Shared auth surface with spec 030. |
| Cluster registry + credential store | Two separate files with different permission models. JSON schema validation on load. |
| Version negotiation | Adds latency per remote operation (one HTTP call) but prevents silent breakage. |

---

## Dependency Changes

No new dependencies. All HTTP client work uses `httpx` (existing); signed S3 URLs use `boto3` (existing `[aws]` extra); JWT validation uses `aws-jwt-verify` (existing `[aws]` extra).
