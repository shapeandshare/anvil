---
title: 037 SaaS Resilience DR - data-model
type: data-model
tags:
  - type/spec
spec-refs:
  - docs/vault/Specs/037 SaaS Resilience DR/
related:
  - '[[037 SaaS Resilience DR]]'
created: '2026-06-27'
updated: '2026-06-27'
---

# Data Model: SaaS Resilience & DR

This model covers the secret dual-key rotation structure, the backup/snapshot inventory, and the RDS/S3 resilience configuration state.

## SSE Signing Secret — Dual-Key Rotation

### Secrets Manager Secret Structure

Stored in AWS Secrets Manager as a single secret (`anvil/sse-signing-secret`). Plan text value:

```json
{
  "current": "base64-encoded-256-bit-key-current",
  "previous": "base64-encoded-256-bit-key-previous"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `current` | `str` (base64, 256-bit) | Active key — signs new SSE tokens. Verification tries this first. |
| `previous` | `str` (base64, 256-bit, nullable) | Previous key — accepted during rotation overlap window. Cleared after window expiry. |

### Lifecycle

```
Initial state: {current: "key-A", previous: ""}
          ↓
Rotation: {current: "key-B", previous: "key-A"}
          ↓
Window expiry: {current: "key-B", previous: ""}
```

### Rotation Procedure

1. Read current secret: `{current, previous}`
2. Validate `current` is a valid 256-bit key
3. Set `new_previous = current`
4. Generate `new_current` (32 bytes from `os.urandom`, base64-encoded)
5. Write back: `{current: new_current, previous: new_previous}`
6. Start timer for window expiry (`ANVIL_SSE_ROTATION_WINDOW_SECONDS`)
7. After window expires, write: `{current: new_current, previous: ""}`

### Token Verification

```python
def verify_sse_token(token: str, secret: dict) -> bool:
    """Verify an SSE signed token against the dual-key secret.

    Tries current first, then previous. Returns True if either matches.
    """
    for key in (secret["current"], secret.get("previous", "")):
        if not key:
            continue
        expected = hmac.new(
            base64.b64decode(key),
            token.encode(),
            hashlib.sha256,
        ).hexdigest()
        if hmac.compare_digest(token, expected):
            return True
    return False
```

## Redis Auth Token — Two-Token Rotation

### ElastiCache State

Managed by ElastiCache's internal two-token rotation mechanism. Not stored as an application-side data structure, but documented here for reference.

| Mechanism | Description |
|-----------|-------------|
| Active token | The current `AUTH` token accepted by the Redis cluster |
| Transition window | After `modify-replication-group --auth-token <new>`, both old and new tokens are accepted |
| Propagation | A rolling ECS deployment restarts tasks to pick up the new token from Secrets Manager |
| Window closure | Old token is no longer accepted after the transition completes (no explicit `reset-auth-token` needed) |

### ECS Task Secret Injection

```yaml
# Task definition secrets: section
secrets:
  - name: REDIS_AUTH_TOKEN
    valueFrom: arn:aws:secretsmanager:us-east-1:...:anvil/redis-auth-token
  - name: SSE_SIGNING_SECRET
    valueFrom: arn:aws:secretsmanager:us-east-1:...:anvil/sse-signing-secret
```

> **Note**: Secrets are injected at task launch only. A rolling ECS deployment is required to propagate rotated values to running tasks.

## Backup & Snapshot Inventory

### RDS Automated Backups

| Property | Value |
|----------|-------|
| Service | RDS PostgreSQL |
| Method | Automated backups (continuous, transactionally consistent) |
| Retention | `BackupRetentionPeriod` ≥ 7 days (configurable) |
| PITR | Enabled (restore to any point within retention window, 1-second granularity) |
| Construct owner | Spec 033 (CDK Infrastructure) |
| Validation | Spec 037 (`deploy verify --layer infra` — T001) |

### RDS Manual / Final Snapshots

| Property | Value |
|----------|-------|
| Source | `deploy destroy --final-snapshot` or manual `aws rds create-db-snapshot` |
| Naming pattern | `{stack-name}-final-{yyyymmdd}` (e.g., `anvil-prod-final-20260627`) |
| Survival | Survives stack deletion via `DeletionPolicy: Snapshot` |
| Cost | Standard RDS snapshot storage ($0.095/GB-month) — persists until manually deleted |
| DR use | Source for `deploy restore --snapshot <id>` |

### S3 Versioning

| Property | Value |
|----------|-------|
| Buckets | `anvil-data-{env}`, `anvil-ml-{env}` |
| Versioning status | `Enabled` |
| Noncurrent version expiry | 30 days (configurable lifecycle policy) |
| Recovery | Via AWS S3 console (Show Versions) or CLI (`aws s3api get-object --version-id`) |
| Construct owner | Spec 033 (CDK Infrastructure) |
| Validation | Spec 037 (`deploy verify --layer infra` — T002) |

### Redis Backup / Snapshot

Redis snapshots are NOT part of the resilience data model because:
- Redis is delivery-only (FR-045r / AD-4) — the source of truth is `job_events` in PostgreSQL.
- Redis data is ephemeral; no critical state is stored only in Redis.
- ElastiCache snapshots are available for Redis but not required for DR.
- On Redis loss, SSE degrades to polling, `job_events` replay fills any gap.

## Configuration Parameters

| Parameter | Default | Description | Set via |
|-----------|---------|-------------|---------|
| `ANVIL_RECONCILER_INTERVAL_SECONDS` | 60 | Reconciler scan period | Env var / deploy config |
| `ANVIL_RECONCILER_GRACE_SECONDS` | 300 | Grace period before declaring a non-terminal job dead | Env var / deploy config |
| `ANVIL_SSE_ROTATION_WINDOW_SECONDS` | 300 | Duration the previous SSE signing secret is accepted after rotation | Env var / deploy config |
| `rds_backup_retention_days` | 7 | RDS automated backup retention | CDK construct parameter (spec 033) |
| `s3_noncurrent_version_expiry_days` | 30 | S3 lifecycle: expire noncurrent versions after N days | CDK construct parameter (spec 033) |

## See Also

- [[037 SaaS Resilience DR - spec|Spec]] — full FR definitions for resilience
- [[037 SaaS Resilience DR - quickstart|DR Runbook]] — operational procedures
- [[Specs/033 SaaS CDK Infrastructure/033 SaaS CDK Infrastructure - data-model|033 CDK Infrastructure Data Model]] — CDK construct parameters
- [[Specs/034 SaaS One-Command Deploy/034 SaaS One-Command Deploy - data-model|034 Deploy CLI Data Model]] — deploy config for destroy/restore