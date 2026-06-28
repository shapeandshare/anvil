---
title: SaaS Architecture Decisions (AD-1..AD-17)
type: reference
tags:
  - type/reference
  - domain/architecture
  - domain/infrastructure
created: '2026-06-27'
updated: '2026-06-27'
aliases:
  - SaaS Architecture Decisions
  - AD-1..AD-17
status: draft
---
# SaaS Architecture Decisions (AD-1..AD-17)

The canonical, binding architecture decisions for anvil's SaaS body of work. These resolve the
pre-implementation architecture review (Oracle pass on [[Decisions/ADR-030-saas-architecture|ADR-030]])
and are **shared substrate** referenced by the per-feature SaaS specs (028–037).

> **Provenance**: These decisions were originally authored inside the umbrella spec
> `016 SaaS Architecture - spec.md`. That spec is now **superseded** and split into per-feature specs
> 028–037 (see [[Specs/016 SaaS Architecture/016 SaaS Architecture|016]]). This note is the durable
> home for the decisions so every child spec links to one authoritative source.

## Decision Index

| AD | Decision | Primary spec(s) |
|----|----------|-----------------|
| AD-1 | Compute on AWS Batch on EC2 (CPU / GPU / multi-GPU / multi-node); Fargate has no GPU | 032, 033 |
| AD-2 | Auth = app-managed Cognito OIDC/JWT (not ALB-managed) | 030 |
| AD-3 | Native Cognito users default; social login BYO post-deploy | 030, 034 |
| AD-4 | Postgres source of truth + append-only `job_events` + reconciler | 032 |
| AD-5 | SSE per-connection subscribe + `Last-Event-ID` replay | 032 |
| AD-6 | Migrations as a single pre-deploy step | 033, 034 |
| AD-7 | Asset-free CloudFormation with digest-pinned images | 033, 034 |
| AD-8 | Full RBAC: Cluster admin (read-wide/write-narrow) + Organization → Team → Role → User | 031 |
| AD-9 | Usage metering for billback derived from `job_events` | 032 |
| AD-10 | Single container image, two entrypoints (web + compute worker) | 028, 033 |
| AD-11 | Three-plane orchestration; AWS Batch owns scheduling; fair-share + quotas + checkpointed retries | 032 |
| AD-12 | Observability: CloudWatch Logs viewer, OTel→X-Ray, Prometheus/Grafana/Alertmanager — SaaS-only extras | 036 |
| AD-13 | MLflow stays private; browser access via authenticated `/v1/mlflow-proxy/` reverse proxy | 036 |
| AD-14 | Two-tier admin: `is_cluster_admin` read-wide / write-narrow | 031 |
| AD-15 | Multi-cluster CLI: `~/.anvil/clusters.json` registry + `GET /v1/version` negotiation | 035 |
| AD-16 | Production posture: single-region multi-AZ HA + backup/DR + secret rotation | 037 |
| AD-17 | Content repository: pure-Python local, LakeFS for SaaS, app-level RBAC | (see spec 019) |

---

## AD-1: Compute Substrate — AWS Batch on EC2 (CPU + GPU + Multi-Node)

**Decision**: AWS Batch with EC2 compute environments. Supports CPU jobs (Fargate or EC2),
single-GPU and multi-GPU-per-node (g4dn/g5/p4 instances), and multi-node distributed training via
Batch **multi-node parallel jobs**. Boring, managed, reliable — no Kubernetes.

**Rationale**: Fargate has NO GPU support (review CRITICAL finding). EKS+Kubeflow is not "boring."
SageMaker is opinionated and pricey. AWS Batch on EC2 natively supports gang-scheduled multi-node
parallel jobs, GPU instance types, and Spot. Simplest substrate covering all four compute shapes.

**Compute shapes the JobQueue/ComputeBackend MUST express**: `cpu`, `gpu`, `multi-gpu`, `multi-node`
(M nodes × N GPUs, Batch multi-node parallel job, gang-scheduled).

**Gotchas**: placement groups for multi-node locality, EFA networking for inter-node bandwidth
(p4/p5), gang scheduling (Batch `numNodes`), Spot interruption handling for long jobs.

