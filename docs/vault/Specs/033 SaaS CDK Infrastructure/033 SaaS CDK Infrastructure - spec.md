---
title: 033 SaaS CDK Infrastructure - spec
type: spec
tags:
  - type/spec
spec-refs:
  - docs/vault/Specs/033 SaaS CDK Infrastructure/
related:
  - '[[033 SaaS CDK Infrastructure]]'
created: '2026-06-27'
updated: '2026-06-27'
status: draft
---

# Feature Specification: SaaS CDK Infrastructure

**Feature Branch**: `033-saas-cdk-infrastructure`
**Created**: 2026-06-27
**Status**: Draft
**Parent Spec**: [[Specs/016 SaaS Architecture/016 SaaS Architecture|016 SaaS Architecture (superseded umbrella)]]

## Overview

This feature delivers the full AWS CDK TypeScript stack under `packages/infra/` that provisions all SaaS infrastructure as code. It is the infrastructure component of the umbrella spec's US6 (SaaS Developer Deploys Branch to Dev AWS). The stack is the single source of truth for SaaS infrastructure; manual console changes will be overwritten.

**Key architectural decisions**:
- **Compute**: AWS Batch on EC2 with four compute shapes — CPU, GPU, multi-GPU, multi-node (AD-1)
- **Migrations**: Single pre-deploy ECS task gating web rollout (AD-6)
- **Deploy model**: Asset-free CloudFormation templates with digest-pinned container images (AD-7)
- **Container**: Single image, two entrypoints — web vs compute worker (AD-10)

## User Story

### User Story 6 — SaaS Developer Deploys Branch to Dev AWS (Priority: P2)

A developer wants to test their changes against real AWS infrastructure. They run `cdk deploy` from `packages/infra/`, which builds the Docker image, pushes it to ECR, and updates the dev ECS service.

**Acceptance Scenarios**:

1. **Given** a developer has made changes, **When** they run `cdk deploy`, **Then** the Docker image is built, tagged with the git commit hash, pushed to ECR, and the ECS service is updated.
2. **Given** a dev stack is deployed, **When** a user visits the dev CloudFront URL, **Then** they see the updated version of the application.
3. **Given** a dev stack with infrastructure changes, **When** `cdk diff` is run, **Then** it shows the planned changes before deployment.

## Requirements

### Owned Functional Requirements

- **FR-008**: System MUST serve the web UI and API from the same origin in SaaS mode (no CORS needed).
- **FR-009**: System MUST support CloudFront CDN with cached static assets and proxied API requests.
- **FR-010**: System MUST deploy infrastructure via AWS CDK (`packages/infra/`) for SaaS mode.
- **FR-022**: The anvil application's Cognito User Pool MUST be deployed via the CDK stack as a first-class resource — no separate Cognito setup outside of `anvil deploy`.
- **FR-029**: CloudFormation templates MUST be pre-synthesized from the CDK source during CI and bundled directly in the pip package so the Python CLI can deploy them via `boto3`.
- **FR-032**: The deploy system MUST support multiple independent environments (dev, staging, prod) in the same AWS account using different stack names.
- **FR-051**: Alembic migrations for both `anvil_app` and `anvil_mlflow` MUST run as a single pre-deploy step (one-off ECS task or CFN custom resource) that completes BEFORE the web service rolls out. The web service MUST perform only a schema-compatibility check on startup and fail fast on mismatch.
- **FR-058 — RDS backups**: The RDS PostgreSQL instance MUST have automated backups enabled by default (backup retention ≥ 7 days, configurable) and point-in-time recovery (PITR) enabled. These are first-class CDK construct settings, not manual console actions. The `instance_size` setting MAY scale retention.
- **FR-059 — S3 versioning**: Both data buckets (`anvil-data-{env}`, `anvil-ml-{env}`) MUST have S3 versioning enabled by default so accidental overwrites/deletes are recoverable. A lifecycle policy MUST expire noncurrent versions after a configurable window (default 30 days) to bound storage cost.

### Related Functional Requirements (shared infrastructure context)

