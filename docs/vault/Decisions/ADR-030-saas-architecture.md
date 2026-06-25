---
title: "ADR-030: SaaS Architecture — Three-Mode Operating Model"
type: decision
tags:
  - type/decision
  - domain/architecture
  - domain/infrastructure
created: 2026-06-19
updated: 2026-06-19
aliases:
  - "ADR-030: SaaS Architecture — Three-Mode Operating Model"
  - ADR-030
status: status/draft
source: agent
code-refs:
  - docs/vault/Specs/016 SaaS Architecture/spec.md
  - docs/vault/Reference/SaaSArchitecture.md
  - docs/vault/Reference/SaaSSystemDiagrams.md
---

# ADR-030: SaaS Architecture — Three-Mode Operating Model

## Status

Proposed

## Context

anvil was designed as a single-user local training tool. Growing demand for a hosted multi-tenant SaaS product requires a different architecture, but the local developer experience and pip-install workflow must remain untouched.

We considered several approaches:

- **Fork**: Separate codebase for SaaS. Rejected -- maintenance nightmare, feature divergence.
- **Monorepo with feature flags**: Same codebase, runtime flags. Rejected -- every route needs auth branching, hard to reason about.
- **Three-mode architecture**: Same codebase, three distinct operating modes selected at deploy time via `ANVIL_MODE`. SaaS-specific code in `anvil/_saas/` -- never imported in local mode.

The key architectural challenge is that local mode uses in-process infrastructure (SQLite, asyncio.Queue, filesystem, subprocess MLflow) while SaaS mode uses cloud services (RDS, Redis pub/sub, S3, ECS MLflow, AWS Batch). All business logic in `anvil/services/` must remain mode-agnostic.

## Decision

The architecture is split into three operating modes, all sharing the same `anvil` package.

### 1. Local User Mode (`ANVIL_MODE=local`)

Unchanged from the current architecture:
- SQLite database, in-process MLflow subprocess, local filesystem, in-process compute
- `pip install anvil` -> `anvil serve` -> `localhost:8080`
- Zero cloud dependencies, no SaaS code loaded

### 2. SaaS User Mode (`ANVIL_MODE=saas`)

Multi-tenant hosted product at `https://anvil.io`:
- RDS PostgreSQL (`anvil_app` + `anvil_mlflow`), dedicated MLflow ECS service
- S3 object store, Redis pub/sub for SSE, AWS Batch for compute
- **Authentication via Amazon Cognito** -- Google/GitHub social login plus email/password via Cognito Hosted UI. No custom auth code. No password hashing, no session management in the application.
- CloudFront + Route53 + WAF, auto-scaling ECS + Batch
- Infrastructure managed via CDK (`packages/infra/`)
- One-command deploy: `pip install anvil[aws] && anvil deploy init`

### 3. SaaS Developer Mode

Three sub-patterns for different iteration speeds:
- **docker compose up** -- full SaaS stack emulation locally (PostgreSQL, Redis, MinIO, MLflow, anvil-web with hot-reload)
- **local code to dev AWS** -- run local code against shared dev RDS/Redis/S3 (compute runs locally for debugging)
- **cdk deploy** -- deploy branch to full dev AWS environment

### Abstraction Layer

Six interfaces enable mode-agnostic business logic:

| Interface | Local Implementation | SaaS Implementation |
|-----------|---------------------|---------------------|
| `FileStore` | `LocalFileStore` (filesystem) | `S3FileStore` (boto3) |
| `EventBus` | `InProcessEventBus` (asyncio.Queue) | `RedisEventBus` (redis.asyncio pub/sub) |
| `JobQueue` | `InProcessJobQueue` (immediate create_task) | `BatchJobQueue` (boto3 batch.submit_job) |
| `ComputeBackend` | `LocalStdlibBackend` / `LocalTorchBackend` | `BatchComputeBackend` (wraps JobQueue) |
| `LogsReader` | `LocalLogsReader` (disk files) | `CloudWatchLogsReader` (boto3 logs) |
| `VersionedContentStore` | `LocalVersionedContentStore` (pure-Python, content-addressed) | `LakeFSVersionedContentStore` (LakeFS over S3) |

SaaS code lives in `anvil/_saas/` and is **never imported in local mode** -- no `boto3`, `redis-py`, or Cognito SDKs added to the base pip package. They are optional extras via `pip install anvil[aws]`.

## Consequences

### Positive

- **Single codebase** -- no fork, no feature flag branching. Three modes, same services layer.
- **Local mode unchanged** -- `pip install anvil` stays lean. Existing users unaffected.
- **Developer velocity** -- three iteration speeds (docker, local to dev, cdk). Fast for UI/API changes, full infra for E2E testing.
- **Clear boundaries** -- SaaS code is physically separated in `anvil/_saas/`. Importing it in local mode would be a bug.
- **Existing compute backends preserved** -- `local-stdlib`, `local-torch`, `modal` still work in local mode.
- **Zero auth code** -- Cognito handles registration, login, password reset, MFA, session management, and social identity federation. No password hashing, no token storage, no session tables in the application.
- **Deployability** -- `anvil deploy init` deploys the entire stack including Cognito into any AWS account with one command.

### Negative

