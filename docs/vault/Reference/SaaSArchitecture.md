---
title: SaaS Architecture — Three-Mode Operating Model
type: reference
tags:
  - type/reference
  - domain/architecture
  - domain/infrastructure
  - domain/mlops
created: '2026-06-19'
updated: '2026-06-19'
aliases:
  - SaaS Architecture
  - Three-Mode Operating Model
  - Remote Mode Architecture
status: status/draft
source: agent
---
# SaaS Architecture — Three-Mode Operating Model

> [!WARNING]
> **Pending Updates (2026-06-19)**: This document predates the SaaS spec-hardening session and does
> NOT yet depict: observability (logs/traces/metrics, FR-052–FR-056), the MLflow reverse proxy
> (FR-057), the cluster-admin model (FR-034–FR-038b), multi-cluster CLI management (FR-014a/c), or
> the backup/DR + HA posture (FR-043a, FR-044a, FR-045q–s, FR-058–061). The spec now defines
> **AD-1 through AD-16**. See [[Decisions/ADR-030-saas-architecture|ADR-030]] and
> [[2026-06-19-saas-spec-hardening|the hardening session log]]. Full narrative + diagram redraw is
> deferred follow-up.

> [!IMPORTANT]
> **Authoritative source**: `specs/016-saas-architecture/spec.md` Architecture Decisions **AD-1 through AD-16** supersede any conflicting detail in this exploration document. Key post-review corrections: compute is **AWS Batch on EC2** (CPU+GPU+multi-node, not Fargate-default — Fargate has no GPU); auth is **app-managed Cognito OIDC/JWT** (not ALB-managed, not custom JWT+refresh); tenancy is **full RBAC** (Organization→Team→Role→User, not user_id-only); job state is **Postgres source-of-truth + append-only job_events + reconciler**; usage metering enables **billback per user/org**.

## Overview

anvil operates in three distinct modes, each targeting a different user persona. All three share the same codebase — the `anvil` pip package — and the same business logic layer. Differences are confined to infrastructure implementations behind a set of abstraction interfaces (`FileStore`, `EventBus`, `JobQueue`, `ComputeBackend`, `LogsReader`, and `VersionedContentStore` — the latter is the versioned content repository from spec 016: pure-Python content-addressed locally, LakeFS-backed in SaaS; see AD-17).

> For granular, full-fidelity per-subsystem diagrams (C4 levels, network, ERD, auth sequences, compute, orchestration, reconciler, deploy flows, CI/CD, observability, MLflow proxy, multi-cluster, HA — 38 diagrams), see [[SaaSSystemDiagrams]]. For security, perimeter, egress, tenant/access boundaries, DFDs, per-user-story flows, and cluster-admin authority (39 diagrams), see [[SaaSSecurityAndFlowDiagrams]].

```mermaid
graph TB
    subgraph "Three Operating Modes"
        direction LR
        L[Local User Mode] --> S[SaaS User Mode]
        S --> D[SaaS Developer Mode]
    end

    L -->|"pip install anvil<br/>anvil serve"| L_DETAIL
    S -->|"browser ──► anvil.io"| S_DETAIL
    D -->|"docker compose up<br/>or cdk deploy"| D_DETAIL

    subgraph L_DETAIL[Local User Mode]
        direction TB
        L1[SQLite] --- L2[In-process MLflow]
        L2 --- L3[Local filesystem]
        L3 --- L4[In-process compute]
        L4 --- L5[No auth]
    end

    subgraph S_DETAIL[SaaS User Mode]
        direction TB
        S1[PostgreSQL<br/>anvil_app + anvil_mlflow] --- S2[Dedicated MLflow service<br/>ECS Fargate]
        S2 --- S3[S3 object store]
        S3 --- S4[AWS Batch compute pods]
        S4 --- S5[Redis pub/sub + job queue]
        S5 --- S6[Cognito auth<br/>Hosted UI + social login<br/>CloudFront + Route53]
        S6 --- S7[Auto-scaling<br/>multi-tenant]
    end

    subgraph D_DETAIL[SaaS Developer Mode]
        direction TB
        D1[docker compose<br/>PostgreSQL + Redis + MinIO + MLflow] --- D2[Local code<br/>against dev AWS services]
        D2 --- D3[cdk deploy ──► dev.aws.com]
        D3 --- D4[Branch → ECR → dev stack]
    end
```

---

## Table of Contents

