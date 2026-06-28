---
title: 037 SaaS Resilience DR - research
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

# Research: SaaS Resilience & Disaster Recovery

## Sources

Primary sources for this research:
- [[Specs/016 SaaS Architecture/016 SaaS Architecture - spec|016 Umbrella Spec]] — FR-044a, FR-045q, FR-045s, FR-058–061, Gate G10
- [[Specs/016 SaaS Architecture/016 SaaS Architecture - plan|016 Plan]] — Phase 13
- [[Reference/SaaSArchitectureDecisions|SaaS Architecture Decisions]] — AD-16
- AWS ElastiCache Multi-AZ documentation
- AWS Secrets Manager rotation documentation
- AWS RDS automated backups and PITR documentation
- AWS S3 versioning and lifecycle policy documentation

## Research Findings

### R1 — Redis Multi-AZ Failover Mechanics
ElastiCache Redis (cluster mode disabled) supports Multi-AZ with automatic failover when configured as a replication group with ≥1 replica in a different AZ. On primary failure:
- The replica in the other AZ is promoted to primary.
- The primary endpoint (DNS name) is updated to point to the new primary. DNS TTL is 60s by default, but ElastiCache manages failover within 30–120s typically.
- Clients using the primary endpoint reconnect transparently.
- The web tier's Redis client (redis-py) must handle connection drops gracefully. With `health_check_interval` and connection retry, the reconnect is transparent after the DNS update propagates.
- During the failover window (typically 10–30s), Redis is unavailable. SSE streams stall. This is why `event: degraded` and polling fallback are essential — they fill the gap deterministically rather than relying on client-side SSE timeout heuristics.
- **Decision**: The SSE handler MUST detect the Redis connection loss and send `event: degraded` before the client's EventSource `onerror` fires. The `redis-py` `connection_error` callback or a health-check failure is the trigger.

### R2 — SSE `event: degraded` Signaling Mechanism
The SSE protocol allows named events via `event:` and `data:` fields. The client-side `EventSource` API dispatches named events via `addEventListener('degraded', ...)`. Implementation:
- Server sends: `event: degraded\ndata: {"fallback": "polling", "since": <sequence>}\n\n`
- Client listens: `eventSource.addEventListener('degraded', handler)`
- On degraded: client stores the `since` sequence, switches to polling `GET /v1/training/{job_id}/events?since=`
- On live: `event: live\ndata: {}\n\n` → client resumes SSE from the last sequence.

### R3 — SSE Signing Secret Dual-Key Window
Storing the secret as a JSON object `{"current": "...", "previous": ""}` in Secrets Manager:
- Secrets Manager supports automatic rotation via a Lambda function. The rotation Lambda reads the current secret, generates a new `current`, sets `previous` to the old `current`, and writes back.
- Verification: try `hmac.compare_digest(token, hmac.new(current, ...))` first; if comparison fails, try `hmac.compare_digest(token, hmac.new(previous, ...))`. Accept if either matches.
- Window expiry: the `previous` key is cleared after a configurable TTL (default: `ANVIL_SSE_ROTATION_WINDOW_SECONDS`, default 300s = 5 minutes). This gives in-flight streams time to reauthenticate with a new token.
- A garbage-collection mechanism in the rotation Lambda (or a sidecar process) clears `previous` after the window.

### R4 — Redis Auth Token Two-Token Rotation
ElastiCache Redis supports the `AUTH` token rotation via:
1. `aws elasticache modify-replication-group --auth-token <new-token>` — the cluster accepts BOTH the old and new token during the transition.
2. Each connected client can switch to the new token at its own pace.
3. Once all clients are migrated, the old token can be retired.
- For anvil: the web tier tasks and any compute pods using Redis must be restarted (rolling deploy) to pick up the new token from Secrets Manager. The two-token window allows this to happen without a service interruption.
- The window is bounded by the ElastiCache transition period (default: the operation completes immediately; the old token remains accepted until explicitly removed via `reset-auth-token`).

