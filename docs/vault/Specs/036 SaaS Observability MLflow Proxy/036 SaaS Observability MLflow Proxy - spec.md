---
title: 036 SaaS Observability MLflow Proxy - spec
type: spec
tags:
  - type/spec
  - domain/operations
  - domain/mlops
  - domain/infrastructure
spec-refs:
  - docs/vault/Specs/036 SaaS Observability MLflow Proxy/
related:
  - '[[036 SaaS Observability MLflow Proxy]]'
created: '2026-06-27'
updated: '2026-06-27'
status: draft
---

# Feature Specification: SaaS Observability & MLflow Proxy

**Feature Branch**: `036-saas-observability-mlflow-proxy`
**Created**: 2026-06-27
**Status**: Draft
**Parent spec**: [[Specs/016 SaaS Architecture/016 SaaS Architecture - spec|016 SaaS Architecture (superseded umbrella)]]
**Plan phase**: 12 (Gate G9) — extracted from the umbrella 016 spec

## Requirements

All requirements are lifted verbatim from the umbrella spec [[Specs/016 SaaS Architecture/016 SaaS Architecture - spec|016 SaaS Architecture - spec]]. Only FR-052 through FR-057 and their sub-requirements are in scope for this feature.

### Functional Requirements

#### Observability — Structured Logging

- **FR-052**: All SaaS services (anvil-web, MLflow, compute worker) MUST emit JSON-structured logs to stdout with fields: `timestamp`, `level`, `service`, `message`, `trace_id`, `org_id`, `job_id` (where applicable). The local mode log-file format MUST remain unchanged. Structured logging is configured by the SaaS factory at startup and MUST NOT affect local mode.
- **FR-052a**: The anvil-web service MUST expose `GET /v1/services/logs/{name}?lines=N` (SaaS mode) that reads from CloudWatch Logs via `boto3 logs filter-log-events` for ECS service log groups (`/ecs/anvil-web`, `/ecs/anvil-mlflow`). The existing local-mode endpoint (reads disk files) MUST continue to work unchanged. This follows the same abstraction-interface pattern as FileStore/EventBus/JobQueue: a `LogsReader` interface with `LocalLogsReader` and `CloudWatchLogsReader` implementations.
- **FR-052b**: The system MUST expose `GET /v1/training/{job_id}/logs?lines=N` to surface compute pod logs post-hoc. The `batch_log_stream` name (predictable from `{batch_job_id}/default` per AWS Batch log stream naming) MUST be stored on the `training_jobs` row at job submission time so the API can query CloudWatch Logs for the terminated pod's log stream.
- **FR-052c — Log viewer cost control**: In SaaS mode the operations page MUST NOT auto-refresh logs on a timer. The local-mode ops page auto-refreshes every 10s from cheap local files; in SaaS mode this would hammer the CloudWatch `FilterLogEvents` API (billed per request, throttled at 5 TPS/account/region). The SaaS log viewer MUST refresh only on explicit user action (a "Refresh" button), and SHOULD cache the last result for a short TTL. System-resource polling (CPU/mem) may continue, but log fetches are user-triggered only. (FR-052c)
- **FR-052d — Log viewer graceful degradation**: If the `[monitoring]` extra is not installed (no `CloudWatchLogsReader` available) in SaaS mode, the log viewer endpoints MUST return a structured "monitoring not configured" response (HTTP 200 with an explanatory payload), NOT a 500 from a failed import. The ops page MUST render a clear "Log viewer requires the monitoring extra" message. The `LogsReader` resolution MUST degrade to a null reader rather than crash. (FR-052d)

#### Observability — Distributed Tracing