- **FR-045c**: Compute pods and the web tier MUST authenticate to PostgreSQL via **RDS Proxy + IAM database authentication** (`rds-db:connect`). Static database passwords MUST NOT flow to pods.
- **FR-045d**: Secrets that cannot use IAM auth (Redis auth token, SSE signing secret, social OAuth client secrets) MUST be stored in Secrets Manager and delivered to containers via the ECS/Batch task `secrets:` mechanism.
- **FR-045e**: Long-lived SQLAlchemy connection pools MUST use a token-provider callback that regenerates the IAM auth token on new connections.
- **FR-045f**: IAM permissions MUST be least-privilege and split: the **execution role** grants ECR pull, CloudWatch Logs, and scoped Secrets Manager reads; the **job/task role** grants `rds-db:connect`, S3 read/write on the org-scoped prefix, and Redis connectivity.
- **FR-045q**: ElastiCache Redis MUST be deployed in **Multi-AZ mode with automatic failover**.
- **FR-045s — Secret rotation discipline**: Rotation of injected secrets MUST follow the dual-key window pattern for SSE signing and the two-step flow for Redis auth token.

## CDK Stack Architecture

### Stack Organization

```
packages/infra/
├── bin/anvil.ts                # CDK app entrypoint (asset-free synth, digest-pinned images)
├── lib/
│   ├── anvil-stack.ts           # Main stack — orchestrates all constructs
│   ├── networking.ts            # VPC (2-AZ), ALB, CloudFront, WAF, Route53 records
│   ├── database.ts              # RDS PostgreSQL + RDS Proxy (IAM auth), Redis (Multi-AZ)
│   ├── s3-storage.ts            # S3 data + ML buckets with versioning and lifecycle
│   ├── cognito-auth.ts          # Cognito User Pool, app client, Hosted UI domain
│   ├── ecs-services.ts          # ECS Fargate: anvil-web (2+ replicas), MLflow, Cloud Map
│   ├── batch-environment.ts     # Batch-on-EC2: CPU + GPU compute envs, multi-node job defs
│   └── migration-task.ts        # One-off ECS migration task (pre-deploy, AD-6)
├── lambdas/
│   └── post_auth.py             # Cognito post-auth user mapping (inline/S3, not CDK asset)
├── package.json
└── tsconfig.json
```

### Resource Inventory

| Construct | Resource(s) | Key Configuration |
|-----------|-------------|-------------------|
| **networking.ts** | VPC (2 AZ), public/private subnets, NAT Gateways, Internet Gateway, VPC endpoints (S3 Gateway, ECR, Secrets Manager, CloudWatch Logs), ALB, CloudFront distribution, WAF ACL, Route53 A record | SSE-compatible CloudFront timeouts, WAF rate limiting |
| **database.ts** | RDS PostgreSQL instance, RDS Proxy, DB subnet group, parameter group, ElastiCache Redis replication group | Multi-AZ, automated backups (≥7d), PITR, IAM auth via RDS Proxy, in-transit encryption, Redis Multi-AZ auto-failover |
| **s3-storage.ts** | `anvil-data-{env}` bucket, `anvil-ml-{env}` bucket, lifecycle policies | Versioning enabled (both), noncurrent version expiry (default 30d), least-privilege bucket policies |
| **cognito-auth.ts** | Cognito User Pool, app client, User Pool domain, identity providers (social BYO post-deploy) | Email/password sign-in, Hosted UI, NO ALB `authenticate-cognito` |
| **ecs-services.ts** | ECS cluster, Fargate task definitions + services (anvil-web, MLflow), Cloud Map namespace + service, auto-scaling targets/policies | anvil-web: 2+ replicas, autoscale on CPU/memory; MLflow: 1 replica; service discovery for pod→MLflow |
| **batch-environment.ts** | Batch compute environments (CPU + GPU), job queues (cpu/gpu/multigpu/multinode), job definitions (pre-registered per shape), security groups, instance roles | Spot allocation strategy, fair-share scheduling keyed on `org_id`, placement group support for multi-node |
| **migration-task.ts** | One-off ECS Fargate run task definition, CFN Custom Resource or `start-task` in deploy CLI | Pre-rollout gate: migration completes before web service reaches steady state |
| **IAM** (spread across constructs) | Execution roles (ECR pull, CW Logs, Secrets Manager), Task/job roles (rds-db:connect, S3, Redis), Lambda execution role | Least-privilege split per FR-045f; no static DB password in any task definition |
| **Secrets Manager** (spread across) | DB credentials (master password for RDS Proxy), Redis auth token, SSE signing secret, OAuth client secrets | Rotation schedules, IAM policy for execution role read access |
| **lambdas/post_auth.py** | Cognito Post-Authentication Lambda trigger | Inline or versioned S3 reference (not CDK asset), maps Cognito sub → local users row |

### Networking Topology

