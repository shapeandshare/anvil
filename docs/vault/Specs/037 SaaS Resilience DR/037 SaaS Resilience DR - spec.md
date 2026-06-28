---
title: 037 SaaS Resilience DR - spec
type: spec
tags:
  - type/spec
spec-refs:
  - docs/vault/Specs/037 SaaS Resilience DR/
related:
  - '[[037 SaaS Resilience DR]]'
created: '2026-06-27'
updated: '2026-06-27'
---

# Feature Specification: SaaS Resilience & Disaster Recovery

**Feature Branch**: `037-saas-resilience-dr`
**Created**: 2026-06-27
**Status**: Draft

## User Scenarios & Testing

### User Story 1 — Redis Primary Fails, SSE Streams Survive (Priority: P1)

A Redis Multi-AZ failover occurs while users have active training SSE streams. The ElastiCache replication group promotes the replica in the second AZ. The browser client receives an `event: degraded` SSE message and switches to polling `GET /v1/training/{job_id}/events?since=`. When Redis recovers, the server MAY send `event: live` to restore SSE. All metrics are preserved because polling reads from `job_events`.

**Why this priority**: Redis is the live SSE delivery path. Its loss degrades all active training streams. Making degradation deterministic (server-driven) rather than relying on client timeout heuristics is essential for production trust.

**Independent Test**:
1. Start a training job and subscribe to its SSE stream.
2. Simulate a Redis Multi-AZ failover (reboot with failover via ElastiCache API, or block Redis port via security group).
3. Verify the browser client receives `event: degraded` and falls back to polling.
4. Verify the loss curve continues updating via polling with no gaps.
5. Restore Redis and verify `event: live` is sent and SSE resumes.

**Acceptance Scenarios**:
1. **Given** an active SSE stream, **When** the ElastiCache primary node fails, **Then** the server sends `event: degraded` and the client switches to polling within the configured client-side interval.
2. **Given** polling is active due to a Redis outage, **When** the client polls `GET /v1/training/{job_id}/events?since=`, **Then** the server returns all `job_events` since the given sequence, including events that arrived during the Redis gap.
3. **Given** Redis recovers, **When** the server detects the subscription is re-established, **Then** it MAY send `event: live` and the client resumes SSE.
4. **Given** the ElastiCache replication group, **When** the primary fails, **Then** automatic failover completes within the ElastiCache Multi-AZ SLA and the primary endpoint resolves to the promoted replica.

---

### User Story 2 — SSE Signing Secret Rotated, In-Flight Streams Survive (Priority: P1)

An operator rotates the SSE signing secret in Secrets Manager. Tokens signed with the previous secret must continue to be accepted during a rotation overlap window so that in-flight SSE streams are not invalidated mid-stream.

**Why this priority**: The SSE signed token (FR-020) authenticates SSE connections. If rotation instantly invalidates all tokens, every active training dashboard loses its live stream simultaneously. The dual-key window prevents this.

**Independent Test**:
1. Connect to an active SSE stream (obtains a signed token).
2. Rotate the SSE signing secret in Secrets Manager (write new `current`, move old to `previous`).
3. Verify the in-flight stream continues (its token was signed with the old key — must pass `previous` validation).
4. Issue a new SSE token for a new stream — verify it is signed with the new `current` key.
5. After the overlap window, the `previous` key is removed — verify a token signed with the old key is now rejected.

**Acceptance Scenarios**:
1. **Given** a token signed with the previous secret, **When** the current secret has been rotated, **Then** the token is accepted via `previous` key verification (dual-key window).
2. **Given** a token signed with the current secret, **When** rotation completes, **Then** the token is accepted via `current` key verification.
3. **Given** the secret is stored as `{"current": "...", "previous": "..."}`, **When** rotation is triggered, **Then** `current` becomes `previous` and a new `current` is generated.
4. **Given** the overlap window has expired, **When** a token signed with the old `previous` key is presented, **Then** it is rejected (window closed).

---

### User Story 3 — Reconciler Crashes Mid-Run, No Corruption (Priority: P1)

The job state reconciler (FR-044a) crashes mid-scan (process killed, OOM, pod restart). On restart, it re-scans from scratch with zero corruption. A healthy job is not accidentally reaped because the reconciler checks the latest `job_events` sequence before appending a terminal event, and the `(job_id, sequence)` unique constraint prevents duplicate appends.