- **FR-053**: The SaaS system MUST use OpenTelemetry SDK with auto-instrumentation for distributed tracing across all service boundaries. Traces MUST be exported to AWS X-Ray via the AWS Distro for OpenTelemetry (ADOT) or the OTLP exporter. The following auto-instrumentation packages cover the majority of the stack: `opentelemetry-instrumentation-fastapi`, `opentelemetry-instrumentation-redis`, `opentelemetry-instrumentation-boto3`, `opentelemetry-instrumentation-httpx`.
- **FR-053a**: Trace context MUST propagate from the web service into ephemeral Batch compute pods. When submitting a Batch job, the web service MUST extract the W3C `traceparent` header from the current span context and pass it as a `TRACEPARENT` environment variable in the Batch container overrides. The compute worker MUST extract this on startup and continue the trace, creating a child span for the training run. (FR-053a)
- **FR-053b**: The SSE metrics path (compute pod → Redis pub/sub → web pod → browser) MUST propagate trace context manually through the Redis message payload. The compute pod MUST inject its current `traceparent` as an envelope field in each published Redis message; the web pod subscriber MUST extract it and continue the trace when forwarding to the browser `EventSource`. This manual propagation is required because auto-instrumentation cannot connect traces across the Redis pub/sub boundary. (FR-053b)
- **FR-053c**: Sampling MUST be configured to manage X-Ray cost in the multi-tenant setting. The web service MUST use head-based sampling (e.g., reservoir + rate: first request/second then 5%). The compute pod MUST sample training step spans (not every step, e.g., every 10th step via a configurable `OTEL_TRACES_SAMPLER` / `OTEL_TRACES_SAMPLER_ARG`). Trace context MUST still be propagated even for non-sampled spans to preserve the trace tree shape. (FR-053c)
- **FR-053d**: Long-lived SQLAlchemy connection pools and Redis pub/sub operations in the web tier MUST be wrapped in traced spans so DB query latency and Redis publish latency appear in the X-Ray trace map.

#### Observability — Prometheus Metrics

- **FR-054**: The SaaS app factory MUST mount a `GET /metrics` endpoint on the anvil-web service via `prometheus-fastapi-instrumentator`, exposing at minimum: HTTP request rate, request duration histogram (p50/p95/p99) by method/path/status, error rate, and in-flight request count. (FR-054)
- **FR-054a**: Custom Prometheus metrics MUST be defined for application-level observability, including:
  - `anvil_jobs_submitted_total{compute_shape, org_id}` — counter
  - `anvil_jobs_completed_total{compute_shape, org_id}` — counter
  - `anvil_jobs_failed_total{compute_shape, org_id, reason}` — counter
  - `anvil_sse_publish_latency_seconds` — histogram (subscribe-to-browser latency)
  - `anvil_concurrent_jobs{org_id}` — gauge (current running count)
  - `anvil_org_quota_remaining{org_id}` — gauge (remaining concurrent job quota)
  - `anvil_training_steps_total{org_id, compute_shape}` — counter
  - Labels MUST be kept low-cardinality: `org_id` on gauges and high-level counters only. Step-level counters use `compute_shape` without per-org labels to avoid cardinality explosion.
- **FR-054b**: A Prometheus server MUST be deployed as an ECS Fargate task with `ecs_sd_configs` to discover anvil-web ECS tasks for scraping. Sizing and durability requirements:
  - **Sizing**: default 1 vCPU / 2 GB (NOT 0.25 vCPU / 512 MB — that is insufficient for `ecs_sd_configs` plus TSDB). Sizing MUST be configurable via the deploy `instance_size` setting.
  - **Scrape interval**: 30 seconds (not 15s) to reduce ECS API pressure and TSDB churn.
  - **Persistent storage**: the Prometheus TSDB MUST be backed by an **EFS volume** mounted into the Fargate task, NOT ephemeral task storage. A task restart MUST NOT lose historical metrics. The EFS filesystem is a first-class CDK construct.
  - **ECS API rate limiting**: `ecs_sd_configs` calls `ListTasks` + `DescribeTasks` per scrape. The Prometheus service discovery MUST be configured with a refresh interval (≥60s, decoupled from scrape interval) and retry/backoff so it does not exceed the ECS API rate limit (40 TPS/account) as task count grows. The Prometheus task role grants only `ecs:ListTasks` and `ecs:DescribeTasks`.
  (FR-054b)