### R5 — Reconciler Stateless Design Safety
The reconciler's stateless design (FR-044a) is critical for crash safety:
- **No in-memory cursor**: each run is `SELECT * FROM training_jobs WHERE status NOT IN ('completed', 'failed', 'cancelled')`.
- **Idempotent appends**: `INSERT INTO job_events (job_id, sequence, ...) VALUES (...) ON CONFLICT (job_id, sequence) DO NOTHING`.
- **Race detection**: before appending a terminal event, the reconciler re-queries the latest sequence for the job. If it has advanced since the scan began, skip this cycle.
- **Backoff**: errors from any of the four read surfaces (Batch, DB, S3, MLflow) cause the reconciler to log and skip, not fail open.

### R6 — RDS Automated Snapshots and PITR
- Automated backups are enabled by default when `BackupRetentionPeriod > 0`.
- PITR restores a DB instance to any point within the retention window (1 second granularity).
- RDS snapshot export to S3 is available for cross-account/cross-region backup but incurs additional cost.
- RDS snapshots (manual and automated) incur standard RDS snapshot storage costs.
- The `DeletionPolicy: Snapshot` CloudFormation attribute causes the RDS instance to be snapshotted before deletion and the snapshot to survive stack deletion.

### R7 — S3 Versioning and Lifecycle
- S3 versioning is a bucket-level setting. Once enabled, it cannot be disabled — only suspended.
- Object versions accrue storage costs. A lifecycle policy is essential to expire noncurrent versions.
- The default lifecycle rule: `NoncurrentVersionExpirationInDays = 30`.
- Object recovery: the user restores a previous version via the AWS S3 console (Show Versions → select version → Download) or CLI (`aws s3api get-object --version-id`).

### R8 — Boundary Clarity with Specs 033 and 034
Research confirms the clean boundary:
- **Spec 033 (CDK Infrastructure)**: owns the CDK L2 construct properties for RDS `BackupRetentionPeriod`, `DeletionPolicy`, S3 `VersioningConfiguration`, ElastiCache `AutomaticFailoverEnabled`, and `MultiAZEnabled`.
- **Spec 034 (Deploy CLI)**: owns the `destroy --final-snapshot` CLI implementation and the `restore --snapshot` CLI implementation.
- **This spec (037)**: owns the **validation** that these settings produce correct behavior, the **chaos tests** that stress them under fault conditions, and the **dual-key rotation logic** for the SSE signing secret.

## Open Questions

1. **ElastiCache failover trigger for chaos tests**: What is the safest way to trigger a failover in a dev environment? `aws elasticache test-failover` (cluster mode only) or rebooting the primary node. For docker-compose, stopping the Redis container is equivalent.
2. **Two-token rotation for Redis auth token**: Does ElastiCache support a true `SET then ROTATE` sequence where both tokens are simultaneously valid? AWS documentation confirms: modify the replication group with a new `--auth-token`, and the cluster accepts both old and new until the transition completes. This is the recommended approach.
3. **RDS snapshot cost**: Final snapshots taken by `DeletionPolicy: Snapshot` incur RDS snapshot storage costs ($0.095/GB-month for standard). The user should be informed of this cost during the destroy prompt.

## References

- AWS: [ElastiCache Multi-AZ](https://docs.aws.amazon.com/AmazonElastiCache/latest/red-ug/AutoFailover.html)
- AWS: [Secrets Manager Rotation](https://docs.aws.amazon.com/secretsmanager/latest/userguide/rotating-secrets.html)
- AWS: [RDS Automated Backups](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_WorkingWithAutomatedBackups.html)
- AWS: [S3 Versioning](https://docs.aws.amazon.com/AmazonS3/latest/userguide/Versioning.html)
- [[Specs/033 SaaS CDK Infrastructure/033 SaaS CDK Infrastructure - spec|033 CDK Infrastructure Spec]]
- [[Specs/034 SaaS One-Command Deploy/034 SaaS One-Command Deploy - spec|034 Deploy CLI Spec]]
- [[Specs/032 SaaS Training Pipeline/032 SaaS Training Pipeline - spec|032 Training Pipeline Spec]]
- [[Specs/036 SaaS Observability MLflow Proxy/036 SaaS Observability MLflow Proxy - spec|036 Observability Spec]]