**Why this priority**: The reconciler is the backstop for jobs that escape the normal lifecycle (pod crash, Spot interruption, timeout). A buggy or fragile reconciler that corrupts state or reaps healthy jobs is worse than no reconciler at all.

**Independent Test**:
1. Start a training job.
2. Kill the reconciler process mid-scan (SIGKILL).
3. Restart the reconciler.
4. Verify all non-terminal jobs are either correctly resolved (if grace period elapsed) or left running (if within grace period).
5. Verify no duplicate `job_events` were written (unique constraint check).

**Acceptance Scenarios**:
1. **Given** a reconciler crash mid-run, **When** the reconciler restarts, **Then** it performs a full scan of non-terminal jobs from PostgreSQL — no in-memory state is assumed.
2. **Given** a job is healthy (pod actively writing events), **When** the reconciler's scan overlaps with a live pod's event emission, **Then** the reconciler skips that job this cycle (it detects a newer event appeared since the scan began).
3. **Given** a job whose grace period has expired, **When** the reconciler determines it is truly orphaned, **Then** it appends a terminal `failed` event and the `(job_id, sequence)` unique constraint prevents a duplicate.
4. **Given** a reconciler encounters errors/throttling from any of its four read surfaces (Batch API, PostgreSQL, S3, MLflow), **When** processing a job, **Then** it backs off and does NOT mark the job as failed — it logs the degradation and retries on the next cycle.

---

### User Story 4 — Operator Destroys Stack, Data Is Backed Up (Priority: P1)

An operator runs `anvil deploy destroy`. Before any resource is deleted, they are warned about permanent data loss, offered to take a final RDS snapshot, and must type the stack name to confirm. If a final snapshot is requested, the RDS `DeletionPolicy` is set to `Snapshot` and the snapshot survives stack deletion.

**Why this priority**: Without destroy-time safety, well-intentioned cleanup permanently destroys customer data including months of experiments and trained models.

**Independent Test**:
1. Deploy the stack.
2. Run `anvil deploy destroy` — verify the prompt warns about data loss, offers `--final-snapshot`, and requires stack name confirmation.
3. Accept the final snapshot. Verify the RDS snapshot exists after stack deletion.
4. Verify the snapshot incurs ongoing storage cost until manually deleted.

**Acceptance Scenarios**:
1. **Given** a deployed stack, **When** the operator runs `deploy destroy`, **Then** a warning is displayed: "WARNING: This destroys ALL data, RDS backups, and S3 versions."
2. **Given** the warning, **When** the operator is prompted, **Then** they are asked: "Take a final RDS snapshot before deleting? [Y/n]" (default Y).
3. **Given** the operator confirms, **When** destruction proceeds, **Then** the RDS instance uses `DeletionPolicy: Snapshot` and the snapshot survives stack deletion.
4. **Given** the final snapshot was taken, **When** destruction completes, **Then** the operator is told the snapshot name and that it incurs ongoing storage cost.

---

### User Story 5 — Operator Recovers from Snapshot (Priority: P2)

An operator needs to recover from a disaster (region failure, data corruption, human error). They run `anvil deploy restore --snapshot <id>` to stand up a new stack from an RDS snapshot.

**Why this priority**: While cross-region DR is a documented post-v1 option, the ability to restore from a known-good snapshot is the minimum viable DR capability.

**Independent Test**:
1. Deploy a stack, create some data (corpora, jobs).
2. Take a manual RDS snapshot.
3. Destroy the stack (with `--final-snapshot` or separately).
4. Run `anvil deploy restore --snapshot <id>`.
5. Verify the new stack is healthy and the data from the snapshot is present.

**Acceptance Scenarios**:
1. **Given** an RDS snapshot (final or manual), **When** the operator runs `deploy restore --snapshot <id>`, **Then** a new CloudFormation stack is created using the snapshot as the RDS source.
2. **Given** the new stack is live, **When** the operator logs in (admin credentials are recreated or preserved), **Then** the data from the snapshot is available.
3. **Given** a restore from a cross-region snapshot, **When** the snapshot is in a different region, **Then** the command documents that the snapshot must first be copied to the target region.

---

### Edge Cases

