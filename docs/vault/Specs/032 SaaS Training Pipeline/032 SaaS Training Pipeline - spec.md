---
title: 032 SaaS Training Pipeline - spec
type: spec
tags:
  - type/spec
  - domain/training
  - domain/operations
  - domain/infrastructure
spec-refs:
  - docs/vault/Specs/032 SaaS Training Pipeline/
related:
  - '[[032 SaaS Training Pipeline]]'
created: '2026-06-27'
updated: '2026-06-27'
status: draft
---

# Feature Specification: SaaS Training Pipeline — Durable Job State & Live Metrics

**Feature Branch**: `032-saas-training-pipeline`
**Created**: 2026-06-27
**Status**: Draft
**Parent Spec**: [[Specs/016 SaaS Architecture/016 SaaS Architecture|016 SaaS Architecture (superseded umbrella)]]

## Overview

This is the **core product** feature (Feature 5 in the shippable-features breakdown, corresponding to Phase 5 / US2 of the umbrella spec). It ships the complete training pipeline for SaaS mode: durable job state in PostgreSQL with append-only `JobEvent`s, AWS Batch dispatch (CPU/GPU/multi-GPU/multi-node), live metric streaming via Redis→SSE, a stateless reconciler for self-healing, usage metering for billback, and all the SaaS implementations behind the abstraction interfaces established in Spec 028.

### Scope

| Dimension | Scope |
|-----------|-------|
| **Owned FRs** | FR-004 (SSE impl aspect), FR-005, FR-006, FR-007, FR-015, FR-016 (impls aspect), FR-039, FR-040, FR-041, FR-042, FR-043, FR-043a, FR-044, FR-044a, FR-045, FR-045a, FR-045b, FR-045c, FR-045d, FR-045e, FR-045f, FR-045g, FR-045h, FR-045i, FR-045j, FR-045k, FR-045l, FR-045m, FR-045n, FR-045o, FR-045p, FR-045r, FR-046, FR-047, FR-048, FR-017 (MLflow Postgres aspect) |
| **Owned Decisions** | AD-1, AD-4, AD-5, AD-9, AD-11 |
| **Depends on** | [[Specs/031 SaaS Multi-Tenancy RBAC/031 SaaS Multi-Tenancy RBAC|031 SaaS Multi-Tenancy]] (RBAC models, org-scoped queries) |
| **Local-mode risk** | **LOW** — all new SaaS implementations behind existing interfaces. Local mode keeps `InProcessJobQueue`/`LocalTorchBackend`/`InProcessEventBus`. |

---

## User Story

### US2 — SaaS User Trains a Model and Watches Live Metrics (Priority: P1)

A logged-in SaaS user uploads a text corpus, configures hyperparameters, starts training, and watches the loss curve stream live in the browser via SSE. On completion, the model is available for download.

**Independent test**: Can be tested by uploading a small file, starting training with minimal hyperparameters (1 layer, 50 steps), and verifying the SSE stream shows step/loss updates and the completed model is downloadable.

**Acceptance Scenarios**:

1. **Given** a logged-in user with an uploaded corpus, **When** they configure training and click start, **Then** a training job is created (status=pending) and the browser opens an SSE connection.
2. **Given** a training job is running, **When** the compute pod completes each step, **Then** a metrics event is published to Redis, forwarded via SSE, and the browser updates the loss curve in real-time.
3. **Given** training completes, **When** the compute pod finishes, **Then** the final loss and generated samples appear in the browser and the model artifacts are stored in S3.
4. **Given** a completed training run, **When** the user clicks download, **Then** a signed S3 URL is returned and the `model.safetensors` file is downloaded.

---

## Requirements

### Compute (CPU / GPU / Multi-Node)

