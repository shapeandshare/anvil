---
title: 016 SaaS Architecture - research
type: research
tags:
  - type/spec
  - status/superseded
spec-refs:
  - docs/vault/Specs/016 SaaS Architecture/
related:
  - '[[016 SaaS Architecture]]'
  - '[[Reference/SaaSArchitectureDecisions]]'
status: superseded
created: '2026-06-19'
updated: '2026-06-27'
---

> [!WARNING] Superseded — This artifact is retained for historical reference.
> Research findings have been lifted into per-feature research docs (028–037).
> See [[Specs/016 SaaS Architecture/016 SaaS Architecture|016 index]].

# Research: SaaS Architecture — Three-Mode Operating Model

**Phase 0 output** — resolves all research unknowns for implementation planning.

> [!NOTE]
> **Superseded by post-review decision**: The Cognito section below explored BOTH ALB-managed and app-managed auth. The architecture review (Oracle) flagged mixing them as a CRITICAL mismatch. The binding decision is **AD-2: app-managed OIDC/JWT only** — the FastAPI app validates Cognito JWTs via `aws-jwt-verify`; the ALB does NOT perform `authenticate-cognito`. Treat ALB-auth references below as "option considered, not chosen."

## 1. Cognito Integration

### Decision
Amazon Cognito User Pools with **app-managed** OIDC/JWT validation via `aws-jwt-verify` (AD-2). ALB-managed auth was considered but rejected to avoid the dual-pattern mismatch.

### Rationale
- ALB can authenticate against Cognito natively, setting `x-amzn-oidc-*` headers on forwarded requests
- No custom auth code, no password hashing, no session management in the application
- `aws-jwt-verify` (AWS Labs) is the official JWT verification library — handles ALB and Cognito JWTs
- Cognito Hosted UI provides login/registration/password-reset/MFA out of the box
- Social login (Google, GitHub) is configured in CDK with `UserPoolIdentityProvider*` constructs

### Key Findings
| Aspect | Decision |
|--------|----------|
| **Browser auth** | ALB `authenticate-cognito` action → redirects to Hosted UI → sets `x-amzn-oidc-*` headers |
| **API/JWT validation** | `aws-jwt-verify` library in FastAPI middleware — verifies ALB-signed JWT or Cognito JWT directly |
| **SSE auth** | ALB validates session cookie on initial HTTP connection. Token refresh before cookie expiry. |
| **CLI auth** | OAuth2 Device Authorization Grant (RFC 8628) — user authenticates via browser popup |
| **User mapping** | Cognito Post-Authentication Lambda trigger — upserts local `users` table mapping Cognito `sub` → integer `user_id` |
| **CDK constructs** | `cognito.UserPool` + `UserPoolIdentityProviderGoogle` + `UserPoolIdentityProviderOidc` + `user_pool.add_client()` |
| **Lambda trigger CDK** | `cognito.UserPool.add_trigger(CognitoUserPoolTriggers.POST_AUTH, lambda_fn)` |

### Alternatives Considered
- Custom JWT auth: More control but adds security surface area and maintenance burden. Rejected.
- Auth0: Excellent product but adds a third-party dependency outside AWS. Rejected for AWS-native approach.
- FastAPI middleware-only (no ALB auth): Works but no built-in Hosted UI, no social login. Rejected.

---

## 2. CloudFormation Deployment via boto3

### Decision
Pre-synthesize CDK templates during CI, bundle in the pip package as `package_data`, deploy via `boto3` CloudFormation client using create-or-update pattern with waiters.

### Rationale
- Zero Node.js or CDK CLI dependency on the user's machine — only Python + AWS credentials
- CDK remains the canonical infra definition for the team (in `packages/infra/`)
- CI pipeline runs `cdk synth --output cdk.out/` → packages JSON templates into the wheel
- `anvil deploy up` uses `create_stack` / `update_stack` with waiter polling

### Key Findings
| Aspect | Decision |
|--------|----------|
| **Template source** | `cdk synth` in CI → `cdk.out/AnvilStack/AnvilStack.template.json` → bundled as `anvil/templates/*.json` |
| **Deploy strategy** | Check stack exists → `create_stack` or `update_stack` (with "No updates" graceful handling) |
| **Waiters** | `get_waiter("stack_create_complete")` with `Delay=30, MaxAttempts=120` (60 min timeout) |
| **Parameters** | Dict → `[{"ParameterKey": k, "ParameterValue": v}]` format, injected per environment |
| **Outputs** | `describe_stacks` → `Stacks[0].Outputs` → `{OutputKey: OutputValue}` |
| **Stack naming** | `anvil-{env}` (e.g., `anvil-dev`, `anvil-prod`) |
| **OnFailure** | `OnFailure="ROLLBACK"` for auto-cleanup on failed creation |
| **Rollback** | `enable_termination_protection=False` for dev, `True` for prod |
| **package_data** | `[tool.setuptools.package-data]` → `anvil = ["templates/*.json"]` |
| **Runtime loading** | `importlib.resources.files("anvil.templates").joinpath("stack.json").read_text()` |

### Alternatives Considered
- Running CDK CLI on user machine: Requires Node.js + `cdk bootstrap`. Adds friction. Rejected.
- AWS CLI subprocess: Fragile, platform-dependent. Rejected.
- Terraform: Different toolchain, steep learning curve for team. Rejected.

---

## 3. Redis Pub/Sub for SSE Bridging

### Decision
Use ElastiCache Redis pub/sub with `redis.asyncio` to bridge compute pod metrics → browser SSE. The FastAPI SSE handler subscribes to a per-job Redis channel; the compute pod publishes to it.

