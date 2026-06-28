---
title: 029 SaaS Dev Stack - spec
type: spec
tags:
  - type/spec
spec-refs:
  - docs/vault/Specs/029 SaaS Dev Stack/
related:
  - '[[029 SaaS Dev Stack]]'
created: '2026-06-27'
updated: '2026-06-27'
---

# Feature Specification: SaaS Dev Stack — Docker Compose Local SaaS Emulation

**Feature Branch**: `029-saas-dev-stack`
**Created**: 2026-06-27
**Status**: Draft

## Owner

Spec 029. Plan phase 10 (US5). Tasks T089–T093.

## Dependencies

- **028** (needs the abstraction framework — the compose stack runs the SaaS entrypoint which depends on `anvil/_saas/` and `anvil/storage/` interfaces).
- **Local-mode risk: LOW** — all new files. `docker compose up` launches the **SaaS** entrypoint (`anvil._saas.app:app`), a different process from `anvil serve`. No overlap with the local path.

## Shipping Priority

This feature is intentionally recommended to ship **2nd** (after Feature 1 — Abstraction Framework) despite being plan phase 10, because it provides the fast iteration loop for every subsequent SaaS feature. The umbrella's recommended shipping order is:

| # | Feature |
|---|---------|
| 1 | Abstraction Framework |
| **2** | **SaaS Dev Stack (this feature)** |
| 3 | Cognito Auth |
| 4 | Multi-Tenancy & RBAC |
| 5 | Durable Training Pipeline (CORE) |

## Functional Requirements

- **FR-012**: System MUST support a docker compose development environment that emulates SaaS infrastructure (PostgreSQL, Redis, MinIO, MLflow) for local development.
- **FR-013**: System MUST support three developer iteration modes: docker compose, local code against dev AWS, and cdk deploy to dev environment.

## User Story 5 — SaaS Developer Runs Full Stack Locally (Priority: P2)

A developer clones the repo and runs `docker compose up` to start PostgreSQL, Redis, MinIO, MLflow, and the anvil web service with hot-reload. They can make changes to the code and see them reflected immediately.

**Why this priority**: Developer velocity directly impacts how fast SaaS features ship. Docker compose emulation is the fastest iteration loop.

**Independent Test**: Run `docker compose up`, verify the anvil web UI loads at localhost:8080, register a user, upload a corpus, and start a training job (compute runs in-process for dev speed). Verify SSE metrics stream in the browser.

### Acceptance Scenarios

1. **Given** the developer runs `docker compose up`, **When** all containers are healthy, **Then** the anvil web UI is available at localhost:8080.
2. **Given** the developer modifies Python code in the mounted volume, **When** the file is saved, **Then** the uvicorn process reloads and the change is reflected without container rebuild.
3. **Given** the docker compose stack is running, **When** the developer starts a training job, **Then** compute runs in-process (not Batch), writing results to the local MinIO and PostgreSQL containers.

### Edge Cases

- **What if docker-compose.yml references a port already in use?** Compose fails immediately with a port-conflict error. Developer kills the conflicting process or changes the host port mapping.
- **What if the anvil-web container crashes on startup?** Docker Compose restart policy (`unless-stopped` or `on-failure`) restarts it. Logs are visible via `docker compose logs anvil-web`.
- **What if hot-reload doesn't pick up changes?** Ensure the mounted volume maps the correct source directory. Check that `--reload` flag is present in the uvicorn command. If uvloop is installed, reload is incompatible — dev deps must exclude uvloop.
- **What if MinIO buckets don't exist on startup?** The `anvil-web` container entrypoint or a separate init container creates the required buckets (`anvil-data-dev`, `anvil-ml-dev`) on first start.
- **What if PostgreSQL is not ready when anvil-web starts?** The startup checks for DB connectivity with retries and backoff before attempting migrations. If unavailable, logs show connection refused and the process retries.
- **What if the developer needs to reset the dev environment?** `docker compose down -v` removes all volumes (DB data, MinIO data, MLflow data) for a complete reset. `make compose-reset` wraps this.

## Requirements

### Functional Requirements

- **FR-012**: System MUST support a docker compose development environment that emulates SaaS infrastructure (PostgreSQL 16, Redis 7, MinIO S3-compatible storage, MLflow tracking server) for local development.
- **FR-012a**: The docker compose stack MUST expose the anvil web service on host port `:8080` with the source tree volume-mounted so uvicorn `--reload` detects file changes without container rebuild.
- **FR-012b**: The docker compose stack MUST include a dev authentication setup so SaaS-mode routes (which require JWT auth in production) remain accessible during development. This MAY be a mock OIDC provider or a dev Cognito pool with known credentials.
- **FR-012c**: The docker compose stack MUST seed initial demo data (admin user, default organization, demo corpus) so the developer can start using the UI immediately without manual setup.
- **FR-012d**: Compute MUST run in-process (not dispatched to external Batch) in the dev stack. The in-process job queue and compute backend MUST write metrics to the local Redis and results to MinIO/PostgreSQL, exactly mirroring the SaaS data flow.
- **FR-013**: System MUST support three developer iteration modes: docker compose (fastest loop), local code against dev AWS (debugger access), and cdk deploy to dev environment (full integration).
- **FR-013a**: The `make compose-up` target MUST build the dev image and start the full compose stack, waiting for all services to report healthy.
- **FR-013b**: The `make compose-down` target MUST stop the compose stack while preserving data volumes. `make compose-reset` MUST stop and remove all volumes for a clean slate.

