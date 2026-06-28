---
title: Verify Layer 1 — Infra Checks
type: spec
tags:
  - type/spec
  - domain/infrastructure
created: '2026-06-27'
updated: '2026-06-27'
---

# Verify Layer 1 — AWS Control-Plane Checks (`--layer infra`)

**Contract**: Every check MUST be a discrete `boto3` API call with a clear pass/fail. The layer exits non-zero on any failure and reports which check failed.

## Check List

| # | Check | AWS API | Pass Condition |
|---|-------|---------|----------------|
| 1 | Stack status | `cloudformation.describe_stacks` | `CREATE_COMPLETE` or `UPDATE_COMPLETE` |
| 2 | ECS web service | `ecs.describe_services` | `runningCount == desiredCount`, steady state |
| 3 | ECS MLflow service | `ecs.describe_services` | Healthy |
| 4 | Batch CPU compute env | `batch.describe_compute_environments` | `VALID` + `ENABLED` |
| 5 | Batch GPU compute env | `batch.describe_compute_environments` | `VALID` + `ENABLED` |
| 6 | Batch job queues | `batch.describe_job_queues` | `VALID` + `ENABLED` |
| 7 | RDS instance | `rds.describe_db_instances` | `available` |
| 8 | ElastiCache | `elasticache.describe_replication_groups` | `available` |
| 9 | S3 data bucket | `s3.head_bucket` + `get_bucket_policy` | Exists, correct policy |
| 10 | S3 MLflow bucket | `s3.head_bucket` | Exists |
| 11 | Cognito pool | `cognito-idp.describe_user_pool` | Exists, email sign-in enabled |
| 12 | Secrets | `secretsmanager.describe_secret` | All required secrets present |
| 13 | Stack outputs | `cloudformation.describe_stacks` Outputs | CloudFront URL, auth domain resolvable |

## Implementation Notes

- Uses the same `boto3.Session` as the deploy command (region-resolved from deploy config)
- No auth token needed beyond AWS credentials
- Each check is independent — failure of one does not stop others
- Output is a JSON list of `{name, passed, detail}` for `--json` mode