- What happens if a **secret rotation** is initiated but the ECS service is not restarted? The running tasks continue using the old injected env value. The rotation is not effective until the next rolling deployment (this is documented operational behavior — FR-045s).
- What happens if the **Redis auth token** rotation completes (old token removed) before all running pods have restarted? Pods using the old token lose Redis connectivity. Mitigation: the two-token window (SET then ROTATE) keeps both old and new active during the window, and a rolling restart is coordinated within that window.
- What happens if the **reconciler** encounters a transient Batch API outage? It backs off — does not mark jobs as failed on incomplete information. It logs the degradation and retries on the next cycle.
- What happens if two **reconciler instances** run concurrently? Safe — each run is a full scan, appends are idempotent via `(job_id, sequence)` unique key, and the reconciler re-checks the latest event before appending.
- What happens if a **final RDS snapshot** is taken but the stack is re-deployed from scratch (not restore)? The old snapshot is a standalone resource — it is NOT automatically cleaned up by a new deploy. The operator must manually delete it to avoid ongoing costs.
- What happens if `deploy restore` is run without providing `--snapshot`? The command fails with a clear error: `--snapshot <id> is required`.
- What happens if the **snapshot specified for restore no longer exists**? The CloudFormation stack creation fails with an error indicating the snapshot was not found. The command outputs the failure and the stack is rolled back.

## Requirements

### Functional Requirements