## AD-2: Authentication — App-Managed OIDC/JWT

**Decision**: FastAPI validates Cognito JWTs directly via `aws-jwt-verify`. ALB does NOT do
`authenticate-cognito`. (See FR-019.)

**Rationale**: Review CRITICAL finding — ALB-managed and app-managed auth are different patterns and
must not be mixed. App-managed works identically across CloudFront, ALB, direct API, and CLI, and is
the only pattern compatible with bearer-token CLI access.

## AD-3: Social Login — Native Default, BYO Social

**Decision**: Email/password Cognito users work out of the box. Social login is post-deploy,
optional, BYO OAuth credentials. (See FR-021a.)

**Rationale**: Review HIGH finding — per-customer Cognito pools need per-customer OAuth apps with
callback URLs not known until after deploy. Making social login post-deploy preserves the true
one-command install.

## AD-4: Job State Consistency — Postgres Source of Truth + Append-Only Events

**Decision**: PostgreSQL is the single source of truth for job lifecycle. An append-only
`job_events` table records idempotent events keyed by `(job_id, sequence)`. Redis is
**delivery-only** (transient SSE fan-out), never the source of truth. A reconciler compares Batch
job state, DB state, MLflow run state, and expected S3 artifacts to repair stuck/terminal jobs.

**Rationale**: Review CRITICAL finding — a compute pod writing to Postgres + S3 + MLflow + Redis with
no transaction boundary creates split-brain state on crash. Deterministic S3 keys + idempotent event
keys + a reconciler make the system self-healing.

## AD-5: SSE — Serving Replica Subscribes Per-Connection + Replay

**Decision**: A browser's `EventSource` connection pins to one ECS replica (long-lived HTTP). That
replica subscribes to the Redis channel for that specific job. SSE supports `Last-Event-ID` replay
backed by the `job_events` table so a reconnect to a different replica resumes without gaps.
CloudFront/ALB idle timeouts are tuned and a 30s heartbeat keeps connections alive.

**Rationale**: Review HIGH finding — raw Redis pub/sub drops events when no subscriber is attached
(reconnect/replica restart). DB-backed replay makes streaming correct, not just live.

## AD-6: Migrations — Single Pre-Deploy Step

**Decision**: Alembic migrations run as a single one-off ECS task (or CFN custom resource) BEFORE the
web service rolls out. The web service does only a schema-compatibility check on startup and fails
fast on mismatch. Applies to both `anvil_app` and `anvil_mlflow` schemas.

**Rationale**: Review HIGH finding — running Alembic on startup with 2+ replicas is a race.
Pre-deploy migration with rollout gating eliminates it.

## AD-7: Deploy Asset Model — Immutable Image Digests, No CDK Asset References

**Decision**: Pre-synthesized CloudFormation templates MUST be asset-free. Container images are
referenced by **immutable digest** (`@sha256:...`) from a public registry (GHCR or public ECR).
Lambda code (post-auth trigger, reconciler) is inlined or referenced from a versioned S3 object the
deploy CLI publishes into the customer account before stack creation. No dependency on
`cdk bootstrap` / CDKToolkit stack in the customer account.

**Rationale**: Review HIGH finding — standard CDK synth output assumes bootstrap state and asset
buckets. Asset-free templates + digest-pinned images make the boto3 deploy truly portable.

## AD-8: Multi-Tenancy — Full RBAC (Cluster Admin + Organization → Team → User → Role)

**Decision**: Two-tier admin model from v1. `is_cluster_admin` is a boolean flag on the `users` table
providing **read-wide, write-narrow** system access: it bypasses `org_id` scoping for READ/LIST
operations and grants a fixed cluster-operation action matrix (FR-037b), but does NOT bypass the
org-role guard for tenant-data WRITES. Below that, `Organization` is the top-level billing/isolation
boundary. `Team` groups users within an org. `Role` (owner/admin/member/viewer) governs permissions
within an org. All resources are owned by `org_id` (+ optional `team_id` + `created_by`).
Authorization is a middleware + service-layer guard; the cluster-admin elevation changes the
read-scoping predicate and adds cluster-operation permissions — it is NOT a blanket "skip all checks"
bypass.