- **FR-039**: The compute layer MUST support four job shapes: `cpu` (CPU-only), `gpu` (single GPU), `multi-gpu` (N GPUs on one node), and `multi-node` (M nodes × N GPUs, gang-scheduled). SaaS mode dispatches to AWS Batch on EC2; local mode runs in-process.
- **FR-040**: The `JobQueue.submit()` / `ComputeBackend.run()` abstraction MUST express compute requirements as a structured `ResourceSpec` (`{node_count, gpus_per_node, vcpus, memory, instance_class}`) so multi-node jobs are first-class, not a special case.
- **FR-041**: Multi-node training jobs MUST use AWS Batch multi-node parallel job definitions with gang scheduling; placement-group locality and EFA networking MUST be configurable for high-bandwidth inter-node communication.
- **FR-042**: The Batch compute environment MUST support EC2 Spot for cost reduction with graceful handling of Spot interruption (job retry / checkpoint resume where supported).

### Job State Consistency

- **FR-043**: PostgreSQL MUST be the single source of truth for job lifecycle. Job state transitions MUST be recorded in an append-only `job_events` table with idempotent keys `(job_id, sequence)`. Redis is delivery-only and MUST NOT be treated as authoritative.
- **FR-043a — `job_events` capacity & lifecycle**: Because each training step may append an event, the `job_events` table is high-volume (a 10K-step job ≈ 10K rows). The design MUST address growth:
  - **Metric granularity control**: per-step metric events MUST be throttled to a configurable cadence (default: emit a metric event at most every N steps or every T seconds, whichever is coarser) so a 100K-step job does not produce 100K rows. Authoritative lifecycle events (submitted/started/completed/failed/cancelled) are always written; metric events are sampled. SSE live granularity (via Redis) is independent and can be finer.
  - **Index strategy**: unique index on `(job_id, sequence)` (correctness + idempotency); secondary index on `(org_id, job_id, ts)` for org-scoped listing; partial index on non-terminal status for the reconciler scan. Indexes MUST be chosen to not degrade append throughput.
  - **Retention/archival**: a scheduled job MUST archive `job_events` rows for terminal jobs older than a configurable window (default 30 days) to a `job_events_archive` table (or cold storage). The hot table stays bounded. UsageRecords (FR-046) are already derived and persisted, so archival of raw events does not lose billing data.
  - **Autovacuum**: the table requires tuned autovacuum (it is append-heavy with periodic bulk archival deletes). Deployment docs MUST note recommended `autovacuum_vacuum_scale_factor` for this table.
  (FR-043a)