```text
CloudFront (+ WAF)
    │
    └── ALB
        │
        └── ECS Fargate (anvil-web) — public subnets (AZ 1 + AZ 2)
            ├── RDS Proxy → RDS PostgreSQL — private subnets
            ├── ElastiCache Redis — private subnets (Multi-AZ)
            ├── AWS Batch (EC2) — private subnets
            └── ECS Fargate (MLflow) — private subnets
```

All outbound traffic from private subnets uses NAT Gateways (one per AZ for HA). VPC Gateway Endpoints serve S3. VPC Interface Endpoints serve ECR, Secrets Manager, and CloudWatch Logs. No public internet route from private subnets.

## IAM Role Design

### Role Matrix

| Role | Used By | Permissions | Trust |
|------|---------|-------------|-------|
| `AnvilExecutionRole` | anvil-web ECS task, MLflow ECS task | ECR pull (`GetDownloadUrlForLayer`, `BatchGetImage`, `BatchCheckLayerAvailability`), CloudWatch Logs create/put (`logs:CreateLogStream`, `logs:PutLogEvents`), Secrets Manager read (scoped `secretsmanager:GetSecretValue` on `anvil/*` prefix) | `ecs-tasks.amazonaws.com` |
| `AnvilTaskRole` | anvil-web ECS task | `rds-db:connect` (RDS Proxy IAM auth), S3 read/write on `anvil-data-{env}/*` and `anvil-ml-{env}/*`, ElastiCache connect (SG), KMS decrypt (if SSE-KMS), `batch:SubmitJob`, `batch:DescribeJobs`, `batch:TerminateJob`, `ecs:RunTask` (migration), `sns:Publish` (alert routing) | `ecs-tasks.amazonaws.com` |
| `MlflowTaskRole` | MLflow ECS task | `rds-db:connect` (MLflow DB), S3 read/write on `anvil-ml-{env}/*`, KMS decrypt | `ecs-tasks.amazonaws.com` |
| `BatchExecutionRole` | AWS Batch compute environment | ECR pull, CloudWatch Logs, Secrets Manager read (scoped) | `batch.amazonaws.com` |
| `BatchJobRole` | Compute pod (Batch) | `rds-db:connect` (RDS Proxy), S3 read/write on `anvil-data-{env}/*` (scoped by `{org_id}/` prefix convention), ElastiCache connect, `logs:PutLogEvents`, `logs:CreateLogStream` | `ecs-tasks.amazonaws.com` (ECS Batch) |
| `ReconcilerExecutionRole` | Reconciler ECS task | ECR pull, CloudWatch Logs | `ecs-tasks.amazonaws.com` |
| `ReconcilerTaskRole` | Reconciler ECS task | `rds-db:connect`, `batch:DescribeJobs`, `s3:ListBucket` + `s3:GetObject` (check artifact existence), `mlflow:...` (via MLflow client) | `ecs-tasks.amazonaws.com` |
| `PostAuthLambdaRole` | Post-auth Lambda | `cognito-idp:AdminUpdateUserAttributes`, `rds-db:connect` (read-only for user mapping) | `lambda.amazonaws.com` |

**No role** grants broader access than its function requires. The execution/job split (FR-045f) ensures that a compromised ECS task cannot, e.g., read all Secrets Manager secrets — only the specific `anvil/*` prefix is accessible.

## Secrets Manager Layout

| Secret Name | Contains | Accessed By |
|-------------|----------|-------------|
| `anvil/{env}/db-master-password` | RDS master password (read only by RDS Proxy) | RDS Proxy only |
| `anvil/{env}/redis-auth-token` | ElastiCache Redis auth token | `AnvilExecutionRole` (→ ECS `secrets:` injection into anvil-web) |
| `anvil/{env}/sse-signing-secret` | `{current, previous}` JSON set for SSE token signing | `AnvilExecutionRole` (→ ECS `secrets:` injection into anvil-web) |
| `anvil/{env}/oauth-google` | Google OAuth client ID + secret (set post-deploy) | `AnvilExecutionRole` (→ Cognito IdP config) |
| `anvil/{env}/oauth-github` | GitHub OAuth client ID + secret (set post-deploy) | `AnvilExecutionRole` (→ Cognito IdP config) |

## Pre-Synth / Asset-Free Template Strategy (AD-7)

The CDK app in `packages/infra/` is designed to produce **asset-free** CloudFormation templates:

