---
title: 016 SaaS Architecture - quickstart
type: quickstart
tags:
  - type/spec
spec-refs:
  - docs/vault/Specs/016 SaaS Architecture/
related:
  - '[[016 SaaS Architecture]]'
created: ~
updated: ~
---
# Quickstart: SaaS Architecture Development

## Prerequisites

### Local Development (Docker Compose)

- Docker Desktop (macOS) or Docker Engine (Linux)
- `make` + `bash`
- Python 3.11+

### AWS Deployment

- AWS CLI configured (`aws configure`)
- Sufficient IAM permissions (AdministratorAccess or equivalent)
- Route53 public hosted zone (for custom domain)

---

## Mode 1: Local User (Existing — Unchanged)

```bash
pip install anvil
anvil serve
# → http://localhost:8080
```

No SaaS code loaded. SQLite, in-process MLflow, local filesystem, in-process compute.

---

## Mode 2: SaaS Developer — Docker Compose

```bash
# Full SaaS stack emulation locally
docker compose up

# Services:
#   postgres:5432  — anvil_app + anvil_mlflow databases
#   redis:6379     — pub/sub + job queue
#   minio:9000     — S3-compatible API (anvil-data-dev, anvil-ml-dev buckets)
#   mlflow:5000    — MLflow tracking server (postgres backend, minio artifacts)
#   anvil-web:8080 — FastAPI with hot-reload (code mounted from ./anvil/)

# Visit: http://localhost:8080
# MinIO console: http://localhost:9001 (minioadmin / minioadmin)

# For auth: Cognito dev pool or mock (TODO)
```

Env vars for `anvil-web`:
```bash
ANVIL_MODE=saas
DATABASE_URL=postgresql+asyncpg://anvil:anvil_dev@postgres:5432/anvil_app
REDIS_URL=redis://redis:6379/0
S3_ENDPOINT=http://minio:9000
S3_DATA_BUCKET=anvil-data-dev
S3_ACCESS_KEY=minioadmin
S3_SECRET_KEY=minioadmin
MLFLOW_TRACKING_URI=http://mlflow:5000
# Cognito config (dev pool or mock OIDC — see anvil/_saas/auth/dev_setup.py)
COGNITO_USER_POOL_ID=us-east-1_devpool
COGNITO_CLIENT_ID=dev-client-id
COGNITO_REGION=us-east-1
# Secret for signing short-lived SSE stream tokens (FR-020), NOT an app JWT secret
SSE_TOKEN_SIGNING_SECRET=dev-secret-not-for-prod
```

---

## Mode 3: SaaS Developer — Local Code Against Dev AWS

```bash
# Run your local code against shared dev AWS infrastructure
# Compute runs locally (no Batch) for debugger access

pip install anvil[aws]

ANVIL_MODE=saas \
DATABASE_URL=postgresql+asyncpg://dev:...@dev-rds.aws:5432/anvil_app \
REDIS_URL=redis://dev-redis.aws:6379 \
S3_DATA_BUCKET=anvil-data-dev \
MLFLOW_TRACKING_URI=http://dev-mlflow.internal:5000 \
uvicorn anvil._saas.app:app --reload

# Training runs in-process (no Batch) so you can set breakpoints.
# All data goes to dev RDS, dev S3, dev MLflow.
```

---

## Mode 4: SaaS Developer — Deploy to Dev AWS

```bash
# Install the deployment CLI
pip install anvil[aws]

# Deploy to dev environment (interactive prompts for first-time setup)
anvil deploy init --stack-name anvil-dev --region us-east-1

# OR deploy from CDK directly (if you have Node.js)
cd packages/infra
ANVIL_ENV=dev npx cdk deploy --hotswap

# Available at: https://dev.anvil.io
```

---

## Mode 5: Self-Hosted SaaS (End User)

```bash
# One-command deploy into any AWS account
pip install anvil[aws]
anvil deploy init

# Follow the prompts:
#   Domain: models.example.com
#   Region: us-east-1
#   Admin email: admin@example.com
#   Social providers: Google, GitHub
#   Instance size: medium

# ~15 minutes later:
#   CloudFront URL: https://d123.cloudfront.net
#   Custom domain: https://models.example.com
#   Admin email: admin@example.com
#   Credentials saved to: ~/.anvil/admin-credentials
```

---

## Architecture Cheatsheet

| Layer | Local | Docker Compose | Dev AWS | Prod AWS |
|-------|-------|---------------|---------|----------|
| **DB** | SQLite | PostgreSQL (ctr) | RDS dev | RDS prod |
| **MLflow** | In-process | MLflow (ctr) | Dev ECS service | Prod ECS service |
| **Storage** | Filesystem | MinIO (ctr) | Dev S3 | Prod S3 |
| **SSE** | asyncio.Queue | Redis (ctr) | Dev ElastiCache | Prod ElastiCache |
| **Compute** | In-process | In-process | Local (debug) | AWS Batch |
| **Auth** | None | Cognito/mock | Dev Cognito pool | Prod Cognito pool |
| **CDN** | None | None | CloudFront | CloudFront |
| **Deploy** | `make run` | `docker compose up` | `cdk deploy` | `anvil deploy` |

## Project Commands

```bash
# Local development (unchanged)
make setup        # Create venv, install deps
make run          # Start web UI + MLflow locally
make test         # Run tests
make lint         # Lint + typecheck

# SaaS development (new)
make compose-up   # Start full SaaS stack via Docker Compose
make compose-down # Stop SaaS stack

# Deployment (new, requires AWS credentials)
anvil deploy init        # Deploy to AWS
anvil deploy destroy     # Tear down
anvil deploy update      # Upgrade
anvil deploy status      # Check status
```