### Rationale
- Redis pub/sub is the natural async decoupling layer between ephemeral compute pods and the persistent web server
- ElastiCache (serverless or node-based) supports pub/sub with the standard `redis-py` protocol
- Channel naming follows the pattern `training:metrics:{job_id}` for isolation
- No message durability needed — metrics are transient; final results persist to S3 + DB

### Key Findings
| Aspect | Decision |
|--------|----------|
| **Library** | `redis.asyncio` (part of `redis-py` >= 4.5) — async pub/sub with connection pooling |
| **Channel naming** | `training:metrics:{job_id}` — per-job isolation |
| **SSE handler** | Subscribe in SSE handler's async generator → yield events → unsubscribe on disconnect |
| **Disconnect cleanup** | `request.is_disconnected()` check per iteration → cleanup via `async with` context manager |
| **Heartbeat** | No separate heartbeat needed — compute pod publishes every step; timeout handled client-side |
| **TLS** | ElastiCache with in-transit encryption (`rediss://`) |
| **Security groups** | Batch pod SG → Redis SG on port 6379 |
| **Alternative (SG blocked)** | SQS fan-out → Lambda → Redis. More durable but higher latency. |

### Message Format
```json
{
  "event": "metrics",
  "data": {
    "step": 1500,
    "loss": 2.345,
    "device": "cuda:0",
    "elapsed_sec": 342.5,
    "steps_per_sec": 45.2,
    "eta_sec": 120.0
  }
}
```

### Alternatives Considered
- SQS polling: Durable but higher latency and more complex. Fine for batch, not real-time.
- Direct HTTP from compute pod to Anvil SSE endpoint: Works if SG allows, but couples compute to web lifecycle.
- WebSocket with API Gateway: No existing WebSocket infra, adds cost. SSE is simpler.

---

## 4. Batch Compute Pod Access

### Decision
Two distinct IAM roles (execution + job), IAM database authentication via RDS Proxy, VPC endpoints for AWS services, and Cloud Map service discovery for MLflow.

### Rationale
- The compute pod runs a minimal subset of anvil (`core/engine` + I/O) — no FastAPI, no web server
- It needs S3 (read data, write models), Redis (publish metrics), PostgreSQL (update job status), MLflow HTTP (log experiments)
- All of these are accessible from private subnets with VPC endpoints or internal DNS
- IAM DB auth eliminates static database credentials in Secrets Manager

### Key Findings
| Aspect | Decision |
|--------|----------|
| **IAM execution role** | ECR pull, Secrets Manager read, CloudWatch logs |
| **IAM job role** | S3 read/write, RDS IAM connect, ElastiCache connect, KMS decrypt |
| **RDS access** | RDS Proxy + IAM database authentication (15-min tokens) — no static passwords |
| **S3 access** | Job role IAM policy with separate read/write resource ARNs |
| **MLflow from pod** | Cloud Map service discovery (`mlflow.anvil.local:5000`) — HTTP, no auth needed internally |
| **Network** | Batch pods in private subnets. VPC Gateway Endpoint for S3. VPC Interface Endpoints for ECR, Secrets Manager, CloudWatch Logs. |
| **Security groups** | Batch SG → RDS Proxy SG:5432, Batch SG → Redis SG:6379, Batch SG → MLflow SG:5000 |
| **Environment** | Non-sensitive config via container overrides (`MLFLOW_TRACKING_URI`, `REDIS_HOST`, bucket names). Sensitive via Secrets Manager. |

### IAM Policy Example (Job Role)
```json
{
  "Effect": "Allow",
  "Action": ["s3:GetObject", "s3:ListBucket"],
  "Resource": ["arn:aws:s3:::anvil-data-*", "arn:aws:s3:::anvil-data-*/*"]
},
{
  "Effect": "Allow",
  "Action": ["s3:PutObject"],
  "Resource": ["arn:aws:s3:::anvil-data-*/{user_id}/models/*"]
},
{
  "Effect": "Allow",
  "Action": ["rds-db:connect"],
  "Resource": "arn:aws:rds-db:*:*:dbuser:*/anvil_worker"
},
{
  "Effect": "Allow",
  "Action": ["secretsmanager:GetSecretValue"],
  "Resource": "arn:aws:secretsmanager:*:*:secret:anvil/*"
}
```

### Alternatives Considered
- Direct RDS with Secrets Manager: Valid, but IAM DB auth + RDS Proxy is more secure (auto-rotation, no static creds).
- No VPC endpoints — use NAT Gateway: Works but adds cost and requires internet route for Batch pods.
- MLflow via internal NLB: Works, but Cloud Map service discovery is simpler for ECS internal communication.

---

## Summary of Architecture Decisions

| Area | Decision | Impact |
|------|----------|--------|
| **Auth provider** | Cognito (ALB auth + FastAPI JWT validation) | Zero custom auth code |
| **CLI auth** | OAuth2 Device Authorization Grant | Browser-based auth flow |
| **User mapping** | Post-Auth Lambda → local `users` table | First-login trigger |
| **Infra deployment** | Pre-synthesized CDK → boto3 CloudFormation | One-command deploy, no Node.js |
| **SSE transport** | Redis pub/sub via ElastiCache | Decouples compute from web |
| **Compute pod DB** | RDS Proxy + IAM auth | No static credentials |
| **Compute pod MLflow** | Cloud Map service discovery | Internal HTTP, no auth |
| **Compute pod S3** | Batch job role IAM policy | Least-privilege access |