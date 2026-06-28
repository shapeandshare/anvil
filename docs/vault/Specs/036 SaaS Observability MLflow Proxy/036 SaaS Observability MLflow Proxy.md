---
title: 036 SaaS Observability MLflow Proxy
type: spec
tags:
  - type/spec
  - domain/operations
  - domain/mlops
  - domain/infrastructure
spec-refs:
  - docs/vault/Specs/036 SaaS Observability MLflow Proxy/
status: draft
created: '2026-06-27'
updated: '2026-06-27'
aliases:
  - 036 SaaS Observability MLflow Proxy
---

# 036 SaaS Observability & MLflow Proxy

## Summary

Production operability for the SaaS deployment. Three observability pillars (logs, traces, metrics) plus an authenticated MLflow reverse proxy — all SaaS-only optional extras.

- **Logs**: structured JSON logging (FR-052); `LogsReader` abstraction with `LocalLogsReader` (shared) and `CloudWatchLogsReader` (`_saas/`); compute-pod logs in-browser via `batch_log_stream` (FR-052b); cost-controlled log viewer (FR-052c) with graceful degradation without `[monitoring]` (FR-052d).
- **Traces**: OpenTelemetry auto-instrumentation → AWS X-Ray (FR-053); `traceparent` propagation into Batch pods (FR-053a) and across Redis SSE boundary (FR-053b); configurable sampling (FR-053c); traced SQLAlchemy/Redis spans (FR-053d).
- **Metrics**: Prometheus `/metrics` + custom metrics (FR-054/FR-054a); Prometheus ECS Fargate (1 vCPU/2GB, EFS-backed, FR-054b) + Grafana with CloudWatch data source (FR-054c); compute pod CloudWatch EMF (FR-054d); Alertmanager + default rules → SNS (FR-054e).
- **Package structure**: `[monitoring]`/`[monitoring-aws]`/`saas` extras (FR-055); local mode graceful degradation (FR-055a); `_saas/observability/` package (FR-055b); `batch_log_stream` column migration (FR-056).
- **MLflow proxy**: authenticated reverse proxy at `/v1/mlflow-proxy/` (FR-057); Cognito JWT + RBAC enforcement (FR-057a); `--static-prefix` for correct SPA URLs (FR-057b/FR-057g); CloudFront-aware `get_mlflow_browser_uri()` (FR-057c); long-lived streaming support (FR-057d); `ANVIL_MLFLOW_INTERNAL_URI` config (FR-057e); org-scoped experiment linking (FR-057f).

**Local-mode risk: MEDIUM** — two explicit guards: (1) FR-055a — `[monitoring]` extra locally enables console JSON logging only, mounts no `/metrics`, `LocalLogsReader` fallback; (2) ADR-035/FR-057c — local `get_mlflow_browser_uri` returns `/v1/mlflow-proxy` path (loopback upstream), a deliberate local behavior change governed by ADR-035 — existing ops/experiments/models pages must still resolve MLflow.

## Artifacts

- [[036 SaaS Observability MLflow Proxy - spec|spec]]
- [[036 SaaS Observability MLflow Proxy - plan|plan]]
- [[036 SaaS Observability MLflow Proxy - tasks|tasks]]
- [[036 SaaS Observability MLflow Proxy - research|research]]
- [[036 SaaS Observability MLflow Proxy - data-model|data-model]]
- [[036 SaaS Observability MLflow Proxy - quickstart|quickstart]]

## Parent

[[Specs/016 SaaS Architecture/016 SaaS Architecture|016 SaaS Architecture (superseded umbrella)]]

## Decisions

- [[Reference/SaaSArchitectureDecisions|SaaS Architecture Decisions]] (AD-12, AD-13)
- [[Decisions/ADR-035-mlflow-reverse-proxy|ADR-035]] — MLflow proxy (superseded by ADR-037)
- [[Decisions/ADR-037-unified-interface-local-tls|ADR-037]] — generic single-origin proxy registry

> **Proxy mechanism ownership (2026-06-28)**: The generic reverse-proxy mechanism
> (route, `httpx` streaming, registry, loopback bind, `--static-prefix`,
> `get_mlflow_browser_uri`) is OWNED by
> [[Specs/056 Reverse-Proxy Registry/056 Reverse-Proxy Registry|Spec 056 — Reverse-Proxy Registry]].
> Spec 036's MLflow-proxy requirements (FR-057a–g) and Phase 5 tasks now layer ONLY
> the **SaaS-specific** concerns on top of 056's deliverable: Cognito JWT + RBAC
> enforcement on the proxied route (FR-057a), `org_id` experiment tagging (FR-057f),
> the Cloud Map upstream address (FR-057e), and CloudFront-aware scheme derivation
> (FR-057c). The route/streaming/registry/`--static-prefix` themselves come from 056.

## References

- [[Specs/Specs|Specs]]