- **Repository pattern refactor** -- every repository method needs an `org_id` scope (full RBAC: org/team/role, AD-8) for SaaS. Local mode uses a single default org. Touches ~20+ methods.
- **New dependency for SaaS deployment** -- `boto3`, `redis-py`, `aws-jwt-verify` are SaaS-only extras, not in the base package.
- **MLflow URL construction** -- `get_mlflow_browser_uri(request)` currently uses `request.host`. SaaS mode needs CloudFront-aware URL construction. **Resolved by AD-13**: an authenticated reverse proxy at `/v1/mlflow-proxy/` plus a CloudFront-aware URI builder; MLflow stays private.
- **Docker compose complexity** -- developers manage 5+ containers locally (PostgreSQL, Redis, MinIO, MLflow, anvil-web). Cognito emulation needs a local mock or dev pool.
- **SSE auth** -- EventSource cannot set custom headers; the SSE endpoint reads a short-lived signed token via query parameter (AD-2/FR-020). The ALB does NOT perform `authenticate-cognito` (app-managed OIDC).
- **CLI auth complexity** -- CLI uses Cognito OAuth2 device grant flow (browser popup) rather than API keys. More steps, more secure.

### Risks

- **SQLite to PostgreSQL dialect differences** -- async SQLAlchemy abstracts most, but edge cases exist (JSON operators, RETURNING syntax). Mitigation: run tests against both.
- **SSE reconnection on pod rotation** -- resolved by AD-5: serving replica subscribes per-connection; `Last-Event-ID` replay from `job_events` (plus polling fallback, FR-045a/b) closes gaps.
- **Batch job state consistency** -- resolved by AD-4: PostgreSQL is the source of truth via append-only `job_events`; a reconciler repairs stuck jobs. Redis is delivery-only.
- **CloudFront cache invalidation** -- static assets served through CloudFront need invalidation on deploy. Mitigation: versioned asset filenames or deploy-time invalidation.

## Architecture Decisions (Canonical: AD-1 .. AD-17)

The detailed, binding decisions resolving the pre-implementation review live in `docs/vault/Specs/016 SaaS Architecture/spec.md` and supersede any summary here:

| AD | Decision |
|----|----------|
| AD-1 | Compute on AWS Batch on EC2 (CPU / GPU / multi-GPU / multi-node); Fargate has no GPU |
| AD-2 | Auth = app-managed Cognito OIDC/JWT (not ALB-managed) |
| AD-3 | Native Cognito users default; social login BYO post-deploy |
| AD-4 | Postgres source of truth + append-only `job_events` + reconciler |
| AD-5 | SSE per-connection subscribe + `Last-Event-ID` replay |
| AD-6 | Migrations as a single pre-deploy step |
| AD-7 | Asset-free CloudFormation with digest-pinned images |
| AD-8 | Full RBAC: Cluster admin (read-wide/write-narrow) + Organization -> Team -> Role -> User |
| AD-9 | Usage metering for billback derived from `job_events` |
| AD-10 | Single container image, two entrypoints (web + compute worker) |
| AD-11 | Three-plane orchestration; AWS Batch owns scheduling; fair-share + quotas + checkpointed retries |
| AD-12 | Observability: in-app CloudWatch Logs viewer, OpenTelemetry->X-Ray tracing, Prometheus `/metrics` + Grafana + Alertmanager; all SaaS-only optional extras (FR-052-FR-056) |
| AD-13 | MLflow stays private; browser access via an authenticated `/v1/mlflow-proxy/` reverse proxy with `--static-prefix` (FR-057) |
| AD-14 | Two-tier admin: `is_cluster_admin` flag is read-wide, write-narrow -- cross-org read + fixed cluster-op action matrix, but tenant-data writes still gated by org role (FR-034-FR-038b). Local mode is implicit admin, no auth |
| AD-15 | Multi-cluster CLI: `~/.anvil/clusters.json` registry (with `region`, `api_version`), `anvil remote cluster *` commands, `GET /v1/version` negotiation (FR-014a/c) |
| AD-16 | Production posture: single-region multi-AZ HA (RDS Multi-AZ + PITR, Redis Multi-AZ failover, S3 versioning), backup/DR with destroy-time final snapshot + `deploy restore`, secret-rotation dual-key window, reconciler operating parameters, `job_events` retention (FR-043a, FR-044a, FR-045q-s, FR-058-061) |
| AD-17 | Content repository substrate: `VersionedContentStore` interface; local = pure-Python content-addressed (no dep); SaaS = LakeFS over org-scoped S3; validation/isolation/acceptance stay in-process (NOT LakeFS hooks); per-branch RBAC is enterprise-only so producer + management authz are enforced app-side (org/team/role + mgmt-authz seam); content-addressed manifest digest is the externally-pinned reproducibility ref in both modes (FR-016, FR-062-067; spec 016) |

**Key clarification (AD-14)**: the cluster-admin elevation is NOT a blanket bypass. It widens the read scoping predicate (cross-org visibility) and grants a fixed cluster-operation matrix (suspend orgs, cancel jobs, manage cluster admins, view health/logs), but destructive tenant-data mutation in a foreign org still requires an explicit org role there. This resolved a blocking authority conflict in the spec review (FR-037 vs FR-038a).

See also: [[SaaSArchitecture]], [[SaaSSystemDiagrams]], [[SaaSSecurityAndFlowDiagrams]], [[2026-06-19-saas-spec-hardening|SaaS Spec Hardening Session]].

## Compliance

- `ANVIL_MODE` env var controls which `app.py` factory is loaded. Mode is never auto-detected -- always explicit.
- SaaS-only imports (`boto3`, `redis`) must only appear in `anvil/_saas/`. Enforced via lint rule (e.g. `ruff` per-file-ignore exclusion).
- All `anvil/services/` code must be importable in local mode without SaaS dependencies.
- `anvil/core/` remains zero-dependency and is shared with compute pods unchanged.
- The `packages/infra/` CDK stack must synth cleanly and pass `cdk diff` before any SaaS infrastructure change.

## See Also
- [[Decisions/README|Decisions]]

- Full architecture reference: `docs/vault/Reference/SaaSArchitecture.md`