- **FR-054c**: A Grafana dashboard MUST be deployed (as an ECS Fargate task or via Grafana Cloud) to visualize the default and custom Prometheus metrics. The dashboard MUST include at minimum: request rate/error/duration (RED method), job lifecycle overview (submitted/running/completed/failed), SSE latency heatmap, concurrent jobs per org, and system health summary. Grafana MUST use a CloudWatch data source (in addition to Prometheus) so compute-pod EMF metrics appear alongside web metrics. (FR-054c)
- **FR-054d**: Batch compute pods (ephemeral, minutes-to-hours lifetime) MUST NOT expose a Prometheus `/metrics` endpoint — the scrape interval cannot reliably capture them. Instead, compute pods MUST emit custom metrics via CloudWatch Embedded Metric Format (EMF): a single structured JSON log line to stdout creates auto-extracted CloudWatch custom metrics (`TrainingSteps`, `JobDuration`) with dimensions `org_id` and `compute_shape`. These CW metrics are surfaced in Grafana via the CloudWatch data source (FR-054c). (FR-054d)
- **FR-054e — Alerting**: A Prometheus Alertmanager MUST be deployed as an ECS Fargate task (1 replica) with a default alert ruleset and routing to an SNS topic (email/webhook configurable at deploy). Default alert rules MUST include at minimum:
  - Job stuck in `pending` > 5 minutes (scheduler/quota problem)
  - SSE publish latency p95 > 1s (SC-002 breach)
  - ECS service `runningCount < desiredCount` for > 2 minutes (capacity/health)
  - Batch job queue depth > configurable threshold (backlog)
  - RDS connection failures / free storage < 10%
  - Reconciler not running (dead-man's switch: no reconciler heartbeat in N minutes)
  Alert routing target (SNS topic ARN or webhook URL) is set via `anvil deploy config set alert-target`. (FR-054e)

#### Observability — Package Structure & Mode Selection

- **FR-055**: All observability dependencies (`opentelemetry-*`, `prometheus-*`, `aws-opentelemetry-distro`) MUST be declared as an optional `[monitoring]` extra in `pyproject.toml`. A composite `[monitoring-aws]` extra MUST combine `[monitoring]` and the ADOT exporter. Neither the base package nor the `[aws]` extra MUST include any of these dependencies. This preserves the zero-cloud-dep local mode and allows SaaS deployers to opt into monitoring. (FR-055)
- **FR-055a**: The `[monitoring]` extra MUST function in local mode without AWS credentials. When the OTel SDK is installed but `ANVIL_MODE` is not `saas`, `setup_tracing()` MUST default to a console exporter (`OTEL_TRACES_EXPORTER=console`) or be a no-op. The `/metrics` endpoint MUST NOT be mounted in local mode. The `LogsReader` abstraction MUST fall back to `LocalLogsReader` (file-based) when no CloudWatch Logs client is configured. (FR-055a)
- **FR-055b**: All observability code MUST live in `anvil/_saas/observability/` with the following structure:
  ```
  anvil/_saas/observability/
  ├── __init__.py
  ├── logging.py       # JsonFormatter, setup_logging()
  ├── tracing.py       # setup_tracing(), TRACEPARENT propagation helpers
  └── metrics.py       # Prometheus custom metric definitions
  ```
  The `LogsReader` abstract interface and `LocalLogsReader` live in `anvil/storage/logs.py` (shared, no cloud deps). The `CloudWatchLogsReader` lives in `anvil/_saas/implementations/cw_logs_reader.py` (boto3). (FR-055b)

- **FR-056**: The `training_jobs` table MUST gain a `batch_log_stream` column (nullable `varchar`) to store the CloudWatch Logs stream name for the compute pod, populated at Batch job submission time. No other schema changes are required for observability — traces and metrics are ephemeral (X-Ray spans TTL = 30 days, Prometheus data retention configured per deployment).

#### MLflow Proxy — Browser Access to Internal MLflow

> **Cross-reference (added 2026-06-21): ADR-035 unifies this pattern across local and SaaS modes.**
> The OWASP remediation (spec 017, FR-004) adopts this same `/v1/mlflow-proxy/` reverse proxy for
> **local mode** so that local MLflow is also accessed only through the authenticated app (loopback
> bind, unpublished host port). The proxy mechanism, `--static-prefix`, and `get_mlflow_browser_uri`
> behavior are now shared by both modes; the only differences are the upstream target
> (`ANVIL_MLFLOW_INTERNAL_URI`: loopback locally vs Cloud Map DNS in SaaS) and the auth scheme
> (single API key / session locally vs Cognito JWT in SaaS). See ADR-035 for the binding decision.

- **FR-057**: The SaaS anvil-web application MUST expose an authenticated reverse proxy route at `/v1/mlflow-proxy/{path:path}` that forwards requests to the internal MLflow ECS Fargate service (`mlflow.svc.local:5000`). This is the sole mechanism for browser access to the MLflow UI in SaaS mode — MLflow MUST remain in a private subnet with no direct ALB, CloudFront, or internet route. (FR-057)
- **FR-057a**: The proxy route MUST enforce the same Cognito JWT authentication and RBAC authorization as all other `/v1/*` endpoints (AD-2). Unauthenticated requests MUST return 401. Auth-gating ensures that exposing MLflow through the proxy does not bypass the application's multi-tenant access controls. (FR-057a)
- **FR-057b**: The proxy MUST forward the full request path and query string to the internal MLflow server and stream the response back, including correct `Content-Type` headers for MLflow's HTML pages, JavaScript, CSS, and API JSON responses. The proxy MUST handle MLflow's URL conventions correctly:
  - **Relative URLs and hash-routes** (`#/experiments/...`): resolve automatically under `/v1/mlflow-proxy/` — no rewriting needed.
  - **Absolute AJAX paths** (`/ajax-api/2.0/mlflow/...`): MLflow's SPA issues `fetch`/XHR calls to absolute root-relative paths that would NOT route through the proxy by default. The proxy MUST handle these via one of two mechanisms (chosen at implementation time after testing the bundled MLflow version): (a) configure MLflow's `--static-prefix=/v1/mlflow-proxy` so the SPA emits prefixed paths natively (preferred — MLflow supports this flag), OR (b) the proxy rewrites the served `index.html` to inject a `<base href="/v1/mlflow-proxy/">` tag and rewrites absolute `/ajax-api/` and `/static-files/` references. Mechanism (a) is preferred because it requires no body rewriting.
  - **Static assets** (`/static-files/...`): served through the same prefix mechanism as AJAX paths.
  - The proxy MUST NOT rewrite response bodies if mechanism (a) (`--static-prefix`) is used. Body rewriting (mechanism b) is permitted only as a fallback and only for the `index.html` document, never for streamed artifact downloads. (FR-057b)
- **FR-057g**: The bundled MLflow server MUST be launched with `--static-prefix=/v1/mlflow-proxy` (or equivalent for the pinned MLflow version) so the SPA emits correctly-prefixed AJAX and static-asset URLs. The exact flag and version compatibility MUST be validated in an integration test (a Playwright check that the MLflow experiments list loads and an AJAX call succeeds through the proxy) before the phase gate passes. If the pinned MLflow version does not support `--static-prefix`, the implementation MUST fall back to FR-057b mechanism (b) and the limitation MUST be documented. (FR-057g)
- **FR-057c**: The `get_mlflow_browser_uri(request)` function (in `anvil/config.py`) MUST produce CloudFront-aware URLs in SaaS mode. When `ANVIL_MODE=saas`, it MUST return `{request.base_url}v1/mlflow-proxy` using the CloudFront origin from the request's `Host` header and the `X-Forwarded-Proto` header for scheme (`https`). **REVISED per ADR-035 (2026-06-21): local mode MUST ALSO return the `/v1/mlflow-proxy` URL (not the direct `:5001` subprocess URL) so local MLflow is reached only through the authenticated app.** The local upstream is loopback (`ANVIL_MLFLOW_INTERNAL_URI` default `http://127.0.0.1:5001`) and its host port is no longer published. This function is consumed by the experiments page, models page, and operations page to generate links to MLflow. A corresponding override service in `anvil/_saas/` supplies the SaaS-mode upstream/auth specifics. (FR-057c)
- **FR-057d**: The MLflow proxy route MUST support long-lived HTTP streaming for MLflow's artifact downloads and metric export endpoints. The proxy timeout MUST be configured to match the MLflow server's timeout (default 60s for UI pages, 300s for artifact downloads). The proxy MUST propagate `Transfer-Encoding: chunked` for streaming responses. (FR-057d)
- **FR-057e**: The internal Cloud Map service name and port for the MLflow target MUST be configurable via the `ANVIL_MLFLOW_INTERNAL_URI` environment variable. If this variable is unset in SaaS mode, the factory MUST fail fast at startup (consistent with FR-011c). The default value is `http://mlflow.svc.local:5000`. (FR-057e)
- **FR-057f**: MLflow experiments and runs MUST be tagged with `org_id` at creation time (by the anvil-web service on the user's behalf). The proxy route does NOT filter experiments by org — filtering happens at the application layer before the user reaches the MLflow proxy. The experiments page (`/v1/experiments-page`) provides the org-scoped list; clicking into an experiment navigates to the proxy at `/v1/mlflow-proxy/#/experiments/{mlflow_exp_id}`. Cross-org experiment visibility through the proxy is prevented by the application layer never linking to experiments the user cannot access. (FR-057f)

## Success Criteria

### Measurable Outcomes

- **SC-016**: In-app log viewer (`GET /v1/services/logs/{name}` and `GET /v1/training/{job_id}/logs`) displays CloudWatch Logs content for ECS services and terminated Batch compute pods within 2 seconds of request. Existing local-mode ops page continues working unchanged.
- **SC-017**: An X-Ray trace map visualizes the complete request path for a training job: browser → web → Redis → Batch pod → DB/S3/MLflow, with spans for each service hop including the SSE metrics path.
- **SC-018**: Custom Prometheus metrics (jobs submitted/completed/failed, SSE latency, concurrent jobs) are available in Grafana within 60 seconds of the instrumented event. The `/metrics` endpoint reports standard RED metrics (rate, errors, duration) for all HTTP routes.
- **SC-019**: Installing `pip install anvil` (no extras) does not install any OpenTelemetry or Prometheus packages. Installing `pip install anvil[monitoring]` in local mode enables structured JSON logging to console but does not contact any AWS service, mount `/metrics`, or emit traces to X-Ray.

## Acceptance Gate G9

Gate G9 is the combined Definition of Done for this feature. Every requirement below MUST pass before the feature is considered shipped.

| # | Criterion | Verification |
|---|-----------|-------------|
| G9.1 | Log viewer shows CloudWatch Logs for ECS services and terminated Batch compute pods | `GET /v1/services/logs/{name}` returns CW log content; `GET /v1/training/{job_id}/logs` returns pod logs via `batch_log_stream` |
| G9.2 | X-Ray trace map shows the full request path: browser → web → Redis → Batch pod → DB/S3/MLflow | X-Ray console displays complete trace tree with spans for each service hop |
| G9.3 | Custom Prometheus metrics visible in Grafana | Grafana dashboard shows job lifecycle, SSE latency, concurrent jobs within 60s (SC-018) |
| G9.4 | MLflow UI loads through the proxy | Playwright check: authenticated `/v1/mlflow-proxy/` loads experiments list and AJAX calls succeed (FR-057g) |
| G9.5 | Prometheus `/metrics` endpoint reports RED metrics | `GET /metrics` returns request rate, duration histogram, error rate, in-flight count |
| G9.6 | Alertmanager rule set deployed and routable | Default rules loaded; alert route targets SNS topic or webhook |

## Local-Mode Regression Gate (LMRG)

This feature has **MEDIUM** local-mode risk. Two explicit guards are required:

### Guard 1: Base install — zero OTel/Prometheus (SC-019)

```bash
# pip install anvil (no extras) installs zero OTel/Prometheus packages
pip install anvil
python -c "import opentelemetry"  # MUST fail: ModuleNotFoundError
python -c "import prometheus_client"  # MUST fail: ModuleNotFoundError
```

### Guard 2: `[monitoring]` extra in local mode is no-op for AWS

```bash
pip install anvil[monitoring]
ANVIL_MODE=local anvil serve
# /metrics MUST NOT be mounted (returns 404)
# logs use LocalLogsReader (disk files), not CloudWatch
# setup_tracing() defaults to console exporter or no-op
# No AWS service contacted
```

### Guard 3: Local MLflow reachable via proxy (ADR-035)

```bash
# get_mlflow_browser_uri(request) returns /v1/mlflow-proxy path
# MLflow bound to loopback, host port NOT published
# Existing ops/experiments/models pages resolve MLflow correctly through proxy
```

### Standard LMRG

```bash
make test            # all pre-existing tests pass unmodified
make lint            # zero new lint errors
make typecheck       # mypy --strict clean
pip install .        # clean install
anvil serve          # boots; UI at :8080 works end-to-end
```

## Key Entities

- **LogsReader**: Abstract interface for reading log streams. `LocalLogsReader` (disk files, shared) and `CloudWatchLogsReader` (boto3, `_saas/`) implementations.
- **batch_log_stream**: A nullable `varchar` column on the `training_jobs` table storing the CloudWatch Logs stream name for the compute pod, populated at Batch job submission time.
- **JsonFormatter**: A `logging.Formatter` subclass that emits JSON-structured log records with fields: `timestamp`, `level`, `service`, `message`, `trace_id`, `org_id`, `job_id`.
- **MLflow proxy**: An in-process FastAPI reverse proxy at `/v1/mlflow-proxy/{path:path}` forwarding to internal MLflow via `httpx.AsyncClient`.

## Dependencies

- **032 SaaS Durable Training Pipeline** — requires `TrainingJob` model with `batch_job_id` column; `JobEvent` model for trace context; Batch job submission pattern for `TRACEPARENT` propagation.
- **029 SaaS Authentication & RBAC** — JWT middleware and RBAC guard shared by the MLflow proxy (FR-057a).
- **ADR-035** — governs the unified local+SaaS MLflow proxy pattern; supersedes the prior direct-URL approach.

## Non-Goals

- Real-time log tailing (NG-5 from umbrella spec) — deferred; the in-app viewer polls CloudWatch on user request.
- Managed observability vendor in v1 (NG-4 from umbrella spec) — Prometheus/Grafana/Alertmanager are self-hosted on ECS Fargate.

## Architecture Decisions

This feature is governed by two decisions from [[Reference/SaaSArchitectureDecisions|SaaS Architecture Decisions]]:

- **AD-12 (Observability)**: SaaS-only optional extras; three pillars (logs, traces, metrics); local mode degrades gracefully.
- **AD-13 (MLflow Private Proxy)**: Browser access exclusively through authenticated `/v1/mlflow-proxy/`; MLflow in private subnet with no internet route.

And one dedicated ADR:

- **ADR-035 (MLflow Reverse Proxy)**: Unifies the proxy pattern across local and SaaS modes; local `get_mlflow_browser_uri` returns the proxy path.

## Assumptions

- CloudWatch Logs is the durable log store for all SaaS services (ECS and Batch). Compute pod logs are available in CloudWatch even after the pod terminates.
- X-Ray traces have a default 30-day retention. Prometheus server storage is configured to match the deployment's data retention needs (default 15 days for the ECS-hosted server).
- Prometheus scraping of ECS Fargate tasks uses `ecs_sd_configs` — the Prometheus server discovers tasks via the ECS API, which requires the `ecs:ListTasks` and `ecs:DescribeTasks` permissions on the Prometheus execution role.
- Compute pod custom metrics use CloudWatch EMF because the pod is ephemeral and cannot be scraped by Prometheus. EMF metrics are billed as CloudWatch custom metrics.
- The OTel SDK and Prometheus client libraries are pure Python or have minimal C extensions — they do not significantly increase container image size.
- The existing local-mode operations page (`/v1/operations`) displays logs from local disk files. In SaaS mode, the same page becomes a CloudWatch Logs-backed viewer.
- MLflow in SaaS mode is never exposed directly to the internet. Browser access is exclusively through the anvil-web reverse proxy.
- The MLflow proxy is a standard FastAPI `httpx.AsyncClient` reverse proxy and does not require any additional runtime dependency beyond `httpx`.
- The bundled MLflow runs with `--static-prefix=/v1/mlflow-proxy` so its SPA emits proxy-correct AJAX/static URLs.