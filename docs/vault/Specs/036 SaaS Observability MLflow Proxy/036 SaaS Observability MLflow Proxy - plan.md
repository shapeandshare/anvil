---
title: 036 SaaS Observability MLflow Proxy - plan
type: plan
tags:
  - type/spec
spec-refs:
  - docs/vault/Specs/036 SaaS Observability MLflow Proxy/
related:
  - '[[036 SaaS Observability MLflow Proxy]]'
created: '2026-06-27'
updated: '2026-06-27'
status: draft
---

# Implementation Plan: SaaS Observability & MLflow Proxy

**Branch**: `036-saas-observability-mlflow-proxy` | **Date**: 2026-06-27
**Parent spec**: [[036 SaaS Observability MLflow Proxy - spec|spec]]
**Plan phase**: 12 (Gate G9) from [[Specs/016 SaaS Architecture/016 SaaS Architecture - plan|016 SaaS Architecture - plan]]

## Summary

Add production observability and an authenticated MLflow reverse proxy to the SaaS deployment. Three observability pillars (structured JSON logging, OpenTelemetry → X-Ray distributed tracing, Prometheus metrics + Grafana dashboards) deployable via optional `[monitoring]`/`[monitoring-aws]` extras. The MLflow proxy at `/v1/mlflow-proxy/` unifies local and SaaS access behind an authenticated reverse proxy (ADR-035). All features are SaaS-only optional extras; local mode degrades gracefully with zero cloud dependencies.

## High-Level Architecture

### Observability Stack

```mermaid
graph TB
    subgraph "Logs"
        WEB_LOG[anvil-web<br/>JSON stdout] --> CW[/CloudWatch Logs/]
        POD_LOG[Batch Compute Pod<br/>JSON stdout] --> CW
        MLF_LOG[MLflow ECS<br/>JSON stdout] --> CW
        WEB_LOG -.-> LCL[LocalLogsReader<br/>disk files]
        CW -.-> CWLR[CloudWatchLogsReader<br/>boto3 filter-log-events]
    end

    subgraph "Traces"
        OTel[OTel SDK auto-instrumentation] --> XR[/AWS X-Ray/]
        OTel -.-> TRACE_PROPA[traceparent propagation]
        TRACE_PROPA --> BATCH_POD[Batch Pod<br/>child spans]
        TRACE_PROPA --> REDIS_SSE[Redis pub/sub<br/>manual envelope]
    end

    subgraph "Metrics"
        PROM[/metrics endpoint<br/>prometheus-fastapi-instrumentator/] --> P_SCRAPE[Prometheus ECS<br/>1vCPU/2GB, EFS]
        P_SCRAPE --> GRAFANA[Grafana<br/>Prometheus + CW data sources]
        POD_EMF[Compute Pod<br/>CloudWatch EMF] --> CW
        P_SCRAPE --> ALERT[Alertmanager<br/>default rules → SNS]
    end

    subgraph "MLflow Proxy"
        BROWSER[Browser] --> PROXY[/v1/mlflow-proxy/{path}<br/>httpx.AsyncClient/]
        PROXY --> AUTH[Cognito JWT + RBAC]
        PROXY --> MLF_UPSTREAM[MLflow ECS<br/>mlflow.svc.local:5000]
        MLF_UPSTREAM --> SPA[--static-prefix=/v1/mlflow-proxy]
    end
```

### Mode Selection

| Capability | Local (no extras) | Local + `[monitoring]` | SaaS + `[monitoring-aws]` |
|------------|-------------------|----------------------|--------------------------|
| **Log format** | Existing file format | Console JSON (no AWS) | Console JSON + CloudWatch |
| **Log viewer** | LocalLogsReader (disk) | LocalLogsReader (disk) | CloudWatchLogsReader |
| **Tracing** | Disabled | Console exporter only | OTel → X-Ray |
| **/metrics** | Not mounted | Not mounted | Prometheus instrumentator |
| **Custom metrics** | None | None | Application metrics |
| **MLflow access** | Loopback via proxy | Loopback via proxy | Cloud Map via proxy |

## Source Code Structure

### New Files

