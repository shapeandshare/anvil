---
title: 033 SaaS CDK Infrastructure - plan
type: plan
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

# Implementation Plan: SaaS CDK Infrastructure

**Branch**: `033-saas-cdk-infrastructure` | **Date**: 2026-06-27 | **Spec**: docs/vault/Specs/033 SaaS CDK Infrastructure/spec.md
**Input**: Feature specification from `docs/vault/Specs/033 SaaS CDK Infrastructure/spec.md` with requirements lifted from umbrella spec `016 SaaS Architecture` Phase 6 (US6), tasks T059–T071.

## Summary

Codify the entire anvil SaaS AWS infrastructure as a TypeScript CDK stack under `packages/infra/`. The stack provisions VPC (2-AZ), RDS PostgreSQL + RDS Proxy (IAM auth, Multi-AZ, automated snapshots/PITR), ElastiCache Redis (Multi-AZ failover), S3 (versioned data + ML buckets), Batch-on-EC2 (CPU + GPU + multi-node), ECS Fargate (web + MLflow), Cloud Map service discovery, migration task (pre-rollout, AD-6), least-privilege IAM (execution vs job/task split, FR-045c/f), CloudFront + WAF, and post-auth Lambda. Asset-free synth with digest-pinned images (AD-7). Cognito User Pool as a first-class CDK resource (FR-022). Pre-synthesized CloudFormation templates bundled into the pip package for `boto3`-based deployment (FR-029). Multi-environment support via different stack names (FR-032).

## Project Structure

### CDK Infrastructure (`packages/infra/`)

```
packages/infra/
├── bin/
│   └── anvil.ts                    # CDK app entrypoint — asset-free synth, digest-pinned images
├── lib/
│   ├── anvil-stack.ts              # Main stack — orchestrates all constructs, environment params
│   ├── networking.ts               # VPC (2 AZ), ALB, NAT Gateways, VPC Endpoints
│   ├── database.ts                 # RDS PostgreSQL + RDS Proxy (IAM auth)
│   ├── redis.ts                    # ElastiCache Redis (Multi-AZ, in-transit encryption)
│   ├── s3-storage.ts               # anvil-data-{env} + anvil-ml-{env} buckets, versioning, lifecycle
│   ├── cognito-auth.ts             # Cognito User Pool, app client, Hosted UI domain, IdP stubs
│   ├── ecs-services.ts             # ECS Fargate: anvil-web (2+ replicas, autoscale) + MLflow (1 replica), Cloud Map
│   ├── batch-environment.ts        # Batch-on-EC2: CPU + GPU compute envs, job queues, multi-node job defs
│   ├── migration-task.ts           # One-off ECS migration task (pre-rollout, AD-6)
│   └── iam.ts                      # IAM role definitions: execution vs task/job split
├── lambdas/
│   └── post_auth.py                # Cognito post-auth user mapping (inline or S3-versioned)
├── cdk.json
├── package.json
└── tsconfig.json
```

### Python Package Integration (`anvil/deploy/templates/`)

```
anvil/deploy/
├── __init__.py
├── command.py                     # deploy CLI entrypoints
├── cloudformation.py              # CFN template loading, stack management via boto3
└── templates/                     # Pre-synthesized *.template.json files from CI
    ├── AnvilStack.template.json   # Main stack template
    └── ...                        # Nested stack templates (if nested stacks used)
```

The templates are bundled via `[tool.setuptools.package-data]` in `pyproject.toml`:
```toml
[tool.setuptools.package-data]
anvil = [
    "deploy/templates/*.json",
    ...
]
```

## CDK Construct Architecture

### Construct Dependencies

```mermaid
graph TD
    A[anvil-stack.ts] --> B[networking.ts]
    A --> C[database.ts]
    A --> D[redis.ts]
    A --> E[s3-storage.ts]
    A --> F[cognito-auth.ts]
    A --> G[ecs-services.ts]
    A --> H[batch-environment.ts]
    A --> I[migration-task.ts]
    A --> J[iam.ts]

    B --> C  # RDS needs VPC subnets
    B --> D  # Redis needs VPC subnets
    B --> G  # ECS needs VPC subnets + ALB
    B --> H  # Batch needs VPC subnets
    B --> I  # Migration task needs VPC subnets
    J --> G  # ECS needs IAM roles
    J --> H  # Batch needs IAM roles
    C --> G  # ECS needs DB connection info
    D --> G  # ECS needs Redis connection info
    E --> G  # ECS needs S3 bucket names
    E --> H  # Batch needs S3 bucket names
    G --> I  # Migration task uses ECS cluster
    B --> K[CloudFront + WAF]  # CloudFront needs ALB
```

## Environment Configuration

The CDK stack consumes environment-specific parameters through CDK context (`cdk.json`), environment variables (`ANVIL_ENV`), or direct constructor arguments:

| Parameter | Source | Description | Dev Default | Prod Default |
|-----------|--------|-------------|-------------|--------------|
| `envName` | context/arg | Environment name | `dev` | `prod` |
| `domainName` | context/arg | Custom domain (optional) | `dev.anvil.io` | `app.anvil.io` |
| `hostedZoneId` | context/arg | Route53 zone ID | Auto-detect | Auto-detect |
| `containerImageDigest` | env/arg | ECR image digest | `latest` | Pinned SHA256 |
| `instanceSize` | context/arg | Resource sizing | `small` | `medium` |
| `adminEmail` | context/arg | Initial admin email | Dev email | Prod email |
| `vpcCidr` | context/arg | VPC CIDR | `10.0.0.0/16` | `10.0.0.0/16` |
| `backupRetentionDays` | context/arg | RDS backup retention | `7` | `30` |
| `s3NoncurrentVersionExpiry` | context/arg | S3 version expiry days | `30` | `90` |

## Instance Sizing

| Size | Web CPU | Web Mem | MLflow CPU | MLflow Mem | RDS Instance | Redis Node Type | Batch CPU Env | Batch GPU Env |
|------|---------|---------|------------|------------|--------------|-----------------|---------------|---------------|
| `small` | 0.5 vCPU | 1 GB | 0.5 vCPU | 1 GB | `db.t4g.small` | `cache.t4g.small` | `c6i.large` | `g4dn.xlarge` |
| `medium` | 1 vCPU | 2 GB | 1 vCPU | 2 GB | `db.t4g.medium` | `cache.t4g.medium` | `c6i.2xlarge` | `g4dn.2xlarge` |
| `large` | 2 vCPU | 4 GB | 2 vCPU | 4 GB | `db.r6g.large` | `cache.r6g.large` | `c6i.4xlarge` | `g4dn.4xlarge` |

## Phasing

The CDK constructs are built in dependency order so each construct is testable immediately after creation. Constructs with no cross-dependency (`[P]` tag) may be built in parallel.

### Phase 1 — Networking & Core Infrastructure

- Networking construct (VPC, subnets, NAT, VPC endpoints, ALB)
- IAM roles construct (execution + task/job roles per FR-045f)
- Secrets Manager entries construct

**Verification**: `cdk synth` produces asset-free template; VPC shows in AWS console with correct subnets.

### Phase 2 — Data Stores

- RDS PostgreSQL + RDS Proxy construct (automated backups + PITR per FR-058)
- ElastiCache Redis construct (Multi-AZ failover per FR-045q)
- S3 buckets construct (versioning + lifecycle per FR-059)

**Verification**: RDS available, RDS Proxy available with IAM auth, Redis replication group with auto-failover, S3 versioning enabled.

### Phase 3 — Compute

- Batch-on-EC2 construct (CPU + GPU compute envs, job queues, multi-node job definitions per AD-1)
- ECS Fargate services construct (anvil-web + MLflow, Cloud Map service discovery)
- Migration task construct (one-off pre-rollout per AD-6)

**Verification**: Batch compute environments VALID/ENABLED; ECS services healthy; migration task runs before web reaches steady state.

### Phase 4 — Auth & Edge

- Cognito User Pool construct (FR-022)
- CloudFront + WAF construct
- Post-auth Lambda (inline/S3, not CDK asset)
- Main stack orchestrator (`anvil-stack.ts`)

**Verification**: Cognito pool exists, CloudFront deployed with ALB origin and WAF, post-auth trigger configured.

### Phase 5 — Entrypoint & CI Integration

- CDK app entrypoint (`bin/anvil.ts`) with environment params and digest-pinned images (AD-7)
- CI synth step: `cdk synth --output cdk.out/` → copy to `anvil/deploy/templates/`
- `package_data` config in `pyproject.toml`

**Verification**: `cdk synth` produces asset-free templates; templates parseable by `boto3` CloudFormation; no CDK bootstrap references.

## Complexity Tracking

| Item | Justification |
|------|---------------|
| TypeScript CDK outside Python package | Standard approach for CDK infrastructure; TypeScript is the canonical CDK language. `packages/infra/` is entirely outside the Python package. No new runtime dep. |
| VPC endpoints for 4 AWS services (S3 Gateway + ECR/Secrets Manager/CW Logs Interface) | Required to keep Batch compute pods in private subnets without NAT transit for AWS API calls. Each endpoint type is a well-documented CDK construct. |
| RDS Proxy + IAM auth eliminates static DB passwords | Review CRITICAL finding — no static credentials flowing to pods. RDS Proxy is the standard AWS pattern for IAM DB auth with connection pooling. Adds ~$15/month per proxy. |
| Multi-AZ Redis with auto-failover | Review HIGH finding — Redis is the live SSE delivery path; single-AZ loss degrades all active streams. Standard CDK replication group construct. |
| Asset-free synth without CDK bootstrap | Review HIGH finding (AD-7) — enables boto3-based deploy into any account without pre-existing bootstrap infrastructure. Requires digest-pinned image references and inline/S3 Lambda code instead of CDK assets. |

## Dependency Changes

- **New dev dependency**: `aws-cdk-lib` (TypeScript, via `packages/infra/package.json`)
- **New dev dependency**: `@aws-cdk/aws-cognito-identitypool-alpha` or equivalent (if needed for identity pools)
- **No new Python runtime dependencies** — all CDK output is consumed via `boto3` (already in `[aws]` extra)

## References

- [[033 SaaS CDK Infrastructure]]
- [[033 SaaS CDK Infrastructure - spec|spec]]
- [[033 SaaS CDK Infrastructure - tasks|tasks]]
- [[Reference/SaaSArchitectureDecisions|SaaS Architecture Decisions]] (AD-1, AD-6, AD-7, AD-10)