1. **Container images** are referenced by immutable digest (`@sha256:...`) pointing to GHCR (public registry). No ECR image asset references.
2. **Lambda code** (the post-auth trigger, reconciler) is provided as inline code or uploaded to a versioned S3 path by the deploy CLI, not embedded as CDK assets.
3. **No `cdk bootstrap` dependency**: the templates contain no references to CDKToolkit staging buckets. They deploy into any AWS account without a pre-existing CDK bootstrap stack.
4. **CI pipeline** runs `cdk synth --output cdk.out/` and packages the resulting `*.template.json` into the Python wheel as `package_data`.

## Deployment Flow (cdk deploy)

```text
1. Check prerequisites (Node.js, AWS credentials, CDK CLI, Docker)
2. Build Docker image (multi-stage: builder → runtime)
3. Tag with git commit hash
4. Push to ECR repository
5. Synthesize CDK templates
6. cdk deploy AnvilStack [--hotswap for dev]
     │
     ├── VPC + networking (2 AZ) — first
     ├── RDS + RDS Proxy + Redis — after VPC
     ├── S3 buckets — after VPC
     ├── Secrets Manager entries — after VPC
     ├── IAM roles — after all dependent resources
     ├── ECS cluster + services — after RDS/Redis/S3/IAM
     │   └── Migration task runs (pre-rollout, AD-6)
     │       ├── Alembic upgrade anvil_app schema
     │       ├── Alembic upgrade anvil_mlflow schema
     │       └── Schema compatibility check → web roll-out gated
     ├── Batch compute environments + job queues — after IAM
     ├── Cognito User Pool — standalone
     ├── CloudFront + WAF — last (depends on ALB)
     └── Route53 record (optional, depends on domain config)
```

## CDK Gate Criteria

The following acceptance gates apply specifically to CDK infrastructure (Phase 6 gate from the umbrella spec):

| ID | Criterion | Verification | Pass Condition |
|----|-----------|--------------|----------------|
| G6-INFRA.1 | CDK app synthesizes asset-free templates | `cd packages/infra && cdk synth` | Exit 0; templates contain no CDK asset references |
| G6-INFRA.2 | VPC creates 2 AZ with public/private subnets | `cdk deploy` to dev; AWS API check | VPC exists with subnets in 2 AZs, NAT per AZ |
| G6-INFRA.3 | RDS PostgreSQL + RDS Proxy deployed with IAM auth | AWS API: `rds.describe_db_instances`, `rds.describe_db_proxies` | Instance `available`, Proxy `available`, IAM auth enabled |
| G6-INFRA.4 | Automated backups enabled on RDS | AWS API: `rds.describe_db_instances` | `BackupRetentionPeriod` ≥ 7, PITR enabled |
| G6-INFRA.5 | ElastiCache Redis Multi-AZ with auto-failover | AWS API: `elasticache.describe_replication_groups` | `AutomaticFailover` enabled, ≥ 2 nodes across AZs |
| G6-INFRA.6 | S3 data + ML buckets versioned with lifecycle policy | AWS API: `s3.get_bucket_versioning`, `s3.get_bucket_lifecycle_configuration` | Versioning `Enabled`, lifecycle policy present |
| G6-INFRA.7 | Batch compute environments (CPU + GPU) created | AWS API: `batch.describe_compute_environments` | Both `VALID` + `ENABLED` |
| G6-INFRA.8 | ECS Fargate services (web + MLflow) healthy | AWS API: `ecs.describe_services` | `runningCount == desiredCount`, steady state |
| G6-INFRA.9 | Migration task gates web rollout | Inspect CFN Custom Resource or deploy CLI logs | Migration completed before web service reaches steady |
| G6-INFRA.10 | IAM roles follow least-privilege split | IAM policy review / automated policy audit | Execution vs task role split; no `*` on sensitive actions |
| G6-INFRA.11 | CloudFront distribution serves ALB origin | AWS API: `cloudfront.get_distribution` | Distribution `Deployed`, ALB as origin, SSE timeouts configured |
| G6-INFRA.12 | Cognito User Pool exists with email sign-in | AWS API: `cognito-idp.describe_user_pool` | Pool exists, email sign-in enabled |
| G6-INFRA.13 | WAF ACL attached to CloudFront | AWS API: `wafv2.get_web_acl` | ACL `Active`, associated with distribution |
| G6-INFRA.14 | Lambda post-auth trigger configured | AWS API: `cognito-idp.describe_user_pool` | `PostAuthentication` trigger set to Lambda ARN |

## Success Criteria (CDK-specific)