```text
# Observability package (SaaS-only, requires [monitoring] extra)
anvil/_saas/observability/
├── __init__.py                # Package docstring
├── logging.py                 # JsonFormatter, setup_logging()
├── tracing.py                 # setup_tracing(), TRACEPARENT propagation helpers
└── metrics.py                 # Prometheus custom metric definitions

# Shared abstraction interface (no cloud deps)
anvil/storage/logs.py          # LogsReader abstract interface + LocalLogsReader

# SaaS implementation (requires boto3)
anvil/_saas/implementations/
└── cw_logs_reader.py          # CloudWatchLogsReader

# MLflow proxy
anvil/api/v1/mlflow_proxy.py   # /v1/mlflow-proxy/{path:path} reverse proxy route
```

### Modified Files

```text
# Schema
anvil/db/models/training_job.py    # +batch_log_stream column
anvil/_resources/migrations/       # +batch_log_stream migration

# Configuration
anvil/config.py                    # get_mlflow_browser_uri() revised per ADR-035

# App factory
anvil/_saas/app.py                 # Wire observability on [monitoring]-extra presence

# Supervisor
anvil/supervisor/services.py       # MLflowService.start() adds --static-prefix

# Ops page templates / views
anvil/api/v1/services.py           # Log viewer endpoint (LogsReader)
anvil/api/v1/training.py           # +GET /v1/training/{job_id}/logs

# CDK infrastructure
packages/infra/lib/
├── ecs-services.ts                # +Prometheus Fargate task
├── ecs-services.ts                # +Grafana Fargate task
├── ecs-services.ts                # +Alertmanager Fargate task
├── storage.ts                     # +EFS filesystem for Prometheus TSDB
└── monitoring.ts                  # NEW — monitoring construct grouping

# pyproject.toml
pyproject.toml                     # +[monitoring], [monitoring-aws] extras
```

## Phasing

### Phase 1 — Package Setup & Shared Abstractions

- Create `anvil/_saas/observability/` package with bare `__init__.py`
- Define `LogsReader` ABC + `LocalLogsReader` at `anvil/storage/logs.py`
- Add `[monitoring]` / `[monitoring-aws]` / `saas` extras to `pyproject.toml`
- Define `CloudWatchLogsReader` at `anvil/_saas/implementations/cw_logs_reader.py`
- Add `batch_log_stream` column to `TrainingJob` model + Alembic migration

**Gate**: `LogsReader` ABC mypy-clean; extras resolve; migration applies; `brew-style pip install anvil` installs zero OTel/Prometheus.

### Phase 2 — Structured JSON Logging

- Implement `JsonFormatter` + `setup_logging()` in `anvil/_saas/observability/logging.py`
- Wire structured logging in SaaS app factory
- SaaS ops page log viewer: use `LogsReader` (CW in SaaS, disk locally)
- Implement cost control: no auto-refresh in SaaS mode (FR-052c), "Refresh" button only
- Implement graceful degradation: null reader when `[monitoring]` absent (FR-052d)
- Compute pod log endpoint: `GET /v1/training/{job_id}/logs?lines=N` (FR-052b)

**Gate**: SaaS log viewer fetches from CloudWatch; local ops page reads from disk unchanged; "monitoring not configured" response without the extra.

### Phase 3 — Distributed Tracing (OTel → X-Ray)

- Implement `setup_tracing()` in `anvil/_saas/observability/tracing.py`
- Wire OTel auto-instrumentation (FastAPI, Redis, boto3, httpx) in SaaS factory
- Implement `traceparent` propagation into Batch compute pods (FR-053a)
- Implement manual Redis pub/sub trace context propagation (FR-053b)
- Configure sampling: head-based for web (reservoir+rate), every 10th step for pods (FR-053c)
- Wrap SQLAlchemy connection pools and Redis operations in traced spans (FR-053d)

**Gate**: X-Ray trace map shows full browser → web → Redis → Batch pod → DB/S3/MLflow path; sampling limits cost.

### Phase 4 — Prometheus Metrics & Dashboards

