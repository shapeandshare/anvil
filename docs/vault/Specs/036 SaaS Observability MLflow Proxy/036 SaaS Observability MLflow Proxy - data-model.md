---
title: 036 SaaS Observability MLflow Proxy - data-model
type: data-model
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

# Data Model: SaaS Observability & MLflow Proxy

This model covers three data concerns for the observability feature: (1) the `batch_log_stream` column on `TrainingJob`, (2) custom Prometheus metric definitions, and (3) the `LogsReader` interface hierarchy.

## 1. Schema Change: `batch_log_stream` Column

### TrainingJob (new column)

| Field | Type | Description |
|-------|------|-------------|
| `batch_log_stream` | `varchar` (nullable) | CloudWatch Logs stream name for the compute pod, populated at Batch job submission time |

**Naming convention**: predictable from `{batch_job_id}/default` per AWS Batch log stream naming.

**Population**: set at Batch submission time in the `BatchJobQueue.submit()` implementation. Stored on the `training_jobs` row so the API can query CloudWatch Logs for the terminated pod's log stream post-hoc.

**No other schema changes** — traces and metrics are ephemeral (X-Ray spans TTL = 30 days, Prometheus data retention configured per deployment).

## 2. Custom Prometheus Metric Definitions

All metrics defined in `anvil/_saas/observability/metrics.py` using `prometheus_client`.

### Counters

| Metric | Labels | Description |
|--------|--------|-------------|
| `anvil_jobs_submitted_total` | `compute_shape`, `org_id` | Total training jobs submitted |
| `anvil_jobs_completed_total` | `compute_shape`, `org_id` | Total training jobs completed |
| `anvil_jobs_failed_total` | `compute_shape`, `org_id`, `reason` | Total training jobs failed |
| `anvil_training_steps_total` | `org_id`, `compute_shape` | Total training steps completed |

### Histograms

| Metric | Buckets | Description |
|--------|---------|-------------|
| `anvil_sse_publish_latency_seconds` | `[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5]` | SSE publish latency (subscribe-to-browser) |

### Gauges

| Metric | Labels | Description |
|--------|--------|-------------|
| `anvil_concurrent_jobs` | `org_id` | Current number of running training jobs |
| `anvil_org_quota_remaining` | `org_id` | Remaining concurrent job quota for org |

### Cardinality Control

Labels MUST be kept low-cardinality:
- `org_id` on gauges and high-level counters only.
- Step-level counters use `compute_shape` without per-org labels to avoid cardinality explosion.
- `reason` on `jobs_failed` is limited to a fixed set: `infra_error`, `user_error`, `timeout`, `cancelled`, `reconciled`.

## 3. LogsReader Interface Hierarchy

```python
from abc import ABC, abstractmethod


class LogsReader(ABC):
    """Abstract reader for service and job log streams."""

    @abstractmethod
    async def read_service_logs(
        self, service_name: str, lines: int = 100
    ) -> list[dict]:
        """Read recent log lines for a named service.

        Parameters
        ----------
        service_name : str
            Service identifier (e.g., "anvil-web", "anvil-mlflow").
        lines : int
            Maximum number of log lines to return.

        Returns
        -------
        list[dict]
            List of log entries, each with ``timestamp``, ``message``,
            and optionally ``level`` / ``trace_id``.
        """

    @abstractmethod
    async def read_job_logs(
        self, job_id: int, batch_log_stream: str, lines: int = 100
    ) -> list[dict]:
        """Read log lines for a terminated compute pod.

        Parameters
        ----------
        job_id : int
            Training job ID.
        batch_log_stream : str
            CloudWatch Logs stream name for the compute pod.
        lines : int
            Maximum number of log lines to return.

        Returns
        -------
        list[dict]
            List of log entries, each with ``timestamp`` and ``message``.
        """


class LocalLogsReader(LogsReader):
    """File-based log reader for local mode.

    Reads from ``data/logs/{service_name}.log`` for service logs
    and ``data/logs/jobs/{job_id}.log`` for job logs.
    """

    async def read_service_logs(
        self, service_name: str, lines: int = 100
    ) -> list[dict]:
        ...

    async def read_job_logs(
        self, job_id: int, batch_log_stream: str, lines: int = 100
    ) -> list[dict]:
        ...


class CloudWatchLogsReader(LogsReader):
    """CloudWatch Logs-based reader for SaaS mode.

    Uses ``boto3 logs filter-log-events`` for ECS service
    log groups and Batch compute pod log streams.
    """

    def __init__(self, log_group_map: dict[str, str]) -> None:
        """Map service names to CloudWatch log group names.

        Parameters
        ----------
        log_group_map : dict[str, str]
            Mapping of service names to log group names, e.g.::

                {"anvil-web": "/ecs/anvil-web", "anvil-mlflow": "/ecs/anvil-mlflow"}
        """

    async def read_service_logs(
        self, service_name: str, lines: int = 100
    ) -> list[dict]:
        ...

    async def read_job_logs(
        self, job_id: int, batch_log_stream: str, lines: int = 100
    ) -> list[dict]:
        ...


class NullLogsReader(LogsReader):
    """Null reader returned when [monitoring] extra is not installed.

    Returns a structured ``{"status": "not_configured"}`` response
    rather than raising ``ImportError``.
    """

    async def read_service_logs(
        self, service_name: str, lines: int = 100
    ) -> list[dict]:
        return [{"status": "not_configured",
                 "message": "Log viewer requires the anvil[monitoring] extra"}]

    async def read_job_logs(
        self, job_id: int, batch_log_stream: str, lines: int = 100
    ) -> list[dict]:
        return [{"status": "not_configured",
                 "message": "Log viewer requires the anvil[monitoring] extra"}]
```

## 4. MLflow Proxy Data Flow

No new data schema. The proxy is a stateless HTTP forwarder. Data considerations:

| Aspect | Detail |
|--------|--------|
| **Upstream resolution** | `ANVIL_MLFLOW_INTERNAL_URI` env var (SaaS: `http://mlflow.svc.local:5000`, local: `http://127.0.0.1:5001`) |
| **Auth** | Cognito JWT validated in middleware (same as all `/v1/*` routes) |
| **Org scoping** | MLflow experiments tagged with `org_id` at creation; filtering happens at app layer before proxy navigation |
| **Proxy timeout (UI)** | 60s (matching MLflow default) |
| **Proxy timeout (artifacts)** | 300s (matching MLflow artifact download timeout) |
| **Caching** | None — proxy is pass-through; CloudFront may cache MLflow static assets if configured |

## 5. CloudWatch EMF Metric Format (Compute Pods)

Compute pods emit custom metrics via CloudWatch Embedded Metric Format (EMF) as a single JSON log line to stdout:

```json
{
  "_aws": {
    "Timestamp": 1719360000000,
    "CloudWatchMetrics": [
      {
        "Namespace": "Anvil/Compute",
        "Dimensions": [["org_id", "compute_shape"]],
        "Metrics": [
          {"Name": "TrainingSteps", "Unit": "Count"},
          {"Name": "JobDuration", "Unit": "Seconds"}
        ]
      }
    ]
  },
  "org_id": "42",
  "compute_shape": "gpu",
  "TrainingSteps": 1500,
  "JobDuration": 342.5
}
```

This creates CloudWatch custom metrics auto-extracted from the log line, surfaced in Grafana via the CloudWatch data source (FR-054c).