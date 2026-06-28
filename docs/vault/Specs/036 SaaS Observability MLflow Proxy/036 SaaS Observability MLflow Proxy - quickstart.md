---
title: 036 SaaS Observability MLflow Proxy - quickstart
type: quickstart
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

# Quickstart: SaaS Observability & MLflow Proxy

## Prerequisites

- Feature 032 (Durable Training Pipeline) — `TrainingJob` model with `batch_job_id`
- Feature 029 (SaaS Authentication & RBAC) — JWT middleware, RBAC guard
- Python 3.11+ with `anvil[saas]` extra (includes `[monitoring-aws]`)
- For local dev: `pip install anvil[monitoring]` for console JSON logging

---

## Mode 1: Local User (No Extras — Unchanged)

```bash
pip install anvil
anvil serve
# → http://localhost:8080
# No OTel, no Prometheus, no /metrics, no CloudWatch.
# Logs: existing file format. Log viewer: disk files.
# MLflow: accessed through /v1/mlflow-proxy/ (loopback, unchanged from ADR-035).
```

---

## Mode 2: Local User with JSON Logging

```bash
pip install anvil[monitoring]
ANVIL_MODE=local anvil serve
# → http://localhost:8080
# Console JSON logging enabled (stdout).
# /metrics NOT mounted (returns 404).
# setup_tracing() defaults to console exporter or no-op.
# LogsReader resolves to LocalLogsReader (disk files).
# No AWS service contacted.
```

---

## Mode 3: SaaS Deploy with Full Observability

```bash
# The ECS/Batch image installs the [saas] extra:
pip install anvil[saas]

# Deploy the stack (includes monitoring CDK constructs):
anvil deploy init

# After deploy:
#   Log viewer: CloudWatch Logs (user-triggered refresh)
#   Tracing: OTel → X-Ray (sampled at 5%)
#   Metrics: Prometheus /metrics → Grafana dashboard
#   Alerts: Alertmanager → SNS topic
#   MLflow: accessed through /v1/mlflow-proxy/ (private subnet)
```

---

## Key Endpoints

| Endpoint | Mode | Description |
|----------|------|-------------|
| `GET /metrics` | SaaS only | Prometheus metrics (RED + custom) |
| `GET /v1/services/logs/{name}?lines=N` | Both | Service log viewer (CW in SaaS, disk in local) |
| `GET /v1/training/{job_id}/logs?lines=N` | Both | Compute pod logs (CW in SaaS, disk in local) |
| `GET /v1/mlflow-proxy/{path:path}` | Both | MLflow reverse proxy (auth-gated) |

---

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `ANVIL_MLFLOW_INTERNAL_URI` | `http://127.0.0.1:5001` (local) / `http://mlflow.svc.local:5000` (SaaS) | MLflow upstream target for the proxy |
| `OTEL_TRACES_SAMPLER` | `traceidratio` | OTel sampling strategy |
| `OTEL_TRACES_SAMPLER_ARG` | `0.05` (web) / `0.1` (compute, every 10th step) | Sampling ratio |
| `OTEL_TRACES_EXPORTER` | `otlp` (SaaS) / `console` (local) | Trace exporter backend |
| `ANVIL_DEPLOY_ALERT_TARGET` | *(none)* | SNS topic ARN or webhook URL for Alertmanager routing |

---

## Checking Observability Health

```bash
# Verify /metrics endpoint (SaaS)
curl http://localhost:8080/metrics | head -20

# Verify MLflow proxy (authenticated)
curl -H "Authorization: Bearer $JWT" http://localhost:8080/v1/mlflow-proxy/ | head -5

# Verify log viewer (SaaS with monitoring)
curl http://localhost:8080/v1/services/logs/anvil-web?lines=10

# Verify compute pod logs
curl http://localhost:8080/v1/training/42/logs?lines=50
```