- Wire Prometheus `/metrics` endpoint via `prometheus-fastapi-instrumentator` in SaaS factory
- Define custom metrics in `anvil/_saas/observability/metrics.py` (FR-054a)
- CDK: Prometheus ECS Fargate task (1 vCPU/2GB, EFS-backed, ecs_sd rate-limited) (FR-054b)
- CDK: Grafana ECS Fargate task with Prometheus + CloudWatch data sources (FR-054c)
- Implement compute pod CloudWatch EMF metrics output (FR-054d)
- CDK: Alertmanager ECS Fargate task + default rules + SNS routing (FR-054e)

**Gate**: `/metrics` returns RED + custom metrics; Grafana dashboard shows job lifecycle; Alertmanager rules loaded.

### Phase 5 — MLflow Reverse Proxy

- Implement `/v1/mlflow-proxy/{path:path}` route with `httpx.AsyncClient`
- Enforce Cognito JWT + RBAC on proxy route (FR-057a)
- Launch MLflow with `--static-prefix=/v1/mlflow-proxy` (FR-057g)
- Serve MLflow SPA with correct prefixed AJAX/static URLs (FR-057b)
- Revise `get_mlflow_browser_uri(request)` to return proxy URL (FR-057c, ADR-035)
- Support long-lived streaming for artifact downloads (FR-057d)
- Wire `ANVIL_MLFLOW_INTERNAL_URI` env var with fail-fast default (FR-057e)
- Tag MLflow experiments with `org_id` at creation (FR-057f)
- Playwright integration test: MLflow experiments list loads through proxy (FR-057g)

**Gate**: MLflow UI loads through `/v1/mlflow-proxy/`; AJAX calls succeed; unauthenticated requests return 401; Playwright check passes.

### Phase 6 — Validation & Local-Mode Regression

- Full LMRG: base install zero OTel/Prometheus; `[monitoring]` locally is console-only
- Local MLflow reachable via proxy (ADR-035)
- `make test`, `make lint`, `make typecheck` pass
- Import-isolation assertion: no SaaS imports leak into local entrypoint

## Complexity Tracking

| Item | Justification |
|------|---------------|
| Observability dependencies (`opentelemetry-*`, `prometheus-*`, `aws-opentelemetry-distro`) | Optional `[monitoring]` / `[monitoring-aws]` extras only; never installed in base or `[aws]`. Local mode gracefully degrades (console exporter, no /metrics). |
| Prometheus + Grafana + Alertmanager ECS tasks | New ECS tasks. Prometheus 1 vCPU/2GB with EFS-backed TSDB (persistent across restarts) and rate-limited ecs_sd_configs; Grafana with Prometheus + CloudWatch data sources; Alertmanager with default rules → SNS. First-class CDK constructs. |
| MLflow proxy with `--static-prefix` | Single FastAPI route; no new process or deployment archetype. `httpx` already in the dependency tree. The `--static-prefix` flag is an MLflow-supported launch parameter. |

## Dependency Changes

### New optional extras (pyproject.toml)

```toml
[project.optional-dependencies]
monitoring = [
    "opentelemetry-distro[otlp]>=0.50",
    "opentelemetry-instrumentation-fastapi>=0.50",
    "opentelemetry-instrumentation-redis>=0.50",
    "opentelemetry-instrumentation-boto3>=0.50",
    "opentelemetry-instrumentation-httpx>=0.50",
    "prometheus-fastapi-instrumentator>=7.0",
    "prometheus-client>=0.21",
]
monitoring-aws = [
    "anvil[monitoring]",
    "aws-opentelemetry-distro>=1.0",
]
# Composite extra for a full SaaS deployment — install this on ECS/Batch images.
saas = [
    "anvil[aws]",
    "anvil[monitoring-aws]",
]
```

**Extra selection by audience:**

| Audience | Install | Gets |
|----------|---------|------|
| Local user | `pip install anvil` | Core only, zero cloud/monitoring deps |
| Local user wanting JSON logs | `pip install anvil[monitoring]` | OTel/Prometheus libs, console exporter, no AWS |
| Operator deploying (CLI only) | `pip install anvil[aws]` | boto3/redis/jwt for deploy, no monitoring |
| **SaaS runtime (ECS/Batch image)** | `pip install anvil[saas]` | Everything: aws + monitoring-aws |