**Rationale**: User requirement — full RBAC. Review HIGH finding — retrofitting `tenant_id` after
launch is painful, so it is first-class now. The read-wide/write-narrow split (FR-037a/b) prevents
the operational-visibility need from becoming an accidental "god mode."

## AD-9: Usage Metering for Billback

**Decision**: Per-user AND per-org usage is captured from job lifecycle events. When a job completes,
its runtime × instance type (GPU-seconds, instance-hours) is recorded in a `usage_records` table
attributed to `org_id`, `team_id`, `user_id`, and `job_id`. Records derive from the authoritative
`job_events` (AD-4), not a separate write path. Cost Allocation Tags on Batch jobs provide a
cross-check against AWS Cost Explorer.

**Rationale**: User requirement — billback per user and organization. Deriving from `job_events`
keeps a single source of truth.

## AD-10: Container Strategy — Single Image, Two Entrypoints

**Decision**: One container image serves both the web tier and the compute worker, selected by
entrypoint/`CMD` (`anvil._saas.app:app` for web, `anvil/_saas/compute_worker.py` for Batch). Built
once, pushed once, referenced by a single digest. A multi-stage build keeps it lean. NOT split into
separate `anvil-web` / `anvil-compute` images for v1.

**Rationale**: Version consistency is a correctness property (shared `job_events` schema, S3 layout,
MLflow conventions); matches digest-pinned turnkey deploy (AD-7); cold-start cost amortized over
minutes-to-hours jobs; simplest CI/CD. **Reversal trigger**: split into a minimal `anvil-compute`
image only if Batch cold-start dominates short jobs OR compliance requires minimizing the compute
attack surface. `compute_worker.py` already isolates the entrypoint, so the split is mechanical later.

## AD-11: Training Orchestration — Three-Plane Model, Batch-Owned Scheduling

**Decision**: Training jobs use a three-plane model (control plane = anvil-web, scheduler = AWS
Batch, executor = compute pod). **AWS Batch is the orchestrator** — it owns queueing,
compute-environment scaling, gang-scheduling, and retries. anvil-web admits/configures/submits/
observes; it does not build a custom scheduler. Orchestration policy: app-level per-org quotas +
Batch fair-share scheduling (keyed on `org_id`); infra-only auto-retry with checkpoint resume;
periodic S3 checkpointing for long/multi-node jobs; pre-registered per-shape job definitions
parameterized by `ResourceSpec`. (FR-045g–FR-045p)

**Rationale**: "Simple and boring orchestration" mandate — Batch already solves queueing/scaling/
gang-scheduling/Spot retries reliably. Fair-share prevents tenant starvation; app-level quotas give
hard per-org caps; infra-only retry avoids burning compute on doomed user-error jobs; checkpointing
makes Spot viable. The three-plane separation enforces AD-4 — planes never mutate each other directly.

## AD-12: Observability — SaaS-Only Optional Extras

**Decision**: Three pillars, all SaaS-only optional extras, local mode degrades gracefully: (1) Logs —
CloudWatch Logs API surfaced in-app via a `LogsReader` abstraction (`LocalLogsReader` /
`CloudWatchLogsReader`); per-job compute pod logs via a `batch_log_stream` column. (2) Traces —
OpenTelemetry auto-instrumentation → AWS X-Ray; `traceparent` propagated into Batch pods and across
the Redis SSE boundary. (3) Metrics — Prometheus `/metrics` + custom metrics; Prometheus + Grafana +
Alertmanager on ECS Fargate; compute pods emit CloudWatch EMF. (FR-052–FR-056)

**Rationale**: Production operability without burdening local mode. `[monitoring]`/`[monitoring-aws]`
extras keep the base package and `[aws]` extra free of OTel/Prometheus deps (SC-019).

## AD-13: MLflow Stays Private — Authenticated Reverse Proxy

**Decision**: Browser access to the private MLflow service is exclusively through an authenticated
`/v1/mlflow-proxy/{path:path}` route on anvil-web. MLflow stays in a private subnet with no ALB/
CloudFront/internet route. The bundled MLflow runs with `--static-prefix=/v1/mlflow-proxy` so its SPA
emits proxy-correct URLs. (FR-057). Per [[Decisions/ADR-035-mlflow-reverse-proxy|ADR-035]] this
pattern is unified across local and SaaS modes (local upstream is loopback).

