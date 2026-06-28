---
title: 037 SaaS Resilience DR - quickstart
type: reference
tags:
  - type/reference
  - domain/infrastructure
  - domain/operations
spec-refs:
  - docs/vault/Specs/037 SaaS Resilience DR/
related:
  - '[[037 SaaS Resilience DR]]'
created: '2026-06-27'
updated: '2026-06-27'
---

# DR Runbook: SaaS Resilience & Disaster Recovery

## Table of Contents

1. [Restore from Snapshot (Primary DR Path)](#restore-from-snapshot-primary-dr-path)
2. [Point-in-Time Recovery (In-Place)](#point-in-time-recovery-in-place)
3. [S3 Object Recovery via Versioning](#s3-object-recovery-via-versioning)
4. [SSE Signing Secret Rotation](#sse-signing-secret-rotation)
5. [Redis Auth Token Rotation](#redis-auth-token-rotation)
6. [Reconciler Health Check](#reconciler-health-check)
7. [Expected Recovery Times](#expected-recovery-times)

---

## Restore from Snapshot (Primary DR Path)

Use when: the entire stack is destroyed or corrupted and you need to recover from a known-good RDS snapshot.

### Prerequisites
- AWS credentials with sufficient permissions (AdministratorAccess or equivalent)
- `anvil` installed with `[aws]` extra: `pip install anvil[aws]`
- An RDS snapshot exists (final snapshot from `deploy destroy --final-snapshot`, or a manual snapshot)

### Steps

```bash
# 1. Verify the snapshot exists
aws rds describe-db-snapshots --db-snapshot-identifier anvil-prod-final-20260627

# 2. Restore
anvil deploy restore --snapshot anvil-prod-final-20260627
```

### What Happens

1. A new CloudFormation stack is created.
2. The RDS instance is restored from the specified snapshot.
3. All other infrastructure (ECS, Redis, S3, etc.) is created fresh.
4. Admin credentials are regenerated and output to the console.
5. The new CloudFront URL is output.

### Important Notes

- The restore creates a **new** stack — it does not modify an existing one.
- S3 data (model artifacts, corpora, datasets) is **not** restored from the snapshot — it must be separately recovered via S3 versioning if needed.
- Cross-region snapshots must be copied to the target region before running restore.
- The restored stack has a **new** CloudFront URL and admin credentials.

---

## Point-in-Time Recovery (In-Place)

Use when: the RDS instance is corrupted but the rest of the stack is healthy, and you need to revert to a specific point within the retention window.

### Prerequisites
- RDS automated backups enabled with retention ≥ 7 days
- The corruption is limited to the database (ECS, Redis, S3 are unaffected)

### Steps

```bash
# 1. Determine the target restore time (use the moment before corruption)
#    Format: YYYY-MM-DD HH:MM:SS (UTC)

# 2. Restore from PITR via AWS CLI
aws rds restore-db-instance-to-point-in-time \
  --source-db-instance-identifier anvil-prod \
  --target-db-instance-identifier anvil-prod-pitr \
  --restore-time "2026-06-27 14:30:00"

# 3. Verify the restored instance is healthy
aws rds describe-db-instances --db-instance-identifier anvil-prod-pitr

# 4. Update the deploy configuration to point to the new instance
anvil deploy config set db-instance anvil-prod-pitr

# 5. Perform a rolling update to reconnect services
anvil deploy update
```

### Important Notes
- PITR creates a **new** DB instance — you must update your deploy config and redeploy.
- The original corrupted instance can be deleted after verification.
- PITR is an AWS console/CLI operation — it is not exposed through the deploy CLI.

---

## S3 Object Recovery via Versioning

Use when: a file was accidentally overwritten or deleted, and you need to recover a previous version.

### Prerequisites
- S3 versioning enabled on `anvil-data-{env}` and `anvil-ml-{env}`
- The overwrite/delete occurred within the noncurrent-version lifecycle window (default 30 days)

### Steps

```bash
# 1. List versions of the object
aws s3api list-object-versions \
  --bucket anvil-data-prod \
  --prefix orgs/{org_id}/corpora/{corpus_id}/raw/input.txt

# 2. Identify the version ID you want to restore
#    (Look for the VersionId of the version before the delete marker or overwrite)

# 3. Download the specific version
aws s3api get-object \
  --bucket anvil-data-prod \
  --key orgs/{org_id}/corpora/{corpus_id}/raw/input.txt \
  --version-id <version-id> \
  recovered-file.txt

# 4. Re-upload as the current version (or copy in-place)
aws s3 cp recovered-file.txt s3://anvil-data-prod/orgs/{org_id}/corpora/{corpus_id}/raw/input.txt
```

### Important Notes
- Versioning cannot be disabled once enabled — it can only be suspended.
- Each version incurs storage cost. The lifecycle policy (30-day expiry) bounds this.
- The application does not expose an S3 version browser — recovery is via AWS CLI/console.

---

## SSE Signing Secret Rotation

Use when: the SSE signing secret is compromised (security incident) or as a routine rotation.

### Prerequisites
- AWS credentials with Secrets Manager write access
- `anvil-sse-signing-secret` secret exists in Secrets Manager

### Rotation Window

The rotation uses a dual-key window where the previous key remains valid for `ANVIL_SSE_ROTATION_WINDOW_SECONDS` (default: 300 seconds / 5 minutes). During this window, in-flight SSE streams continue to work.

### Steps

#### Automatic (via Secrets Manager rotation Lambda, if configured)

```bash
# Trigger rotation
aws secretsmanager rotate-secret --secret-id anvil/sse-signing-secret
```

#### Manual

```bash
# 1. Read current secret
CURRENT=$(aws secretsmanager get-secret-value \
  --secret-id anvil/sse-signing-secret \
  --query SecretString --output text)

# 2. Extract current key, generate new key
NEW_KEY=$(openssl rand -base64 32)
PREVIOUS_KEY=$(echo $CURRENT | jq -r '.current')

# 3. Write rotated secret with dual-key window
aws secretsmanager put-secret-value \
  --secret-id anvil/sse-signing-secret \
  --secret-string "{\"current\": \"$NEW_KEY\", \"previous\": \"$PREVIOUS_KEY\"}"

# 4. After the window expires (default 5 min), clear previous key
sleep 300
aws secretsmanager put-secret-value \
  --secret-id anvil/sse-signing-secret \
  --secret-string "{\"current\": \"$NEW_KEY\", \"previous\": \"\"}"
```

### Verification

```bash
# After rotation, verify existing SSE streams are still accepted:
# (Run this as a test — open a dashboard with an SSE stream)
# The stream should continue uninterrupted during the 5-minute window.
echo "SSE signing secret rotated. Dual-key window active for 5 minutes."
```

---

## Redis Auth Token Rotation

Use when: the Redis auth token is compromised or as a routine rotation.

### Prerequisites
- AWS credentials with ElastiCache modify and Secrets Manager write access
- The ElastiCache replication group ID (from CloudFormation outputs or `aws elasticache describe-replication-groups`)
- A rolling ECS deployment to propagate the new token to running tasks

### Steps

```bash
# 1. Generate a new auth token
NEW_TOKEN=$(openssl rand -base64 32)

# 2. Set new token (ElastiCache accepts BOTH old and new during transition)
aws elasticache modify-replication-group \
  --replication-group-id anvil-redis-prod \
  --auth-token "$NEW_TOKEN" \
  --apply-immediately

# 3. Store the new token in Secrets Manager
aws secretsmanager put-secret-value \
  --secret-id anvil/redis-auth-token \
  --secret-string "$NEW_TOKEN"

# 4. Perform a rolling ECS deployment to propagate the new token
aws ecs update-service \
  --cluster anvil-prod \
  --service anvil-web \
  --force-new-deployment

# 5. Verify both old and new tokens work during the transition
redis-cli -h <primary-endpoint> -a "$NEW_TOKEN" PING
# Should respond: PONG

# 6. After all tasks are restarted, the old token can be retired
#    (ElastiCache automatically handles token retirement after the transition)
```

### Important Notes
- The two-token window is managed by ElastiCache — there is no explicit "close window" step.
- All running ECS tasks must be restarted to pick up the new token.
- The rolling deployment ensures zero-downtime rotation.

---

## Reconciler Health Check

Use when: you suspect the reconciler is not running or is malfunctioning.

### Prerequisites
- Monitoring/observability installed (optional `[monitoring]` extra)
- Or: AWS CloudWatch Logs access

### Steps

```bash
# 1. Check for reconciler heartbeat in CloudWatch Logs
aws logs filter-log-events \
  --log-group-name /ecs/anvil-reconciler \
  --filter-pattern '"heartbeat"' \
  --limit 5

# Expected output: heartbeat log entries every ANVIL_RECONCILER_INTERVAL_SECONDS (default 60s)

# 2. If no heartbeat for > ANVIL_RECONCILER_GRACE_SECONDS (default 300s):
#    - Check the ECS service status
aws ecs describe-services \
  --cluster anvil-prod \
  --services anvil-reconciler

#    - Restart the reconciler task
aws ecs update-service \
  --cluster anvil-prod \
  --service anvil-reconciler \
  --force-new-deployment

# 3. Verify reconciler is functional
#    Check that no jobs are stuck in non-terminal state beyond grace period:
aws rds describe-db-instances  # or query PostgreSQL directly:
psql $DATABASE_URL -c "
  SELECT id, status, started_at
  FROM training_jobs
  WHERE status NOT IN ('completed', 'failed', 'cancelled')
    AND started_at < NOW() - INTERVAL '5 minutes';
"
# Expected: empty (all jobs resolved) or few jobs with expected long runtime
```

---

## Expected Recovery Times

| Scenario | Expected Time | Notes |
|----------|---------------|-------|
| Restore from final snapshot (`deploy restore`) | ~20 min | CDK deploy ~15 min + snapshot restore ~5 min |
| PITR in-place recovery | ~15 min | RDS restore ~5 min + config update + redeploy ~10 min |
| S3 object recovery (single file) | ~2 min | Via AWS CLI |
| SSE signing secret rotation | ~5 min | Rotation is instant; window is 5 min for in-flight streams |
| Redis auth token rotation | ~10 min | Token set + rolling ECS deploy (~10 min for rolling update) |
| Reconciler restart | ~2 min | ECS force-new-deployment |

## See Also

- [[037 SaaS Resilience DR - spec|Spec]] — full FR definitions
- [[037 SaaS Resilience DR - data-model|Data Model]] — secret structures and configuration parameters
- [[Specs/033 SaaS CDK Infrastructure/033 SaaS CDK Infrastructure - quickstart|033 CDK Quickstart]] — deploying infrastructure
- [[Specs/034 SaaS One-Command Deploy/034 SaaS One-Command Deploy - quickstart|034 Deploy Quickstart]] — deploy lifecycle commands