1. [User Personas](#user-personas)
2. [Local User Mode](#local-user-mode)
3. [SaaS User Mode](#saas-user-mode)
4. [SaaS Developer Mode](#saas-developer-mode)
5. [Feature Support Matrix](#feature-support-matrix)
6. [Data Flows](#data-flows)
7. [AWS Infrastructure](#aws-infrastructure)
8. [Abstraction Contracts](#abstraction-contracts)
9. [Codebase Structure](#codebase-structure)

---

## User Personas

### Local User

| Attribute | Description |
|-----------|-------------|
| **Who** | A developer or researcher who wants to train and experiment with LLMs on their own machine |
| **Install** | `pip install anvil` |
| **Run** | `anvil serve` (or `make run` during development) |
| **Auth** | None — single-user, local-only |
| **Database** | SQLite (`data/anvil-state.db`) |
| **MLflow** | In-process subprocess on `localhost:5001` |
| **Storage** | Local filesystem (`data/`) |
| **Compute** | In-process (stdlib or torch, same process as web server) |
| **SSE** | In-memory `asyncio.Queue` |
| **Scalability** | 1 user, 1 machine, no concurrency |

**Story**: *As a local user, I want to install anvil with a single pip command and train models immediately without any cloud dependencies or account setup.*

### SaaS User

| Attribute | Description |
|-----------|-------------|
| **Who** | A user who visits the hosted anvil website, creates an account, and trains models in the cloud |
| **Install** | None — uses a browser |
| **Run** | Visit `https://anvil.io` |
| **Auth** | Cognito (Google/GitHub/email) — multi-tenant, no custom auth code |
| **Database** | RDS PostgreSQL (`anvil_app` + `anvil_mlflow`) |
| **MLflow** | Dedicated ECS Fargate service, connects to `anvil_mlflow` database |
| **Storage** | S3 (`anvil-data-*`, `anvil-ml-*`) |
| **Compute** | AWS Batch (ephemeral compute pods, N concurrent per user) |
| **SSE** | Redis pub/sub (decouples compute pod from web server) |
| **Scalability** | N users, M concurrent jobs per user, auto-scaling |

**Story**: *As a SaaS user, I want to log in to anvil.io, upload my training data through the web UI, train models in the cloud, and download results — all without installing any software.*

### SaaS Developer

| Attribute | Description |
|-----------|-------------|
| **Who** | A developer contributing to the anvil codebase who needs to test SaaS features locally and deploy to dev environments |
| **Install** | `git clone` + `make setup` |
| **Run** | Three options depending on iteration speed needed |
| **Auth** | Cognito — configurable for local dev (seed pool or mock) |
| **Database** | PostgreSQL in Docker, or shared dev RDS |
| **MLflow** | MLflow in Docker container, or shared dev MLflow service |
| **Storage** | MinIO (S3-compatible) in Docker, or dev S3 bucket |
| **Compute** | Local in-process (for debugging), or AWS Batch for dev stack |
| **SSE** | Redis in Docker, or dev ElastiCache |
| **Scalability** | N/A — development environment |

**Story**: *As a SaaS developer, I want to run the full SaaS stack locally with Docker so I can iterate quickly on UI and API changes, and deploy to a dev AWS environment when I need to test against real cloud services or Batch compute.*

---

## Local User Mode

### Architecture

```mermaid
graph TB
    subgraph "Local Machine — Single Process"
        direction TB
        BROWSER[Browser<br/>localhost:8080] --> FASTAPI[FastAPI<br/>uvicorn]
        FASTAPI --> STATIC[Static files<br/>anvil/api/static]
        FASTAPI --> TEMPLATES[Jinja2 templates]
        FASTAPI --> SSE[SSE endpoint<br/>asyncio.Queue]
        FASTAPI --> API[JSON API routes<br/>20+ endpoints under /v1]

        subgraph "Lifespan Startup"
            DB_INIT[init_engine<br/>SQLite WAL mode] --> MIGRATE[Alembic auto-migrate]
            MIGRATE --> MLFLOW_START[MLflowService.start<br/>port 5001]
            MLFLOW_START --> DEMO_BOOTSTRAP[Demo data bootstrap]
            DEMO_BOOTSTRAP --> WARMUP[Demo model warmup<br/>background thread]
        end

        TRAINING[TrainingService<br/>in-process compute] --> QUEUE[asyncio.Queue<br/>step metrics]
        QUEUE --> SSE

        MLFLOW_PROCS[MLflow subprocess<br/>port 5001] --> MLFLOW_DB[(mlruns/)]

        FASTAPI --> DB[(SQLite<br/>data/anvil-state.db)]

        FASTAPI --> FS[LocalFileStore<br/>data/models/]
        FASTAPI --> MLFLOW_CLIENT[MlflowClient<br/>HTTP to :5001]
    end

    style BROWSER fill:#e1f5fe
    style FASTAPI fill:#fff3e0
    style MLFLOW_PROCS fill:#e8f5e9
    style DB fill:#fce4ec
    style FS fill:#f3e5f5
    style TRAINING fill:#fff8e1
```

### Key Characteristics

- **Single process tree**: `anvil serve` → uvicorn → FastAPI → MLflow subprocess
- **Everything in-process**: Training runs in the same process (stdlib) or thread pool (torch)
- **Zero cloud dependencies**: No S3, no Redis, no PostgreSQL, no Batch
- **Demo bootstrapping**: On first run, demo corpora and datasets are auto-imported; demo model is warmed up in a background thread
- **PID file management**: `logs/web.pid` and `logs/mlflow.pid` for `anvil stop`

### Entrypoint

```bash
pip install anvil
anvil serve
# Opens http://localhost:8080
```

---

## SaaS User Mode

### Architecture — Full Topology

```mermaid
graph TB
    subgraph "Browser"
        BROWSER[Browser ──► anvil.io]
    end

    subgraph "CloudFront"
        CF[CloudFront CDN<br/>static cache, DDoS protection]
    end

    subgraph "AWS VPC"
        direction TB

        subgraph "Public Subnets"
            ALB[ALB<br/>TLS termination<br/>target group]
        end

        subgraph "Private Subnets"
            direction TB

            subgraph "ECS Fargate — Anvil Service"
                ANVIL[anvil-web:latest<br/>2+ replicas, auto-scale]
                ANVIL_AUTH[Cognito JWT middleware<br/>app-managed OIDC, aws-jwt-verify]
                ANVIL_API[JSON API routes<br/>org-scoped RBAC queries]
                ANVIL_SSE[SSE handler<br/>Redis subscriber]
                ANVIL_UPLOAD[File upload<br/>S3 multipart]
            end

            subgraph "ECS Fargate — MLflow Service"
                MLFLOW[mlflow server<br/>1 replica, stateful]
                MLFLOW_HTTP[MlflowClient<br/>HTTP from Anvil]
            end

            subgraph "Data Layer"
                RDS[(RDS PostgreSQL<br/>anvil_app + anvil_mlflow)]
                ELASTICACHE[(ElastiCache Redis<br/>pub/sub + job queue)]
                S3_DATA[S3 — anvil-data-*<br/>user-scoped prefixes]
                S3_ML[S3 — anvil-ml-*<br/>MLflow artifacts]
            end

            subgraph "Compute Layer"
                BATCH_QUEUE[AWS Batch Queue<br/>anvil-training]
                BATCH_ENV[AWS Batch on EC2<br/>CPU + GPU + multi-node, Spot]
                COMPUTE_POD1[Compute Pod<br/>job #1 — user A]
                COMPUTE_POD2[Compute Pod<br/>job #2 — user A]
                COMPUTE_POD3[Compute Pod<br/>job #3 — user B]
            end
        end
    end

    BROWSER --> CF
    CF --> ALB
    ALB --> ANVIL

    ANVIL --> RDS
    ANVIL --> ELASTICACHE
    ANVIL --> S3_DATA
    ANVIL --> MLFLOW_HTTP

    MLFLOW --> RDS
    MLFLOW --> S3_ML

    ANVIL -- submit_job --> BATCH_QUEUE
    BATCH_QUEUE --> BATCH_ENV
    BATCH_ENV --> COMPUTE_POD1
    BATCH_ENV --> COMPUTE_POD2
    BATCH_ENV --> COMPUTE_POD3

    COMPUTE_POD1 -- publish metrics --> ELASTICACHE
    COMPUTE_POD2 -- publish metrics --> ELASTICACHE
    COMPUTE_POD3 -- publish metrics --> ELASTICACHE

    ELASTICACHE -- subscribe --> ANVIL_SSE

    COMPUTE_POD1 -- read training data --> S3_DATA
    COMPUTE_POD1 -- log experiments --> MLFLOW_HTTP
    COMPUTE_POD1 -- write results --> S3_DATA
    COMPUTE_POD1 -- update status --> RDS
```

### Service Mesh (Internal DNS)

```mermaid
graph LR
    subgraph "ECS Service Discovery"
        ANVIL_SVC[anvil-web.svc.local:8080]
        MLFLOW_SVC[mlflow.svc.local:5000]
        REDIS_SVC[redis.svc.local:6379]
        RDS_SVC[postgres.svc.local:5432]
    end

    ANVIL_SVC --> MLFLOW_SVC
    ANVIL_SVC --> REDIS_SVC
    ANVIL_SVC --> RDS_SVC
    COMPUTE_POD --> REDIS_SVC
    COMPUTE_POD --> MLFLOW_SVC
    COMPUTE_POD --> RDS_SVC
```

### Key Characteristics

- **Fully decoupled**: Each service runs in its own container; training runs in ephemeral Batch pods
- **Multi-tenant**: Every database query is scoped by `user_id`; storage paths are `data/{user_id}/...`
- **SSE via Redis**: Compute pods publish step metrics to Redis pub/sub; Anvil pods subscribe and forward to browser EventSource
- **Job queue via AWS Batch**: Anvil calls `batch.submit_job()`; Batch handles queueing, retries, and concurrent execution limits
- **Auto-scaling**: Anvil service scales on CPU/memory/request count; Batch scales on queue depth

### Entrypoint

```
Browser ──► https://anvil.io
         ──► Login page → JWT → Dashboard
```

---

## SaaS Developer Mode

### Option 1: Full Local SaaS Emulation (Fastest Iteration)

```mermaid
graph TB
    subgraph "docker compose up"
        direction TB
        PG[PostgreSQL<br/>anvil_app + anvil_mlflow]
        REDIS[Redis<br/>pub/sub + queue]
        MINIO[MinIO<br/>S3-compatible API]
        MLFLOW[MLflow service]
        ANVIL_DEV[anvil-web<br/>local code mounted<br/>hot-reload enabled]

        PG --- ANVIL_DEV
        REDIS --- ANVIL_DEV
        MINIO --- ANVIL_DEV
        MLFLOW --- ANVIL_DEV
        ANVIL_DEV --- BROWSER_DEV[Browser ──► localhost:8080]
    end

    MINIO --- S3_LOCAL[(MinIO Buckets<br/>anvil-data-dev<br/>anvil-ml-dev)]
    PG --- PG_LOCAL[(PostgreSQL Data<br/>Docker volume)]
```

```yaml
# docker-compose.yml — SaaS emulation
services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: anvil_app
      POSTGRES_PASSWORD: anvil_dev

  redis:
    image: redis:7-alpine

  minio:
    image: minio/minio
    command: server /data --console-address :9001

  mlflow:
    image: ghcr.io/shapeandshare/anvil:latest
    entrypoint: >
      mlflow server
      --backend-store-uri postgresql://anvil:anvil_dev@postgres:5432/anvil_mlflow
      --default-artifact-root s3://anvil-ml-dev/
      --host 0.0.0.0
    environment:
      AWS_ACCESS_KEY_ID: minioadmin
      AWS_SECRET_ACCESS_KEY: minioadmin
      MLFLOW_S3_ENDPOINT_URL: http://minio:9000

  anvil-web:
    build:
      context: .
      dockerfile: Dockerfile.dev
    volumes:
      - ./anvil:/app/anvil  # live code reload
    environment:
      ANVIL_MODE: saas
      DATABASE_URL: postgresql+asyncpg://anvil:anvil_dev@postgres:5432/anvil_app
      REDIS_URL: redis://redis:6379/0
      S3_ENDPOINT: http://minio:9000
      S3_DATA_BUCKET: anvil-data-dev
      JWT_SECRET: dev-secret-not-for-prod
    ports:
      - "8080:8080"
```

### Option 2: Local Code → Dev AWS Services

```bash
# Run your local code against shared dev infrastructure
# Compute runs locally for debugger access
# No Batch — training is in-process for dev speed

ANVIL_MODE=saas \
DATABASE_URL=postgresql+asyncpg://dev:...@dev-rds.aws:5432/anvil_app \
REDIS_URL=redis://dev-redis.aws:6379 \
S3_ENDPOINT=https://s3.us-east-1.amazonaws.com \
S3_DATA_BUCKET=anvil-data-dev \
MLFLOW_TRACKING_URI=http://dev-mlflow.internal:5000 \
JWT_SECRET=... \
uvicorn anvil._saas.app:app --reload
```

### Option 3: Deploy Branch to Dev AWS

```bash
# Full infrastructure deployment
cd packages/infra
ANVIL_ENV=dev cdk deploy --hotswap
# → Builds container, pushes to ECR, updates ECS service
# → Available at https://dev.anvil.io
```

### Developer Iteration Speed Trade-off

```
FAST ◄──────────────────────────────────────────────────► SLOW

docker compose dev    local code → dev AWS    cdk deploy
     │                      │                     │
     ├── Instant changes    ├── Real RDS/Redis    ├── Full AWS infra
     ├── No cloud cost      ├── No Batch          ├── Batch compute
     ├── MinIO for S3       ├── Debug locally     ├── CI/CD pipeline
     └── Hot reload         └── Data-layer bugs   └── E2E validation
```

---

## Feature Support Matrix

| Feature | Local User | SaaS User | SaaS Developer |
|---------|:----------:|:---------:|:--------------:|
| **Web UI** | ✅ Jinja2 served locally | ✅ Jinja2 served via CloudFront | ✅ Docker hot-reload |
| **REST API** | ✅ `/v1/*` routes | ✅ Same routes, user-scoped | ✅ Same routes |
| **SSE streaming** | ✅ In-process asyncio.Queue | ✅ Redis pub/sub | ✅ Docker Redis |
| **Training (stdlib)** | ✅ In-process | ✅ AWS Batch on EC2 (CPU) | ✅ Docker or local |
| **Training (torch)** | ✅ In-process thread | ✅ AWS Batch (EC2 Spot GPU) | ⚠️ GPU passthrough |
| **Training (modal)** | ✅ Via Modal SDK | ❌ N/A | ❌ N/A |
| **File upload** | ✅ Browser upload | ✅ Browser + CLI | ✅ Browser + CLI |
| **File download** | ✅ Direct filesystem | ✅ S3 signed URLs | ✅ MinIO or S3 |
| **MLflow tracking** | ✅ In-process subprocess | ✅ Dedicated ECS service | ✅ Docker MLflow |
| **Experiment history** | ✅ SQLite | ✅ PostgreSQL | ✅ PostgreSQL |
| **Model registry** | ✅ MLflow | ✅ MLflow + S3 | ✅ MLflow + MinIO |
| **Dataset management** | ✅ Local filesystem | ✅ S3 | ✅ MinIO or S3 |
| **Corpus management** | ✅ Local filesystem | ✅ S3 | ✅ MinIO or S3 |
| **Auth / login** | ❌ None | ✅ Cognito (app-managed OIDC/JWT) | ✅ Configurable |
| **Multi-user isolation** | ❌ Single-user | ✅ user_id scoping | ✅ Same as prod |
| **Auto-scaling** | ❌ N/A | ✅ ECS + Batch | ❌ Dev scale |
| **CLI remote push/pull** | ❌ N/A | ✅ `anvil remote` | ✅ Against dev |
| **CDN** | ❌ N/A | ✅ CloudFront | ❌ N/A |
| **Custom domain** | ❌ N/A | ✅ Route53 + CloudFront | ✅ Per env |
| **Container deployment** | ❌ pip install | ✅ ECS Fargate | ✅ Docker compose |
| **Compute pod isolation** | ❌ Single process | ✅ Per-job containers | ✅ Per-job or in-process |

---

## Data Flows

### Local Mode: Training Flow

```mermaid
sequenceDiagram
    participant B as Browser
    participant F as FastAPI
    participant T as TrainingService
    participant Q as asyncio.Queue
    participant C as Compute (in-process)
    participant M as MLflow (subprocess)

    B->>F: POST /v1/training/start {config}
    F->>T: reserve_run()
    T->>T: create asyncio.Queue
    F-->>B: { run_id }
    B->>F: GET /v1/training/stream/{run_id} (EventSource)

    F->>T: start_training(config)
    T->>C: train(data, callback=progress_cb)

    loop Every step
        C->>C: model.forward(), model.backward()
        C->>T: callback(step, loss)
        T->>Q: run_coroutine_threadsafe(queue.put({metrics}))
        Q->>F: queue.get() → yield SSE event
        F->>B: event: metrics\ndata: {step, loss}
    end

    C->>T: completion callback
    T->>M: mlflow.log_metrics(...)
    T->>M: mlflow.log_artifact(model.safetensors)
    T->>Q: queue.put({event: complete})
    Q->>F: queue.get() → yield SSE event
    F->>B: event: complete\ndata: {final_loss, samples}
```

### SaaS Mode: Training Flow

```mermaid
sequenceDiagram
    participant B as Browser
    participant A as Anvil Pod
    participant R as RDS PostgreSQL
    participant Q as Redis
    participant BA as AWS Batch
    participant C as Compute Pod
    participant M as MLflow Service
    participant S as S3

    B->>A: POST /v1/training/start {config}
    A->>R: INSERT training_job (status=pending)
    A->>S: PUT jobs/{job_id}/config.json
    A->>BA: batch.submit_job(jobQueue=anvil-training, jobDefinition=anvil-compute-worker, containerOverrides={JOB_ID, CONFIG_S3_KEY})
    A-->>B: { job_id }

    B->>A: GET /v1/training/stream/{job_id} (EventSource)
    A->>Q: SUBSCRIBE training:metrics:{job_id}

    BA->>C: Launch compute pod
    C->>R: UPDATE training_job SET status=running
    C->>S: GET jobs/{job_id}/config.json
    C->>S: GET data/{user_id}/datasets/{dataset_id}/

    loop Every step
        C->>C: model.forward(), model.backward()
        C->>Q: PUBLISH training:metrics:{job_id} {step, loss}
        Q->>A: Message received
        A->>B: event: metrics\ndata: {step, loss}
    end

    C->>M: mlflow.log_metrics(...)
    C->>S: PUT data/{user_id}/models/{model_id}/model.safetensors
    C->>R: UPDATE training_job SET status=completed, artifact_path=...
    C->>Q: PUBLISH training:metrics:{job_id} {event: complete}
    Q->>A: Message received
    A->>B: event: complete\ndata: {final_loss, samples}
    C->>C: Exit (pod terminates)
```

### SaaS Mode: File Upload Flow

```mermaid
sequenceDiagram
    participant U as User
    participant B as Browser
    participant A as Anvil Pod
    participant S as S3
    participant R as RDS

    U->>B: Select files to upload
    B->>A: POST /v1/corpora/create {name, files...}
    A->>A: Generate signed S3 URLs
    A->>B: { upload_urls: {...} }
    B->>S: PUT {signed_url} — direct upload to S3
    B->>A: POST /v1/corpora/ingest {corpus_id}
    A->>S: GET data/{user_id}/corpora/{id}/* — read files
    A->>A: Chunk, tokenize, index
    A->>R: INSERT corpus metadata
    A-->>B: { corpus_id, document_count }
```

---

## AWS Infrastructure

### CDK Stack Topology

```mermaid
graph TB
    subgraph "CDK Stack: AnvilSaasStack"
        direction TB

        NETWORKING[VPC<br/>2 AZ, 1 NAT GW per AZ]
        DNS[Route53 Zone<br/>anvil.io]
        CERT[ACM Certificate<br/>*.anvil.io]
        CDN[CloudFront Distribution<br/>static cache, WAF]
        ALB[Application Load Balancer<br/>internet-facing, TLS]
        ECS_CLUSTER[ECS Cluster<br/>Fargate launch type]

        subgraph "ECS Services"
            ANVIL_SVC[anvil-web<br/>service: AnvilService<br/>task: AnvilTask<br/>min=2, max=10]
            MLFLOW_SVC[mlflow<br/>service: MlflowService<br/>task: MlflowTask<br/>replicas=1]
        end

        DATA[(RDS Cluster<br/>anvil_app + anvil_mlflow)]
        REDIS[ElastiCache Redis<br/>serverless]

        S3_DATA_BUCKET[S3 Bucket<br/>anvil-data-{env}]
        S3_ML_BUCKET[S3 Bucket<br/>anvil-ml-{env}]

        subgraph "AWS Batch"
            BATCH_ENV[ComputeEnvironment<br/>Fargate + EC2 Spot]
            BATCH_QUEUE[JobQueue<br/>anvil-training-{env}]
            BATCH_DEF[JobDefinition<br/>anvil-compute-worker]
        end

        SECRETS[Secrets Manager<br/>/anvil/{env}/*]
        LOGS[CloudWatch Log Groups<br/>/ecs/anvil/*]
    end

    CDN --> ALB
    DNS --> CDN
    ALB --> ANVIL_SVC
    ALB --> CERT
    ANVIL_SVC --> DATA
    ANVIL_SVC --> REDIS
    ANVIL_SVC --> S3_DATA_BUCKET
    ANVIL_SVC --> MLFLOW_SVC
    MLFLOW_SVC --> DATA
    MLFLOW_SVC --> S3_ML_BUCKET
    ANVIL_SVC --> BATCH_QUEUE
    BATCH_QUEUE --> BATCH_ENV
    BATCH_ENV --> BATCH_DEF
    BATCH_DEF --> DATA
    BATCH_DEF --> REDIS
    BATCH_DEF --> S3_DATA_BUCKET
    BATCH_DEF --> MLFLOW_SVC

    ANVIL_SVC --> SECRETS
    BATCH_DEF --> SECRETS
    ANVIL_SVC --> LOGS
    MLFLOW_SVC --> LOGS
```

### S3 Bucket Structure

```
anvil-data-{env}/
├── {user_id}/
│   ├── corpora/
│   │   ├── {corpus_id}/
│   │   │   ├── files/
│   │   │   └── chunks/
│   ├── datasets/
│   │   └── {dataset_id}/
│   ├── models/
│   │   └── {model_id}/
│   │       ├── model.safetensors
│   │       ├── config.json
│   │       └── tokenizer.json
│   └── exports/
│       └── {export_id}/
└── jobs/
    └── {job_id}/
        └── config.json

anvil-ml-{env}/
├── {experiment_id}/
│   └── {run_id}/
│       ├── model.safetensors
│       ├── config.json
│       ├── tokenizer.json
│       └── metrics/

anvil-content-{env}/                # LakeFS storage namespace (versioned content repo, spec 016 / AD-17)
└── {org_id}/                        # org-isolated; LakeFS repo(s) back the canonical Corpus
    └── <lakefs-managed objects>     # content-addressed blobs + commit/version metadata
```

> **Content repository (AD-17)**: The versioned content repository (spec 016) is served
> by `LakeFSVersionedContentStore` over the `anvil-content-{env}` bucket as the LakeFS
> storage namespace; corpus/version/entry metadata lives in PostgreSQL. Content is
> org-isolated (`org_id`); the externally-pinned reproducibility ref is the content-
> addressed **manifest digest** (identical to local mode). Validation, isolation, and
> serialized acceptance run **in-process** (not LakeFS hooks); producer + management
> authorization is enforced at the app layer (per-branch RBAC is enterprise-only in
> LakeFS OSS). In **local mode** there is no LakeFS and no `anvil-content` bucket — the
> content store is pure-Python over `data/content/` on the filesystem.

### Secrets Manager Structure

```
/anvil/{env}/
├── database/master-password
├── database/app-username
├── database/app-password
├── redis/auth-token
├── jwt/secret
└── s3/data-bucket-name
```

### IAM Roles

| Role | Trusts | Permissions |
|------|--------|-------------|
| `AnvilTaskRole` | ECS (anvil-web) | S3 read/write (anvil-data), Secrets Manager read, Batch submit_job, ElastiCache connect |
| `MlflowTaskRole` | ECS (mlflow) | S3 read/write (anvil-ml), PostgreSQL connect |
| `BatchTaskRole` | Batch (compute worker) | S3 read/write (anvil-data), ElastiCache connect, MLflow HTTP, Secrets Manager read |
| `BatchInstanceRole` | Batch (EC2 instances) | ECR pull, CloudWatch logs |

---

## Abstraction Contracts

The four interfaces that enable all three modes to share the same service layer. Each has a local (in-process) implementation and a cloud (SaaS) implementation.

### 1. FileStore

```python
"""Abstract storage backend for application data.

All user-facing data (corpora, datasets, models, exports) flows through
this interface. Local mode writes to disk; SaaS mode writes to S3.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import (
    AsyncIterator,
    BinaryIO,
    Protocol,
)


class FileStore(ABC):
    """Abstract file storage for application data."""

    @abstractmethod
    async def read(self, path: str) -> bytes:
        """Read the contents of a file at *path*.

        Parameters
        ----------
        path : str
            File path relative to the store root.

        Returns
        -------
        bytes
            Raw file contents.

        Raises
        ------
        FileNotFoundError
            If the path does not exist.
        """

    @abstractmethod
    async def write(self, path: str, data: bytes) -> None:
        """Write *data* to *path*, creating parent directories as needed.

        Parameters
        ----------
        path : str
            File path relative to the store root.
        data : bytes
            Raw file contents to write.
        """

    @abstractmethod
    async def delete(self, path: str) -> None:
        """Delete the file at *path*.

        Parameters
        ----------
        path : str
            File path relative to the store root.

        Raises
        ------
        FileNotFoundError
            If the path does not exist.
        """

    @abstractmethod
    async def list(self, prefix: str) -> list[str]:
        """List all file paths under *prefix*.

        Parameters
        ----------
        prefix : str
            Directory prefix to list.

        Returns
        -------
        list of str
            Relative paths of all files under the prefix.
        """

    @abstractmethod
    async def exists(self, path: str) -> bool:
        """Check whether a file exists at *path*.

        Parameters
        ----------
        path : str
            File path relative to the store root.

        Returns
        -------
        bool
        """

    @abstractmethod
    async def signed_download_url(self, path: str, expires_in: int = 3600) -> str:
        """Generate a time-limited URL for direct download.

        Parameters
        ----------
        path : str
            File path relative to the store root.
        expires_in : int
            URL validity in seconds. Defaults to 3600 (1 hour).

        Returns
        -------
        str
            Signed URL for direct HTTP download.

        Raises
        ------
        FileNotFoundError
            If the path does not exist.
        """

    @abstractmethod
    async def signed_upload_url(self, path: str, expires_in: int = 3600) -> str:
        """Generate a time-limited URL for direct upload.

        Parameters
        ----------
        path : str
            File path relative to the store root.
        expires_in : int
            URL validity in seconds. Defaults to 3600 (1 hour).

        Returns
        -------
        str
            Signed URL for direct HTTP PUT upload.
        """
```

#### Implementations

| Implementation | Backend | Mode |
|----------------|---------|------|
| `LocalFileStore` | `Path(filesystem)` — reads/writes under a root directory | Local user |
| `S3FileStore` | `boto3` S3 client — reads/writes to S3 bucket with `user_id` prefix | SaaS user + developer |

---

### 2. EventBus

```python
"""Publish/subscribe abstraction for real-time training metrics.

Decouples compute pods (producers) from web server SSE handlers
(consumers) so they can run in separate processes or containers.
"""

from abc import ABC, abstractmethod
from typing import Any, AsyncIterator


class EventBus(ABC):
    """Publish/subscribe for streaming events (training metrics)."""

    @abstractmethod
    async def publish(self, channel: str, event: dict[str, Any]) -> None:
        """Publish an event to *channel*.

        Parameters
        ----------
        channel : str
            Channel name (e.g. ``"training:metrics:{job_id}"``).
        event : dict
            JSON-serialisable event payload.
        """

    @abstractmethod
    async def subscribe(self, channel: str) -> AsyncIterator[dict[str, Any]]:
        """Subscribe to events on *channel*, yielding them as they arrive.

        Parameters
        ----------
        channel : str
            Channel name to subscribe to.

        Yields
        ------
        dict
            Event payload (``{"event": str, "data": ...}``).
        """

    @abstractmethod
    async def unsubscribe(self, channel: str) -> None:
        """Unsubscribe from *channel*.

        Parameters
        ----------
        channel : str
            Channel name to unsubscribe from.
        """

    @abstractmethod
    async def close(self) -> None:
        """Release all resources (connections, threads)."""
```

#### Implementations

| Implementation | Backend | Mode |
|----------------|---------|------|
| `InProcessEventBus` | Wraps `asyncio.Queue` — same-process producer/consumer | Local user |
| `RedisEventBus` | `redis.asyncio` pub/sub — cross-process, cross-container | SaaS user + developer |

---

### 3. JobQueue

```python
"""Asynchronous job dispatch abstraction.

Encapsulates how training jobs are submitted for execution. Local mode
runs immediately in-process. SaaS mode dispatches to AWS Batch.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any, Optional


class JobStatus(StrEnum):
    """Status of a training job in the system."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class TrainingJob:
    """A training job specification.

    Parameters
    ----------
    job_id : str
        Unique identifier for this job.
    user_id : int
        The user who owns this job.
    config : dict
        Training hyperparameters and dataset references.
    status : JobStatus
        Current status. Defaults to ``PENDING``.
    created_at : datetime
        When the job was created.
    started_at : datetime, optional
        When execution began.
    completed_at : datetime, optional
        When execution finished.
    error : str, optional
        Error message if the job failed.
    artifact_path : str, optional
        Path to result artifacts in FileStore.
    """
    job_id: str
    user_id: int
    config: dict[str, Any]
    status: JobStatus = JobStatus.PENDING
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None
    artifact_path: str | None = None


class JobQueue(ABC):
    """Abstract job submission and lifecycle tracking."""

    @abstractmethod
    async def submit(self, job: TrainingJob) -> str:
        """Submit a training job for execution.

        Parameters
        ----------
        job : TrainingJob
            The job specification.

        Returns
        -------
        str
            The external queue provider's job ID (e.g. AWS Batch job ID).
        """

    @abstractmethod
    async def cancel(self, job_id: str) -> None:
        """Cancel a pending or running job.

        Parameters
        ----------
        job_id : str
            The job ID to cancel.
        """

    @abstractmethod
    async def status(self, job_id: str) -> JobStatus:
        """Query the current status of a job.

        Parameters
        ----------
        job_id : str
            The job ID to query.

        Returns
        -------
        JobStatus
        """

    @abstractmethod
    async def list_active(self, user_id: int) -> list[TrainingJob]:
        """List all active (pending or running) jobs for a user.

        Parameters
        ----------
        user_id : int
            The user whose jobs to list.

        Returns
        -------
        list of TrainingJob
        """
```

#### Implementations

| Implementation | Backend | Mode |
|----------------|---------|------|
| `InProcessJobQueue` | Immediately executes via `asyncio.create_task` | Local user |
| `BatchJobQueue` | `boto3` `batch.submit_job(...)` — writes config to S3 first | SaaS user + developer |

---

### 4. ComputeBackend

```python
"""Compute backend abstraction — extends the existing pattern.

The existing ``ComputeBackend`` from ``anvil/services/compute/`` already
supports ``local-stdlib``, ``local-torch``, and ``modal``. This adds a
``batch`` variant that dispatches through the JobQueue.
"""

from abc import ABC, abstractmethod
from typing import Any, Callable, Optional

from .event_bus import EventBus
from .job_queue import JobQueue, TrainingJob


class ComputeBackend(ABC):
    """Abstract training execution backend."""

    @abstractmethod
    async def run(
        self,
        job: TrainingJob,
        event_bus: EventBus,
        progress_callback: Callable[[int, float], None] | None = None,
    ) -> dict[str, Any]:
        """Execute a training job.

        Parameters
        ----------
        job : TrainingJob
            The job to execute.
        event_bus : EventBus
            Channel for publishing live step metrics.
        progress_callback : callable, optional
            Synchronous callback for per-step progress (used in local
            mode for direct queue injection).

        Returns
        -------
        dict
            Result with keys: ``final_loss``, ``samples``, ``model``,
            ``artifact_path``, ``error``.
        """
```

#### Implementations

| Implementation | Execution model | Mode |
|----------------|-----------------|------|
| `LocalStdlibBackend` | In-process, same thread | Local user |
| `LocalTorchBackend` | In-process, thread pool | Local user |
| `ModalBackend` | Remote Modal cloud GPU | Local user |
| `BatchComputeBackend` | Wraps `JobQueue.submit()` — no local execution | SaaS user + developer |

---

## Codebase Structure

```
anvil/
├── cli.py                  # pip-install user: anvil serve, anvil train, etc.
├── config.py               # Shared config (env vars, LRU-cached)
│
├── core/                   # Zero-dependency training engine (untouched)
│   ├── engine.py           # Transformer: RoPE, SwiGLU MLP, RMSNorm
│   ├── torch_engine.py     # PyTorch training loop
│   ├── autograd.py         # Custom autograd engine
│   └── tokenizer.py        # Byte-level tokenizer
│
├── db/                     # Async SQLAlchemy (SQLite + PostgreSQL)
│   ├── models/             # ORM models — all get user_id in SaaS mode
│   ├── repositories/       # Repository pattern — all get user_id filter
│   └── session.py          # Engine + session factory
│
├── services/               # Business logic (shared across all modes)
│   ├── training/           # Training orchestration, export
│   ├── tracking/           # MLflow experiment tracking (HTTP client)
│   ├── datasets/           # Corpora, datasets, import, curation
│   ├── inference/          # Inference, loaded model
│   ├── compute/            # Compute backend abstraction (extended)
│   ├── auth/               # ** NEW ** Cognito JWT validation, user mapping middleware
│   └── _shared/            # Cross-domain types
│
├── api/                    # FastAPI (local mode, unchanged)
│   ├── app.py              # Local-mode FastAPI factory
│   ├── v1/                 # Route definitions (shared with _saas)
│   ├── static/             # Frontend assets
│   └── templates/          # Jinja2 templates
│
├── _saas/                  # ** NEW ** SaaS-only module
│   ├── __init__.py
│   ├── app.py              # SaaS-mode FastAPI factory (wires cloud impls)
│   ├── compute_worker.py   # AWS Batch entrypoint
│   ├── auth/               # JWT middleware, user dependency
│   └── implementations/
│       ├── s3_file_store.py
│       ├── redis_event_bus.py
│       ├── batch_job_queue.py
│       └── batch_compute_backend.py
│
├── supervisor/             # Process manager (local MLflow only)
│   ├── supervisor.py       # ProcessSupervisor
│   └── services.py         # MLflowService
│
└── storage/                # File store abstraction
    ├── __init__.py         # FileStore interface
    └── local.py            # LocalFileStore (existing)

packages/
└── infra/                  # ** NEW ** CDK infrastructure
    ├── lib/
    │   ├── anvil-stack.ts          # Main stack
    │   ├── anvil-service.ts        # Anvil ECS service construct
    │   ├── mlflow-service.ts       # MLflow ECS service construct
    │   ├── batch-environment.ts    # AWS Batch compute construct
    │   ├── networking.ts           # VPC, ALB, CloudFront
    │   └── database.ts             # RDS + Redis constructs
    ├── bin/
    │   └── anvil.ts                # CDK app entrypoint
    └── package.json
```

### SaaS-only imports never pollute local mode

```python
# In _saas/app.py — imported only when ANVIL_MODE=saas
import boto3
import redis.asyncio as aioredis
```

```python
# Local mode — never touches boto3 or redis-py
from anvil.app import app  # anvil serve
```

---

## User Stories

### Local User

| # | Story | Implementation |
|---|-------|---------------|
| L1 | As a local user, I want to `pip install anvil` and have it work immediately | All deps declared in `pyproject.toml`; no cloud SDKs needed |
| L2 | As a local user, I want to `anvil serve` and get a working web UI at `localhost:8080` | Existing `serve()` entrypoint; lifespan handles DB, MLflow, demo bootstrap |
| L3 | As a local user, I want to upload a text file and train a model on it | Existing corpus/dataset upload + training flow |
| L4 | As a local user, I want to see live training metrics in the browser | Existing SSE via `asyncio.Queue` |
| L5 | As a local user, I want to `anvil stop` to cleanly shut everything down | Existing `stop()` — PID file + port scan |
| L6 | As a local user, I want my data to persist between restarts | SQLite file + filesystem are persistent |
| L7 | As a local user, I want to export trained models in safetensors format | Existing `SafetensorsExportService` |

### SaaS User

| # | Story | Implementation |
|---|-------|---------------|
| S1 | As a SaaS user, I want to sign in with Google/GitHub/email | Cognito Hosted UI — no custom auth code |
| S2 | As a SaaS user, I want to see only my own corpora, datasets, and experiments | All queries scoped by `user_id` mapped from Cognito `sub` |
| S3 | As a SaaS user, I want to upload training data through the browser | Signed S3 URLs → direct upload → async ingest |
| S4 | As a SaaS user, I want to start a training job and watch it live | Anvil creates job → Batch launches pod → Redis pub/sub → SSE |
| S5 | As a SaaS user, I want to run multiple training jobs simultaneously | Batch queue handles concurrency; each job = 1 pod |
| S6 | As a SaaS user, I want to download my trained models | Signed S3 URLs for direct download |
| S7 | As a SaaS user, I want to compare experiment metrics in the MLflow UI | MLflow service accessible via browser (auth-gated) |
| S8 | As a SaaS user, I want my session to persist across browser tabs | httpOnly JWT cookie shared across all tabs on `anvil.io` |
| S9 | As a SaaS user, I want to use the CLI to push/pull data from my local machine | `anvil remote login` → stores JWT → `push`/`pull`/`ls` commands |

### SaaS Developer

| # | Story | Implementation |
|---|-------|---------------|
| D1 | As a SaaS developer, I want to run the full SaaS stack locally with Docker | `docker compose up` — PostgreSQL, Redis, MinIO, MLflow, anvil-web |
| D2 | As a SaaS developer, I want hot-reload for frontend changes in local SaaS mode | Docker volume mounts `./anvil:/app/anvil` + `--reload` |
| D3 | As a SaaS developer, I want to run my local code against dev AWS services | Env var config → local FastAPI connects to dev RDS/Redis/S3 |
| D4 | As a SaaS developer, I want to deploy my branch to a dev AWS environment | `cdk deploy` → builds ECR image → updates ECS service |
| D5 | As a SaaS developer, I want to debug training without Batch | Local mode compute backend while SaaS services for DB/storage/MLflow |
| D6 | As a SaaS developer, I want to test auth flows without a real JWT secret | Dev config uses a known JWT secret; seeded test users |
| D7 | As a SaaS developer, I want infra tests in CDK to prevent misconfiguration | CDK assertions; synth snapshot tests |
