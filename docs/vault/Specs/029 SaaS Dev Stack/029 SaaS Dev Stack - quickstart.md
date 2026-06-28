---
title: 029 SaaS Dev Stack - quickstart
type: quickstart
tags:
  - type/spec
spec-refs:
  - docs/vault/Specs/029 SaaS Dev Stack/
related:
  - '[[029 SaaS Dev Stack]]'
created: '2026-06-27'
updated: '2026-06-27'
---

# Quickstart: SaaS Dev Stack — Docker Compose Local SaaS Emulation

## Prerequisites

- Docker Desktop (macOS) or Docker Engine (Linux)
- `make` + `bash`
- Python 3.11+ (for the seed data script)
- Git clone of the anvil repository

---

## Mode 2: SaaS Developer — Docker Compose

This is the fastest iteration loop for SaaS feature development. All infrastructure services run in containers — no AWS account needed.

### Start the Stack

```bash
make compose-up
```

This will:
1. Build the dev Docker image from `Dockerfile.dev`
2. Start all 5 services
3. Wait for all health checks to pass
4. Run the seed data script (admin user, org, demo corpus)

### Services

| Service | Internal URL | Host Port | Purpose |
|---------|-------------|-----------|---------|
| **postgres** | `postgres:5432` | `5432` | `anvil_app` + `anvil_mlflow` databases |
| **redis** | `redis:6379` | `6379` | SSE pub/sub delivery |
| **minio** | `minio:9000` | `9000` | S3-compatible API (`anvil-data-dev`, `anvil-ml-dev` buckets) |
| **mlflow** | `mlflow:5000` | `5000` | MLflow tracking server (Postgres backend, MinIO artifacts) |
| **anvil-web** | — | `8080` | FastAPI with hot-reload (code mounted from `./anvil/`) |

### Access

- **Web UI**: http://localhost:8080
- **MinIO Console**: http://localhost:9001 (minioadmin / minioadmin)

### Hot Reload

Edit any Python source file in `./anvil/` — uvicorn detects the change and reloads within 3 seconds. No container rebuild needed.

### Authentication

In dev mode, authentication uses a static API key instead of Cognito:

```bash
# All API calls use this header:
Authorization: Bearer anvil-dev-key-change-me

# Set via env var (Docker Compose sets ANVIL_DEV_MODE=true automatically)
ANVIL_DEV_API_KEY=anvil-dev-key-change-me
```

The dev auth resolves all requests to a single identity:
- Email: `dev@anvil.dev`
- Role: cluster admin (`is_cluster_admin=true`)

### Seed Data

On first start, the seed data script creates:
| Entity | Details |
|--------|---------|
| Admin user | `dev@anvil.dev`, cluster admin |
| Organization | `Dev Org` |
| Membership | Admin as `owner` of Dev Org |
| Demo corpus | Pre-loaded text sample |
| Demo dataset | Default chunking config |

### Environment Variables

The `anvil-web` container receives these env vars automatically from `docker-compose.yml`:

```bash
ANVIL_MODE=saas
ANVIL_DEV_MODE=true
DATABASE_URL=postgresql+asyncpg://anvil:anvil_dev@postgres:5432/anvil_app
REDIS_URL=redis://redis:6379/0
S3_ENDPOINT=http://minio:9000
S3_DATA_BUCKET=anvil-data-dev
S3_ACCESS_KEY=minioadmin
S3_SECRET_KEY=minioadmin
MLFLOW_TRACKING_URI=http://mlflow:5000
SSE_TOKEN_SIGNING_SECRET=dev-secret-not-for-prod
ANVIL_DEV_API_KEY=anvil-dev-key-change-me
```

---

## Commands

```bash
make compose-up      # Build + start + seed data
make compose-down    # Stop (preserves data volumes)
make compose-reset   # Stop + remove all volumes (clean slate)

# Manual control
docker compose logs -f anvil-web   # Tail web service logs
docker compose ps                  # Service status
docker compose exec postgres psql -U anvil -d anvil_app  # DB shell
```

---

## Troubleshooting

| Problem | Cause | Fix |
|---------|-------|-----|
| Port 8080 in use | Another process on :8080 | Stop the other process, or change the host port mapping in `docker-compose.yml` |
| Hot-reload not working | uvloop installed | Ensure `uvicorn[standard]` excludes uvloop. Check logs for "reload is incompatible with uvloop" |
| Anvil-web crashes on startup | PostgreSQL not ready | Compose waits for health checks before starting anvil-web. Check logs: `docker compose logs anvil-web` |
| Seed data already exists | Re-running after restart | Idempotent — safe to run multiple times. No duplicate entities created |
| Reset needed | Corrupted data or schema migration | `make compose-reset` removes all volumes for a clean slate |

---

## See Also

- [[029 SaaS Dev Stack - spec|spec]] — Feature specification
- [[029 SaaS Dev Stack - plan|plan]] — Implementation plan
- [[Specs/016 SaaS Architecture/016 SaaS Architecture - quickstart|016 Quickstart (superseded)]] — Original quickstart with Mode 2 section