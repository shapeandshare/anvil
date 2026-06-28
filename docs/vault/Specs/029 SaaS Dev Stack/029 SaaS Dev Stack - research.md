---
title: 029 SaaS Dev Stack - research
type: research
tags:
  - type/spec
spec-refs:
  - docs/vault/Specs/029 SaaS Dev Stack/
related:
  - '[[029 SaaS Dev Stack]]'
created: '2026-06-27'
updated: '2026-06-27'
---

# Research: SaaS Dev Stack — Docker Compose Local SaaS Emulation

**Phase 0 output** — resolves architectural and implementation unknowns for the SaaS dev stack.

## 1. Docker Compose Service Selection

### Decision

Use standard Docker images for infrastructure services: `postgres:16-alpine` for database, `redis:7-alpine` for pub/sub, `minio/minio:latest` for S3-compatible storage, and a custom `Dockerfile.dev` for the anvil-web service. MLflow runs as a separate container using the `python:3.11-slim` base with `mlflow` installed.

### Rationale

- All services are mature, well-known images with Alpine variants for slim footprint
- MinIO is the de facto standard S3 emulator — uses the exact same `boto3` API as AWS S3
- PostgreSQL 16 matches the target RDS version for production parity
- Redis 7 matches the target ElastiCache version
- No need for a separate image for MLflow — it installs via pip and connects to the same Postgres and MinIO

### Key Findings

| Service | Image | Alternative Considered | Why Chosen |
|---------|-------|----------------------|------------|
| PostgreSQL | `postgres:16-alpine` | `postgres:17`, SQLite | 16 matches target RDS; Alpine for small size |
| Redis | `redis:7-alpine` | `redis:6`, `valkey` | 7 matches target ElastiCache; valkey is less known |
| MinIO | `minio/minio:latest` | `localstack` (S3 only), `fake-s3` | MinIO is the standard; full S3 API compat |
| MLflow | Custom `python:3.11-slim` + pip | Bundled in anvil-web container | Separate container mirrors production topology |

---

## 2. uvicorn --reload Compatibility

### Decision

Use `uvicorn[standard]` (which includes watchfiles) for hot-reload support. Explicitly exclude `uvloop` (which is incompatible with `--reload`).

### Rationale

- `uvicorn --reload` requires `watchfiles` (or `auto` which defaults to polling)
- `uvicorn[standard]` includes watchfiles
- `uvloop` is incompatible with `--reload` (raises `RuntimeError: reload is incompatible with uvloop`)
- The `[dev]` extras set must NOT include `uvloop`, or if it does, the Dockerfile.dev must pin `uvicorn[standard]` without uvloop

### Findings

| Aspect | Conclusion |
|--------|-----------|
| Reload mechanism | `watchfiles` via uvicorn `--reload` (auto-detect file changes in mounted volume) |
| uvloop exclusion | Must explicitly exclude uvloop or use `UVICORN_RELOAD=true` env var which auto-disables uvloop |
| Volume mount | Source code at `./anvil/` → `/app/anvil/` within container |
| Detection latency | < 3 seconds (watchfiles uses inotify/kqueue, polling not needed for mounted volumes on macOS) |

---

## 3. Dev Auth Strategy

### Decision

A lightweight middleware gated on `ANVIL_DEV_MODE=true` that accepts a static API key (`ANVIL_DEV_API_KEY`) as a substitute for Cognito JWT validation. When active, it resolves the caller to a known dev user with `is_cluster_admin=true`.

### Rationale

- Running a real Cognito User Pool requires an AWS account and internet access
- Mock OIDC providers (e.g., `dex`, `hydra`) add another container and configuration surface
- A simple API key bypass is the minimum needed to unblock SaaS route development
- The guard (`ANVIL_DEV_MODE=true`) ensures this never activates in production

### Alternatives Considered

- **Real Cognito dev pool**: Most production-like but requires AWS account, internet, and longer startup. Rejected for the dev stack.
- **Dex (OIDC provider)**: Standards-compliant but adds complexity (another container, TLS config, client registration). Overkill for dev scenarios.
- **No auth at all**: Simpler but would mask auth-related routing issues. The chosen approach (API key) still exercises the `Authorization` header path.

### Findings

| Aspect | Decision |
|--------|----------|
| Auth mechanism | Static API key in `Authorization: Bearer <key>` header |
| Guard env var | `ANVIL_DEV_MODE=true` |
| Dev identity | `sub=dev-user-0000`, email=`dev@anvil.dev`, `is_cluster_admin=true` |
| Middleware location | `anvil/_saas/auth/dev_setup.py` |
| Integration | Replaces Cognito JWT middleware in the dev app factory when `ANVIL_DEV_MODE=true` |

---

## 4. Seed Data Strategy

### Decision

A standalone Python script (`scripts/seed-dev-data.py`) that connects to PostgreSQL and creates the admin user, default organization, membership, and demo corpus. Idempotent — safe to run on every compose start.

### Rationale

- A "fresh stack" with no data is useless — developer must create everything manually
- Idempotent script can run as an init container or post-start step
- Python over bash (per AGENTS.md): testable, type-checkable

### Findings

| Entity | Seed Value |
|--------|-----------|
| Admin user | email: `dev@anvil.dev`, cognito_sub: `dev-user-0000`, is_cluster_admin: `true` |
| Organization | name: `Dev Org`, slug: `dev-org` |
| Membership | admin → Dev Org, role: `owner` |
| Demo corpus | A small excerpt (~500 chars) embedded in the script |
| Demo dataset | Default chunking strategy (LINE) referencing the demo corpus |

### Alternatives Considered

- **SQL dump file**: Fast but fragile (schema changes break the dump). Rejected.
- **ORM migration seed**: Couples seed to ORM internals. Rejected for a standalone script.
- **Shell script**: AGENTS.md mandates Python over bash for new scripts. Rejected.

---

## 5. Makefile Targets

### Decision

Add three targets: `make compose-up`, `make compose-down`, `make compose-reset`. These wrap `docker compose` commands with health-wait logic and seed-data execution.

### Findings

| Target | Command |
|--------|---------|
| `compose-up` | `docker compose build && docker compose up -d --wait && python scripts/seed-dev-data.py` |
| `compose-down` | `docker compose down` (preserves volumes) |
| `compose-reset` | `docker compose down -v` (removes all volumes) |

---

## Summary

| Area | Decision | Impact |
|------|----------|--------|
| PostgreSQL image | `postgres:16-alpine` | Matches target RDS version |
| Redis image | `redis:7-alpine` | Matches target ElastiCache version |
| S3 emulation | MinIO | Full S3 API compat; uses same boto3 client |
| MLflow | Custom container from `python:3.11-slim` | Separate from anvil-web, mirrors prod topology |
| Hot-reload | `uvicorn[standard]` with `--reload`, no uvloop | < 3s reload detection |
| Dev auth | Static API key middleware gated on `ANVIL_DEV_MODE` | Simple, no external dependencies |
| Seed data | Idempotent Python script | Bootstraps dev environment on first start |
| Make targets | `compose-up`, `compose-down`, `compose-reset` | Fast, standard interface |