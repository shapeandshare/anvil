---
title: 032 SaaS Training Pipeline - research
type: research
tags:
  - type/spec
  - domain/training
spec-refs:
  - docs/vault/Specs/032 SaaS Training Pipeline/
related:
  - '[[032 SaaS Training Pipeline]]'
created: '2026-06-27'
updated: '2026-06-27'
status: draft
---

# Research: SaaS Training Pipeline — Durable Job State & Live Metrics

**Phase 0 output** — resolves implementation unknowns for the training pipeline feature.

---

## 1. Redis Pub/Sub for SSE Bridging

### Decision
Use ElastiCache Redis pub/sub with `redis.asyncio` to bridge compute pod metrics → browser SSE. The FastAPI SSE handler subscribes to a per-job Redis channel; the compute pod publishes to it. Redis is **delivery-only** — never the source of truth (AD-4).

### Key Findings

| Aspect | Decision |
|--------|----------|
| **Library** | `redis.asyncio` (part of `redis-py` >= 4.5) — async pub/sub with connection pooling |
| **Channel naming** | `training:metrics:{job_id}` — per-job isolation |
| **SSE handler** | Subscribe in SSE handler's async generator → yield events → unsubscribe on disconnect |
| **Disconnect cleanup** | `request.is_disconnected()` check per iteration → cleanup via `async with` context manager |
| **Heartbeat** | 30s SSE heartbeat to keep CloudFront/ALB connection alive |
| **TLS** | ElastiCache with in-transit encryption (`rediss://`) |
| **Security groups** | Batch pod SG → Redis SG on port 6379 |
| **Degradation signaling** | Server sends `event: degraded` when Redis subscription drops (FR-045r) |

### Message Format
```json
{
  "event": "metrics",
  "data": {
    "step": 1500,
    "loss": 2.345,
    "device": "cuda:0",
    "elapsed_sec": 342.5,
    "steps_per_sec": 45.2,
    "eta_sec": 120.0
  }
}
```

### Alternatives Considered
- SQS polling: Durable but higher latency and more complex. Fine for batch, not real-time.
- Direct HTTP from compute pod to anvil SSE endpoint: Couples compute to web lifecycle.
- WebSocket with API Gateway: No existing WebSocket infra, adds cost. SSE is simpler.

---

## 2. Batch Compute Pod Access

### Decision
Two distinct IAM roles (execution + job), IAM database authentication via RDS Proxy, VPC endpoints for AWS services.

### Key Findings

| Aspect | Decision |
|--------|----------|
| **IAM execution role** | ECR pull, Secrets Manager read, CloudWatch logs |
| **IAM job role** | S3 read/write, RDS IAM connect, ElastiCache connect, KMS decrypt |
| **RDS access** | RDS Proxy + IAM database authentication (15-min tokens) — no static passwords (FR-045c) |
| **S3 access** | Job role IAM policy with separate read/write resource ARNs |
| **MLflow from pod** | Cloud Map service discovery (`mlflow.anvil.local:5000`) — HTTP, no auth needed internally |
| **Network** | Batch pods in private subnets. VPC Gateway Endpoint for S3. VPC Interface Endpoints for ECR, Secrets Manager, CloudWatch Logs. |
| **Secrets injection** | Non-sensitive config via container overrides. Sensitive (Redis auth token, SSE signing secret) via Secrets Manager (FR-045d). |

---

## 3. Job Event Storage Strategy

### Decision
PostgreSQL source of truth with append-only `job_events` table. Idempotent `(job_id, sequence)` key.

### Key Findings

| Aspect | Decision |
|--------|----------|
| **Primary key** | Unique `(job_id, sequence)` — idempotent for pod retry (FR-043) |
| **Metric throttling** | Configurable cadence (N steps or T seconds, whichever coarser). Lifecycle events always written (FR-043a) |
| **Index strategy** | Unique `(job_id, seq)`, secondary `(org_id, job_id, ts)`, partial non-terminal (FR-043a) |
| **Archival** | 30-day default window → `job_events_archive` table (FR-043a) |
| **Autovacuum** | Tuned for append-heavy + bulk-delete pattern (FR-043a) |
| **SSE replay** | `Last-Event-ID` reads from `job_events` (AD-5) |
| **Reconciler** | 60s scan of non-terminal jobs, 300s grace, dependency backoff (FR-044a) |

---

## 4. Reconciler Design

### Decision
Stateless reconciler running on a fixed schedule. Scans non-terminal jobs from PostgreSQL, compares against Batch/MLflow/S3, appends terminal events for stuck jobs.

### Key Findings

| Aspect | Decision |
|--------|----------|
| **Period** | 60s default, configurable via `ANVIL_RECONCILER_INTERVAL_SECONDS` (FR-044a) |
| **Grace** | 300s default, configurable via `ANVIL_RECONCILER_GRACE_SECONDS` (FR-044a) |
| **State** | Stateless — crash-safe, multiple instances safe (FR-044a) |
| **Race guard** | Re-check latest `job_events` before appending terminal event (FR-044a) |
| **Degradation backoff** | If any of 4 read surfaces returns errors, back off — don't reap on incomplete info (FR-044a) |
| **Heartbeat** | Emit metric/log each cycle for dead-man's switch (FR-044a) |

---

## Summary of Architecture Decisions

| Area | Decision | AD Reference |
|------|----------|--------------|
| **Compute substrate** | AWS Batch on EC2 (CPU / GPU / multi-node) | AD-1 |
| **Job state** | PostgreSQL source of truth + append-only events + reconciler | AD-4 |
| **SSE streaming** | Per-connection subscribe + `Last-Event-ID` replay | AD-5 |
| **Usage metering** | Derive from `job_events`, cross-check Cost Explorer | AD-9 |
| **Orchestration** | Three-plane: control/scheduler/executor, Batch-owned scheduling | AD-11 |