- **FR-044**: Compute pods MUST write artifacts to deterministic S3 keys and emit idempotent lifecycle events. A reconciler MUST periodically compare Batch job state, DB state, MLflow run state, and expected S3 artifacts, and repair any job stuck in a non-terminal state beyond a configurable grace period.
- **FR-044a — Reconciler operating parameters**: The reconciler MUST be specified precisely:
  - **Period**: runs on a fixed schedule, default every 60 seconds, configurable via `ANVIL_RECONCILER_INTERVAL_SECONDS`. The grace period before declaring a non-terminal job dead is separately configurable (default 300s) via `ANVIL_RECONCILER_GRACE_SECONDS`.
  - **Stateless**: the reconciler holds NO in-memory state between runs. Each run is a full scan of non-terminal jobs from PostgreSQL. A reconciler crash mid-run causes no corruption — the next run re-scans from scratch. It MUST be safe to run multiple reconciler instances concurrently (idempotent appends via `(job_id, sequence)` unique key).
  - **Idempotency / race with live pods**: before appending a terminal `failed` event, the reconciler MUST re-check the latest `job_events` sequence for that job to avoid racing a healthy pod that is actively writing. If a newer event appeared since the scan began, the reconciler skips that job this cycle. The `(job_id, sequence)` unique constraint is the final guard — a duplicate append is rejected by the DB, not silently doubled.
  - **Dependency degradation backoff**: the reconciler reads four surfaces (Batch API, PostgreSQL, S3, MLflow). If ANY surface returns errors/throttling, the reconciler MUST back off and NOT mark jobs as failed on incomplete information — a transient Batch API outage MUST NOT cause healthy jobs to be reaped. It logs the degradation and retries on the next cycle.
  - **Heartbeat**: the reconciler MUST emit a heartbeat metric/log each cycle so Alertmanager can detect a dead reconciler (FR-054e dead-man's switch).
  (FR-044a)
- **FR-045**: SSE streaming MUST support `Last-Event-ID` replay backed by `job_events`, so a client reconnecting to any replica resumes the stream without gaps.
- **FR-045a**: The system MUST expose a metrics polling endpoint `GET /v1/training/{job_id}/events?since={sequence}` that returns the `job_events` backlog (status + metrics) after a given sequence. This is the durable fallback used when SSE cannot be established (proxies blocking `text/event-stream`) or for clients that prefer polling. It reads the same `job_events` source of truth as SSE.
- **FR-045b**: The browser client MUST auto-degrade: attempt SSE first; on repeated connection failure (EventSource `onerror` without open), fall back to polling `GET /v1/training/{job_id}/events?since=` on a fixed interval. Both paths render identically because both read `job_events`. The job's terminal state is always reachable via polling even if SSE never connects.
- **FR-045r — Server-signaled SSE degradation**: When the serving web replica cannot establish or loses its Redis subscription (Redis outage, failover in progress), the SSE handler MUST send an explicit `event: degraded` SSE message instructing the browser client to switch to polling `GET /v1/training/{job_id}/events?since=` immediately, rather than waiting for the client-side `onerror` heuristic. When Redis recovers, the server MAY send `event: live` to allow the client to resume SSE. This makes degradation deterministic (server-driven) rather than relying solely on client timeout heuristics (FR-045b). Both paths read the same `job_events` source of truth, so no metrics are lost during the Redis outage — they are replayed from `job_events` on the next poll or `Last-Event-ID` cycle. (FR-045r)

### Training Job Orchestration

- **FR-045g**: Training orchestration MUST follow a three-plane model: **control plane** (anvil-web admits, configures, submits, and observes — never tracks progress by polling the pod), **scheduler** (AWS Batch owns queueing, compute-environment scaling, gang-scheduling, and retries), **executor** (the compute pod runs `anvil/core` and emits events). Planes communicate only through durable records (`job_events`, S3), never direct mutation.
- **FR-045h**: Job configuration MUST be split into four concerns: hyperparameters (`TrainingJob.config`), `ResourceSpec` (compute), data binding (`corpus_id`/`dataset_id`), and job policy (timeout/retry/priority). Hyperparameters and data references MUST be delivered to the pod via an S3 config object (`jobs/{job_id}/config.json`), not env vars; the pod receives only small pointers (`JOB_ID`, `CONFIG_S3_KEY`) as env.
- **FR-045i**: Batch job definitions MUST be pre-registered per compute shape (`anvil-cpu`, `anvil-gpu`, `anvil-multigpu`, `anvil-multinode`) and parameterized per job via container overrides from `ResourceSpec` — not dynamically created per submission.
- **FR-045j** — Quota: anvil-web MUST enforce per-org quotas (max concurrent jobs, max total GPUs) before submitting to Batch; jobs exceeding quota are rejected or queued with a clear reason. Batch fair-share scheduling provides the second layer.
- **FR-045k** — Fair-share scheduling: The Batch job queue MUST use a fair-share scheduling policy keyed on `org_id` so no organization can starve others. No user-facing priority tiers in v1.
- **FR-045l** — Retry policy: Infrastructure failures (Spot interruption, instance failure) MUST auto-retry (Batch `attempts` = 2–3) and resume from the last checkpoint; user/config errors (invalid hyperparameters, missing data) MUST fail immediately without retry. The reconciler is the backstop for jobs that escape both paths.
- **FR-045m** — Checkpointing: Long-running and multi-node jobs MUST write periodic checkpoints to S3 (deterministic keys). On Spot reclaim + retry, the worker MUST resume from the last checkpoint rather than restarting from scratch.
- **FR-045n** — Cancellation: A user with permission MUST be able to cancel a pending or running job; cancellation terminates the Batch job and records a `cancelled` `JobEvent`. Cancellation is idempotent.
- **FR-045o** — Timeout: Each job MUST have a maximum duration (Batch job timeout + reconciler grace); exceeding it transitions the job to `failed` with a timeout reason.
- **FR-045p** — Multi-node coordination: For multi-node parallel jobs, only the main node (rank 0) MUST emit authoritative `JobEvent`s and write the final artifact; worker nodes participate in training (NCCL/EFA) but do not write job state, preventing duplicate/conflicting events.

### Secrets Management & Credential Flow

- **FR-045c**: Compute pods and the web tier MUST authenticate to PostgreSQL via **RDS Proxy + IAM database authentication** (`rds-db:connect`). Static database passwords MUST NOT flow to pods. Each connection uses a short-lived (≤15 min) IAM-derived auth token generated from the task's IAM role. The real DB master password is held only by RDS Proxy (read from Secrets Manager) and is never injected into any application container.
- **FR-045d**: Secrets that cannot use IAM auth (Redis auth token, SSE signing secret, social OAuth client secrets) MUST be stored in Secrets Manager and delivered to containers via the ECS/Batch task `secrets:` mechanism (execution role pulls and injects as env at launch). Secrets MUST NEVER be baked into images, written to logs, or passed as plaintext container overrides.
- **FR-045e**: Long-lived SQLAlchemy connection pools (web tier, MLflow) MUST use a token-provider callback that regenerates the IAM auth token on new connections, so pools survive beyond the 15-minute token lifetime without manual credential rotation.
- **FR-045f**: IAM permissions MUST be least-privilege and split: the **execution role** grants ECR pull, CloudWatch Logs, and scoped Secrets Manager reads; the **job/task role** grants `rds-db:connect`, S3 read/write on the org-scoped prefix, and Redis connectivity. No role grants broader access than its function requires.

### Usage Metering & Billback

- **FR-046**: On every job completion, the system MUST write a `usage_record` capturing GPU-seconds and instance-hours (derived from job runtime × resolved instance type), attributed to `org_id`, `team_id`, `user_id`, and `job_id`. Records MUST derive from `job_events` (the authoritative lifecycle), not a separate write path.
- **FR-047**: Batch jobs MUST be tagged with AWS Cost Allocation Tags (`org_id`, `team_id`, `user_id`) so internal `usage_records` can be cross-checked against AWS Cost Explorer.
- **FR-048**: The system MUST expose a usage query API returning aggregated usage per organization, team, and user over a time range, for billback reporting.

### MLflow Integration

- **FR-017**: MLflow in SaaS mode MUST use the same PostgreSQL server as the application (separate `anvil_mlflow` database) with artifacts on S3.

### Cross-Cutting (Implied by Abstraction Interfaces)

- **FR-004**: System MUST support SSE-based live training metrics streaming via Redis pub/sub (SaaS mode) or in-process `asyncio.Queue` (local mode). *(Implementation aspect — the streaming mechanism is realized by this spec.)*
- **FR-005**: System MUST dispatch training jobs to AWS Batch (SaaS mode) or run in-process (local mode), selected at deploy time. *(Batch dispatch is implemented by this spec.)*
- **FR-006**: System MUST store application data in S3 (SaaS mode) or local filesystem (local mode), selected at deploy time. *(S3 storage for training artifacts is implemented by this spec.)*
- **FR-007**: System MUST track training job lifecycle (pending → running → completed/failed) in PostgreSQL (SaaS mode) or SQLite (local mode). *(Job lifecycle tracking in PostgreSQL is implemented by this spec.)*
- **FR-015**: SaaS mode MUST support concurrent training jobs across multiple users and multiple jobs per user.
- **FR-016**: The core abstraction interfaces (`FileStore`, `EventBus`, `JobQueue`, `ComputeBackend`) MUST be defined with local implementations alongside them and SaaS implementations in `anvil/_saas/implementations/`. *(The SaaS implementations are provided by this spec.)*

---

## Edge Cases

- What happens when a **compute pod** crashes mid-training (Spot reclaim, instance failure)? Training execution stops, but `job_events` in PostgreSQL preserves all progress (AD-4). The reconciler detects the dead Batch job (Batch status FAILED, or grace timeout with no new events) and appends a terminal `failed` event, moving the job out of `running`. For Spot-interrupted jobs, optional retry per FR-042. No job stays stuck `running` indefinitely (SC-012).
- What happens when a **web pod** (ECS replica) serving an SSE stream goes down? Training is unaffected (it runs in a separate Batch pod). The browser's `EventSource` fires `onerror` and auto-reconnects through the ALB to any healthy replica, sending `Last-Event-ID`; the new replica replays `job_events` since that sequence and resubscribes to Redis — no metrics gap (FR-045, AD-5).
- What happens when SSE cannot be established at all (corporate proxy strips `text/event-stream`)? The client auto-degrades to polling `GET /v1/training/{job_id}/events?since=` (FR-045a/b). Both paths read the same `job_events` source of truth, so the loss curve and terminal state are always reachable.
- What happens when the Redis pub/sub connection drops during training? The SSE stream pauses. Mitigation: the serving replica reconnects to Redis and resubscribes; any events missed during the gap are recovered from `job_events` on the next `Last-Event-ID` cycle (Redis is delivery-only, not the source of truth). The server sends `event: degraded` (FR-045r) so the client switches to polling immediately rather than waiting for client timeout.
- What happens when a compute pod exceeds its 15-minute IAM token lifetime? The SQLAlchemy token-provider callback regenerates a fresh token on the next connection from the pool (FR-045e); existing pooled connections through RDS Proxy remain valid. No job interruption.
- What happens if S3 upload from the compute pod fails mid-checkpoint? The worker retries with exponential backoff (boto3 default). If all retries are exhausted, the checkpoint is skipped (the job continues with the last good checkpoint). The reconciler catches terminal-state artifacts missing from S3.
- What happens in local mode when `ANVIL_MODE=saas` is not set? Local mode runs the `anvil.api.app:app` entrypoint, selecting `InProcessJobQueue` + `LocalTorchBackend`/`LocalStdlibBackend` + `InProcessEventBus`. The `TrainingJob`/`JobEvent` models are shared but the local flow remains in-process, emitting events into an `asyncio.Queue` — no change to user-facing behavior.
- What happens if a user exceeds their per-org quota? The training start endpoint rejects the submission with a clear quota-exceeded message (FR-045j). The submission is not forwarded to Batch.

---

## Success Criteria

- **SC-002**: Training metrics appear in the browser within 1 second of the compute pod reporting them (SSE latency via Redis pub/sub).
- **SC-003**: Users can run 10+ concurrent training jobs across different accounts without interference or performance degradation.
- **SC-012**: A training job that loses its compute pod mid-run is detected and reconciled to a terminal state (`failed` or recovered) within the configured grace period — no job remains stuck in `running` indefinitely.
- **SC-013**: Every completed training job produces exactly one `usage_record` attributing GPU-seconds/instance-hours to the correct `org_id`, `team_id`, and `user_id`.
- **SC-015**: Multi-node distributed training jobs (M nodes × N GPUs) gang-schedule and complete; the `JobQueue`/`ComputeBackend` abstraction expresses all four compute shapes (cpu, gpu, multi-gpu, multi-node).

---

## Acceptance Gate G5

**Gate G5** — All of the following MUST pass:

- CPU/GPU/multi-node jobs complete end-to-end
- Per-org quota enforced; fair-share prevents starvation
- Spot interruption auto-retries + resumes from checkpoint
- User/config errors fail immediately (no retry)
- Cancellation terminates Batch job + records `cancelled` event; cancellation is idempotent
- Timeout → `failed` with timeout reason
- SSE delivers live metrics to browser
- SSE reconnect (`Last-Event-ID` replay) resumes without gap
- Polling fallback reaches terminal state when SSE never connects
- Server-signaled degradation (`event: degraded`) switches client to polling when Redis is down
- Pod-crash reconciled within grace period (SC-012)
- Artifact lands in S3 + MLflow
- `usage_record` created with correct attribution (SC-013)
- `mypy --strict` clean
- Contract tests pass for all SaaS implementations

---

## Local-Mode Regression Gate

This feature carries the **Local-Mode Regression Gate (LMRG)** per the shippable-features convention. Every new piece is a SaaS *implementation behind an existing interface*. Local mode keeps selecting `InProcessJobQueue` + `LocalTorchBackend`/`LocalStdlibBackend` + `InProcessEventBus` — no local code path changes. The shared `TrainingJob`/`JobEvent` models remain usable by the in-process local flow (local mode emits the same events into an in-process bus).

```bash
make test            # all pre-existing tests pass UNMODIFIED (SC-007)
make lint            # zero new lint errors
make typecheck       # mypy --strict clean; no SaaS imports leaking into non-SaaS modules
pip install .        # clean install
anvil serve          # boots; UI at :8080 works end-to-end (upload → train → SSE → export)
```

Plus the **import-isolation assertion**:

```bash
python - <<'PY'
import importlib, sys
import anvil.api.app
for forbidden in ("boto3", "redis", "aws_jwt_verify", "opentelemetry", "prometheus_client"):
    assert forbidden not in sys.modules, f"{forbidden} loaded by local entrypoint"
print("import isolation OK")
PY
```

PLUS confirm the **local in-process training flow still streams metrics via `InProcessEventBus`** and produces a downloadable model from `data/models/`, exactly as before. The introduction of `JobEvent` MUST NOT change local behavior (local may persist events to SQLite but the user-facing SSE stream is unchanged).

---

## Dependencies

- [[Specs/028 SaaS Abstraction Framework/028 SaaS Abstraction Framework|028 SaaS Abstraction Framework]] — abstraction interfaces (`FileStore`, `EventBus`, `JobQueue`, `ComputeBackend`, `ResourceSpec`)
- [[Specs/029 SaaS Dev Stack/029 SaaS Dev Stack|029 SaaS Dev Stack]] — docker compose environment for local testing
- [[Specs/030 SaaS Authentication/030 SaaS Authentication|030 SaaS Authentication]] — JWT auth middleware, SSE signed-token auth
- [[Specs/031 SaaS Multi-Tenancy RBAC/031 SaaS Multi-Tenancy RBAC|031 SaaS Multi-Tenancy]] — RBAC models, org-scoped repository queries

---

## Related Architecture Decisions

| AD | Title | How it applies |
|----|-------|----------------|
| AD-1 | Compute on AWS Batch on EC2 | BatchJobQueue + BatchComputeBackend dispatch to Batch on EC2 (CPU, GPU, multi-node) |
| AD-4 | Postgres source of truth + reconciler | `job_events` table is authoritative; Redis is delivery-only; reconciler repairs stuck jobs |
| AD-5 | SSE per-connection subscribe + replay | SSE handler subscribes to Redis channel per job; `Last-Event-ID` replay from `job_events` |
| AD-9 | Usage metering from `job_events` | `UsageRecord` derived from terminal `JobEvent`, not separate write path |
| AD-11 | Three-plane orchestration | Control plane (anvil-web), scheduler (Batch), executor (compute pod); planes never mutate directly |