**Rationale**: Avoids exposing MLflow to the internet while keeping experiment tracking usable; the
proxy enforces the same Cognito JWT + RBAC as all `/v1/*` endpoints.

## AD-14: Two-Tier Admin — Read-Wide, Write-Narrow

**Decision**: The `is_cluster_admin` flag is read-wide, write-narrow — cross-org read + a fixed
cluster-operation action matrix, but tenant-data writes still gated by org role (FR-034–FR-038b).
Local mode is implicit admin, no auth.

**Key clarification**: the cluster-admin elevation is NOT a blanket bypass. It widens the read scoping
predicate (cross-org visibility) and grants a fixed cluster-operation matrix (suspend orgs, cancel
jobs, manage cluster admins, view health/logs), but destructive tenant-data mutation in a foreign org
still requires an explicit org role there. This resolved a blocking authority conflict in the spec
review (FR-037 vs FR-038a).

## AD-15: Multi-Cluster CLI

**Decision**: The CLI maintains a cluster registry at `~/.anvil/clusters.json` (with `region`,
`api_version`), `anvil remote cluster *` commands, and `GET /v1/version` API-version negotiation
(FR-014a/c). `deploy init` auto-adds a cluster entry, `deploy destroy` removes it. CLI-only concern.

**Rationale**: A single machine may manage multiple regional clusters; version negotiation prevents
silent breakage when `deploy update` rolls a newer API while operators run older CLIs.

## AD-16: Production Posture — Single-Region Multi-AZ HA + Backup/DR

**Decision**: Single-region multi-AZ HA (RDS Multi-AZ + PITR, Redis Multi-AZ failover, S3
versioning), backup/DR with destroy-time final snapshot + `deploy restore`, secret-rotation dual-key
window, reconciler operating parameters, `job_events` retention (FR-043a, FR-044a, FR-045q–s,
FR-058–061). No cross-region failover in v1.

**Rationale**: Production trust is non-negotiable, but cross-region is over-engineering for v1.
All HA settings are default-on CDK constructs.

## AD-17: Content Repository Substrate — LakeFS (SaaS) behind a shared `VersionedContentStore`

**Decision**: The versioned content repository is fronted by a `VersionedContentStore` interface.
**Local mode** uses a pure-Python, content-addressed implementation (no external service, no new
dependency). **SaaS mode** uses a **LakeFS-backed** implementation over the org-scoped S3 bucket,
presented as a managed component. **Validation, isolation, and serialized acceptance remain
app-level/in-process** (NOT LakeFS hooks). **Producer/data-plane scoping and management-action
authorization are enforced in the application layer** (org/team/role RBAC + management-authz seam),
because fine-grained per-branch RBAC is enterprise-only in LakeFS OSS. The content-addressed
**manifest digest** is the externally-pinned reproducibility ref in both modes. (FR-016, FR-062–FR-067)

**Rationale**: LakeFS is a non-pip Go binary with enterprise-only RBAC (unsuitable as a transparent
local sidecar, insufficient for tenant isolation alone); LakeFS `pre-*` hooks lock the branch and
deadlock when calling back into the same app; a content-addressed manifest digest gives
reproducibility-by-reference without coupling to LakeFS commit semantics. One interface lets local
stay zero-dependency while SaaS gains LakeFS's storage/versioning. See spec 019.

## See Also

- [[Decisions/ADR-030-saas-architecture|ADR-030]] — the originating ADR
- [[Decisions/ADR-035-mlflow-reverse-proxy|ADR-035]] — MLflow proxy unification
- [[Reference/SaaSArchitecture|SaaSArchitecture]] — long-form architecture reference
- [[Reference/SaaSSystemDiagrams|SaaSSystemDiagrams]] — 38 system diagrams
- [[Reference/SaaSSecurityAndFlowDiagrams|SaaSSecurityAndFlowDiagrams]] — 39 security/flow diagrams
- [[Specs/016 SaaS Architecture/016 SaaS Architecture|016 SaaS Architecture]] — superseded umbrella spec