- **SC-008 (partial)**: The CDK stack is the prerequisite for SC-008's single-command deploy. `cdk deploy` to a dev account creates a `CREATE_COMPLETE` CloudFormation stack. The stack is asset-free — synthesizes without CDK bootstrap dependencies.
- **SC-009 (partial)**: The CDK deployment flow enables `deploy init → verify → destroy` within 30 minutes by codifying every resource.

## Edge Cases

- **What happens when CDK synthesis encounters a missing parameter (e.g., env not set)?** The CDK app reads `ANVIL_ENV` (or `--context env=...`) to select environment-specific parameters. If unset, synth fails with a clear error listing required context.
- **What happens when VPC creation hits AWS service limits?** CloudFormation rolls back with a clear error indicating which limit was hit. The user requests a limit increase and re-deploys.
- **What happens when a migration fails pre-rollout?** The migration task exits non-zero; the CFN Custom Resource (or deploy CLI) marks the stack as `ROLLBACK_IN_PROGRESS` or aborts with a clear error message. The web service is never deployed with an incompatible schema.
- **What happens when a post-auth Lambda deployment fails?** Since the Lambda is not a CDK asset (it's inlined or versioned-S3), failures are limited to IAM policy misconfiguration or runtime errors. The Cognito trigger continues to authenticate existing users; new users lose the auto-mapping feature until the Lambda is fixed.
- **What happens when `cdk deploy --hotswap` is used in dev?** `--hotswap` bypasses CloudFormation for container image updates only (faster dev iteration). Infrastructure changes still go through CloudFormation. This is development-only and MUST NOT be used for staging/production stacks.
- **What happens when ECR push fails (disk full, auth error)?** The deploy script exits before `cdk deploy` is invoked. The previous image remains in the ECR repository; the ECS service continues running with the existing image. No downtime.

## Assumptions

- The CDK stack targets a single AWS region. Multi-region is post-v1.
- Route53 public hosted zone must already exist in the account (or be delegated). CDK can create records but NOT the zone itself.
- The CDK app is the single source of truth. Manual console changes to any resource the stack manages will be overwritten on the next `cdk deploy`.
- The deployment user has sufficient IAM permissions to create all resources in the stack (AdministratorAccess or equivalent scoped policy).
- Container images are built locally (or in CI) and pushed to ECR before `cdk deploy` runs. The image digest is recorded in the CDK context as a stack parameter.
- Secrets Manager entries are created by the CDK stack with auto-generated initial values. Post-deployment command (`deploy config`) rotates them as needed.
- The `anvil-web` service requires 2+ replicas for HA. The `mlflow` service runs as a single replica (restart on failure).
- RDS Proxy is used for all database access — the application never connects to RDS directly. This enables IAM auth and connection pooling.
- Batch compute environments use Spot instances for cost reduction. Spot interruption handling is managed by Batch (auto-retry) with application-level checkpointing.

## Architecture Decisions (Owned)

### AD-6: Migrations — Single Pre-Deploy Step

From the canonical decision record: Alembic migrations run as a single one-off ECS task (or CFN custom resource) BEFORE the web service rolls out. The web service does only a schema-compatibility check on startup and fails fast on mismatch. Applies to both `anvil_app` and `anvil_mlflow` schemas. Rationale: running Alembic on startup with 2+ replicas is a race; pre-deploy migration with rollout gating eliminates it.

### AD-7: Deploy Asset Model — Immutable Image Digests, No CDK Asset References

Pre-synthesized CloudFormation templates MUST be asset-free. Container images referenced by immutable digest (`@sha256:...`) from a public registry (GHCR or public ECR). Lambda code inlined or referenced from a versioned S3 object. No dependency on `cdk bootstrap` / CDKToolkit stack in the customer account.

## Non-Goals

- **No multi-region deployment in v1** — single-region only. Cross-region DR is post-v1.
- **No customer BYO container infrastructure** — the CDK stack provisions compute for anvil's fixed engine only (AD-10). Custom container support would require per-org ECR, image scanning, sandboxing — out of scope for the CDK infrastructure feature.

## References

- [[033 SaaS CDK Infrastructure]]
- [[Reference/SaaSArchitectureDecisions|SaaS Architecture Decisions]] (AD-1, AD-6, AD-7, AD-10)
- [[Specs/016 SaaS Architecture/016 SaaS Architecture|016 SaaS Architecture (superseded umbrella)]]
- [[Specs/032 SaaS Training Pipeline/032 SaaS Training Pipeline|032 SaaS Durable Training]] — Batch job definitions consumed by this stack
- [[Specs/030 SaaS Authentication/030 SaaS Authentication|030 SaaS Cognito Auth]] — Cognito User Pool via CDK