### Non-Goals (v1)

- **NG-1**: The dev stack does NOT run AWS Batch or simulate multi-node compute. Compute is always in-process.
- **NG-2**: The dev stack does NOT include CloudFront, WAF, or CDN emulation. MinIO is accessed directly, not through a CDN.
- **NG-3**: The dev stack auth setup is NOT a production-grade identity provider. It emulates enough of the auth flow for development and testing. The production auth path uses real Cognito.

## Service Contracts

### docker-compose.yml — Service Topology

| Service | Image | Port(s) | Purpose |
|---------|-------|---------|---------|
| `postgres` | `postgres:16-alpine` | `5432` | Application + MLflow databases |
| `redis` | `redis:7-alpine` | `6379` | SSE pub/sub delivery |
| `minio` | `minio/minio:latest` | `9000` (API), `9001` (console) | S3-compatible object storage |
| `mlflow` | `python:3.11-slim` | `5000` | MLflow tracking server (Postgres backend, MinIO artifacts) |
| `anvil-web` | `Dockerfile.dev` | `8080` | FastAPI with uvicorn `--reload`, volume-mounted source |

### Dockerfile.dev

A development-stage Dockerfile that:
- Extends `python:3.11-slim`
- Installs the project in editable mode with `[dev]` extras (including `uvicorn[standard]` for `--reload` support)
- Entrypoint: `uvicorn anvil._saas.app:app --reload --host 0.0.0.0 --port 8080`
- Volume-mounts `./anvil/` → `/app/anvil/` for hot-reload

### Dev Auth Contract

See `contracts/dev-auth.md` for the full contract. In summary:
- The dev auth setup MUST accept a known static API key (`ANVIL_DEV_API_KEY`) as a substitute for Cognito JWT validation
- All SaaS routes MUST be accessible with this key in the `Authorization` header
- The dev auth middleware MUST emulate the user identity (a known dev user with `is_cluster_admin=true`) so RBAC-scoped queries return unfiltered data
- The setup MUST be gated by `ANVIL_DEV_MODE=true` and MUST NOT activate in production SaaS mode

### Seed Data Script

`scripts/seed-dev-data.py` MUST:
1. Connect to the PostgreSQL instance using `DATABASE_URL`
2. Create the admin user (`dev@anvil.dev`) with `is_cluster_admin=true`
3. Create a default Organization ("Dev Org") and assign the admin as `owner`
4. Create a demo corpus from a small embedded text sample
5. Create a demo dataset with default chunking configuration
6. Print a success message with login credentials

## Architecture Cheatsheet

| Layer | Docker Compose | Dev AWS | Prod AWS |
|-------|---------------|---------|----------|
| **DB** | PostgreSQL (ctr) | RDS dev | RDS prod |
| **MLflow** | MLflow (ctr) | Dev ECS service | Prod ECS service |
| **Storage** | MinIO (ctr) | Dev S3 | Prod S3 |
| **SSE** | Redis (ctr) | Dev ElastiCache | Prod ElastiCache |
| **Compute** | In-process | Local (debug) | AWS Batch |
| **Auth** | Mock/API key | Dev Cognito pool | Prod Cognito pool |
| **CDN** | None | CloudFront | CloudFront |
| **Deploy** | `docker compose up` | `cdk deploy` | `anvil deploy` |

## Success Criteria

- **SC-004**: A developer can go from `git clone` to running the full SaaS stack locally (docker compose) in under 3 minutes.
- **SC-dev-1**: The compose stack starts all 5 services (postgres, redis, minio, mlflow, anvil-web) and all report healthy within 60 seconds.
- **SC-dev-2**: Editing a Python source file in the mounted volume is reflected in the running web service within 3 seconds (uvicorn `--reload` detection).
- **SC-dev-3**: Seed data is available on first boot — the developer can see the demo corpus in the UI without manual setup.
- **SC-dev-4**: Running `make compose-down && make compose-up` without `-v` preserves data across restarts.
- **SC-dev-5**: Running `make compose-reset` produces a clean state indistinguishable from the first boot.

## Key Entities

- **Dockerfile.dev**: Development-stage image with hot-reload support and editable install.
- **docker-compose.yml**: Service topology defining all 5 containers, their ports, volumes, dependencies, and health checks.
- **Dev auth middleware**: A lightweight JWT bypass that accepts a static API key when `ANVIL_DEV_MODE=true`.
- **Seed data script**: Python script that bootstraps an admin user, organization, and demo data.

## See Also

- [[029 SaaS Dev Stack - plan|plan]] — Phase 10 implementation plan
- [[029 SaaS Dev Stack - tasks|tasks]] — T089–T093 task breakdown
- [[029 SaaS Dev Stack - quickstart|quickstart]] — Developer quickstart for Mode 2
- [[029 SaaS Dev Stack - data-model|data-model]] — Dev stack seed data model notes
- [[Specs/016 SaaS Architecture/016 SaaS Architecture|016 SaaS Architecture]] — Superseded umbrella spec
- [[Reference/SaaSArchitectureDecisions|SaaS Architecture Decisions]] — AD-1 through AD-17