- **FR-044a — Reconciler operating parameters**: The reconciler MUST be specified precisely:
  - **Period**: runs on a fixed schedule, default every 60 seconds, configurable via `ANVIL_RECONCILER_INTERVAL_SECONDS`. The grace period before declaring a non-terminal job dead is separately configurable (default 300s) via `ANVIL_RECONCILER_GRACE_SECONDS`.
  - **Stateless**: the reconciler holds NO in-memory state between runs. Each run is a full scan of non-terminal jobs from PostgreSQL. A reconciler crash mid-run causes no corruption — the next run re-scans from scratch. It MUST be safe to run multiple reconciler instances concurrently (idempotent appends via `(job_id, sequence)` unique key).
  - **Idempotency / race with live pods**: before appending a terminal `failed` event, the reconciler MUST re-check the latest `job_events` sequence for that job to avoid racing a healthy pod that is actively writing. If a newer event appeared since the scan began, the reconciler skips that job this cycle. The `(job_id, sequence)` unique constraint is the final guard — a duplicate append is rejected by the DB, not silently doubled.
  - **Dependency degradation backoff**: the reconciler reads four surfaces (Batch API, PostgreSQL, S3, MLflow). If ANY surface returns errors/throttling, the reconciler MUST back off and NOT mark jobs as failed on incomplete information — a transient Batch API outage MUST NOT cause healthy jobs to be reaped. It logs the degradation and retries on the next cycle.
  - **Heartbeat**: the reconciler MUST emit a heartbeat metric/log each cycle so Alertmanager can detect a dead reconciler (FR-054e dead-man's switch).
  (FR-044a)

- **FR-045q — Redis high availability**: The ElastiCache Redis cluster MUST be deployed in **Multi-AZ mode with automatic failover** (a replication group with at least one replica in a second AZ). A single-AZ Redis is NOT acceptable — Redis is the live SSE delivery path and its loss degrades all active streams. Failover MUST be transparent to the web tier via the ElastiCache primary endpoint.

- **FR-045r — Server-signaled SSE degradation**: When the serving web replica cannot establish or loses its Redis subscription (Redis outage, failover in progress), the SSE handler MUST send an explicit `event: degraded` SSE message instructing the browser client to switch to polling `GET /v1/training/{job_id}/events?since=` immediately, rather than waiting for the client-side `onerror` heuristic. When Redis recovers, the server MAY send `event: live` to allow the client to resume SSE. This makes degradation deterministic (server-driven) rather than relying solely on client timeout heuristics (FR-045b). Both paths read the same `job_events` source of truth, so no metrics are lost during the Redis outage — they are replayed from `job_events` on the next poll or `Last-Event-ID` cycle. (FR-045r)

- **FR-045s — Secret rotation discipline**: Rotation of the injected secrets (Redis auth token, SSE signing secret, OAuth client secrets) MUST be specified, not hand-waved:
  - **ECS `secrets:` injection happens at task launch** — rotating a Secrets Manager value does NOT affect running tasks until they restart. Rotation therefore requires a rolling ECS deployment to propagate. This is documented operational behavior.
  - **SSE signing secret dual-key window**: the SSE signed token (FR-020) MUST be verified against BOTH the current and the previous signing secret during a rotation overlap window. The secret is stored as a small JSON set `{current, previous}` in Secrets Manager. On rotation, `current` becomes `previous` and a new `current` is generated; tokens signed with either verify until the next rotation. This prevents rotation from instantly invalidating all in-flight SSE streams. Verification tries `current` first, then `previous`.
  - **Redis auth token**: ElastiCache supports two-token rotation (SET then ROTATE) so the cluster accepts both old and new during the window. Rotation MUST use this two-step flow plus a rolling web/compute restart.
  - A rotation does NOT affect DB access (IAM auth, no static DB secret — FR-045c).
  (FR-045s)

- **FR-058 — RDS backups**: The RDS PostgreSQL instance MUST have automated backups enabled by default (backup retention ≥ 7 days, configurable) and point-in-time recovery (PITR) enabled. These are first-class CDK construct settings, not manual console actions. The `instance_size` setting MAY scale retention.
  > **Boundary note**: The CDK construct wiring for RDS backup retention and PITR is owned by spec 033 (CDK Infrastructure). This spec owns the **validation** that these settings produce working backups and the **chaos testing** that confirms PITR recovers data correctly.

- **FR-059 — S3 versioning**: Both data buckets (`anvil-data-{env}`, `anvil-ml-{env}`) MUST have S3 versioning enabled by default so accidental overwrites/deletes are recoverable. A lifecycle policy MUST expire noncurrent versions after a configurable window (default 30 days) to bound storage cost.
  > **Boundary note**: The CDK construct wiring for S3 versioning and lifecycle policies is owned by spec 033. This spec owns the **validation** that versioning is enabled and object recovery works as expected.

- **FR-060 — Destroy safety**: The `anvil deploy destroy` command MUST, before deleting any resource: (1) warn that ALL data including RDS backups and S3 versions will be permanently lost, (2) offer to take a final RDS snapshot (`--final-snapshot` flag, default prompt), (3) require typing the stack name to confirm (unless `--force`). When a final snapshot is requested, the CFN deletion MUST use `DeletionPolicy: Snapshot` on the RDS instance so the snapshot survives stack deletion. The user MUST be told the snapshot name and that it incurs ongoing storage cost until manually deleted.
  > **Boundary note**: The deploy CLI implementation for `destroy --final-snapshot` is owned by spec 034 (Deploy CLI). This spec owns the **validation** that the safety flow works correctly — that prompts appear, that the snapshot survives stack deletion, and that the user is informed.

- **FR-061 — Recovery documentation**: The deploy CLI MUST provide an `anvil deploy restore --snapshot <id>` command (or documented runbook) to stand up a new stack from an RDS snapshot, for disaster recovery. Cross-region replication is a documented post-v1 option, not a v1 default.
  > **Boundary note**: The deploy CLI implementation for `restore --snapshot` is owned by spec 034. This spec owns the **validation** of the DR flow and the **quickstart DR runbook** (see [[037 SaaS Resilience DR - quickstart]]).

### Success Criteria (SC subset relevant to resilience)

- **SC-012**: A training job that loses its compute pod mid-run is detected and reconciled to a terminal state (`failed` or recovered) within the configured grace period — no job remains stuck in `running` indefinitely.
- **SC-002**: Training metrics appear in the browser within 1 second of the compute pod reporting them (SSE latency via Redis pub/sub). Degraded mode (polling) is slower but always reachable.

### Key Entities

- **SSESigningSecret**: A small JSON structure stored in Secrets Manager: `{"current": "...", "previous": "..."}`. The `current` key signs new SSE tokens. During rotation, `current` moves to `previous` and a fresh `current` is generated. Verification tries `current` first, then `previous`. See [[037 SaaS Resilience DR - data-model]].
- **RedisAuthToken**: Managed via ElastiCache's two-token rotation (SET then ROTATE). The cluster accepts both old and new tokens during the rotation window. See [[037 SaaS Resilience DR - data-model]].
- **FinalRDSDBSnapshot**: An RDS DB snapshot taken before stack destruction, identified by `{stack-name}-final-{yyyymmdd}`. Survives CloudFormation stack deletion via `DeletionPolicy: Snapshot`. Incurs storage cost until manually deleted.
- **Reconciler**: A stateless, scheduled task that scans non-terminal jobs and reconciles them against Batch, S3, and MLflow state. See FR-044a for full operating parameters. Implemented in spec 032; hardened and chaos-tested here.

### Assumptions

- The CDK stack owns the **construct-level** settings (RDS `BackupRetentionPeriod`, `DeletionPolicy`, S3 `VersioningConfiguration`, ElastiCache `AutomaticFailoverEnabled`). This spec validates those settings at deployment time and tests the behavior under fault conditions.
- The deploy CLI owns the **command-level** implementation (`destroy --final-snapshot`, `restore --snapshot`). This spec validates the safety and DR flows.
- Redis Multi-AZ failover is configured by the CDK construct (spec 033). This spec validates that failover is transparent and that SSE degrades gracefully.
- The SSE `event: degraded` and `event: live` server signaling is implemented in the SSE handler owned by spec 032 (Training Pipeline). This spec tests the signaling under Redis outage scenarios.
- The reconciler is implemented in spec 032. This spec adds chaos tests for crash-recovery and dependency degradation.
- Secret rotation is an operational procedure documented here. The runtime dual-key verification logic for SSE tokens is implemented in the auth layer (spec 030/032) and tested here.
- RDS PITR restores to any point within the retention window. `deploy restore` restores from a specific named snapshot (not PITR). PITR is available via the AWS console/CLI for in-place recovery.
- S3 versioning recovers overwrites and deletes within the noncurrent-version lifecycle window (default 30 days). Recovery is via the AWS S3 console or CLI — the application does not expose an S3 version browser.

## Acceptance Gates

### Gate G10 — Resilience & DR Gate

Copied verbatim from the umbrella spec (016 SaaS Architecture). This spec implements and validates all G10 criteria.

| ID | Criterion | Verification | Pass Condition |
|----|-----------|--------------|----------------|
| G10.1 | RDS automated snapshots enabled | AWS API: `rds.describe_db_instances` | `BackupRetentionPeriod` ≥ 7 |
| G10.2 | S3 data buckets versioned | AWS API: `s3.get_bucket_versioning` | Status `Enabled` |
| G10.3 | Redis Multi-AZ enabled | AWS API: `elasticache.describe_replication_groups` | `AutomaticFailover` enabled |
| G10.4 | SSE degrades to polling on Redis loss | Chaos: block Redis, observe client | Client falls back to polling, curve still updates |
| G10.5 | Reconciler recovers after its own crash | Chaos: kill reconciler mid-scan, restart | No jobs left non-terminal beyond grace |
| G10.6 | Destroy warns before deleting backups | Run `deploy destroy`, inspect prompt | Prompt offers final snapshot, warns on data loss |

> **G10.1–G10.3** are AWS control-plane validation checks (layer 1 of the verify pyramid), run as `anvil deploy verify --layer infra` extensions. **G10.4–G10.5** are chaos tests run against a deployed or docker-compose stack. **G10.6** is a deploy CLI safety test (layer 2, API canary).

## Architecture Decisions

### AD-16: Production Posture — Single-Region Multi-AZ HA + Backup/DR

**Decision**: Single-region multi-AZ HA (RDS Multi-AZ + PITR, Redis Multi-AZ failover, S3 versioning), backup/DR with destroy-time final snapshot + `deploy restore`, secret-rotation dual-key window, reconciler operating parameters (FR-044a, FR-045q–s, FR-058–061). No cross-region failover in v1.

**Rationale**: Production trust is non-negotiable, but cross-region is over-engineering for v1. All HA settings are default-on CDK constructs. The dual-key rotation window prevents secret rotation from breaking in-flight SSE streams. The reconciler's stateless design and dependency-degradation backoff ensure it is safe under fault conditions. Destroy-time final snapshot and `deploy restore` provide minimum viable DR.

## References

- [[037 SaaS Resilience DR - data-model|Data Model]] — secret dual-key structure, backup/snapshot inventory
- [[037 SaaS Resilience DR - plan|Implementation Plan]]
- [[037 SaaS Resilience DR - tasks|Task Breakdown]]
- [[037 SaaS Resilience DR - quickstart|DR Runbook Quickstart]]
- [[Reference/SaaSArchitectureDecisions|SaaS Architecture Decisions]] — AD-16
- [[Specs/033 SaaS CDK Infrastructure/033 SaaS CDK Infrastructure - spec|033 CDK Infrastructure Spec]] — construct-level RDS/S3/Redis settings
- [[Specs/034 SaaS One-Command Deploy/034 SaaS One-Command Deploy - spec|034 Deploy CLI Spec]] — destroy/restore commands
- [[Specs/032 SaaS Training Pipeline/032 SaaS Training Pipeline - spec|032 Training Pipeline Spec]] — reconciler implementation
- [[Specs/036 SaaS Observability MLflow Proxy/036 SaaS Observability MLflow Proxy - spec|036 Observability Spec]] — alerting on failover