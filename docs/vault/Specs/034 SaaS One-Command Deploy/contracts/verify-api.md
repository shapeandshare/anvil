---
title: Verify Layer 2 — API Canary
type: spec
tags:
  - type/spec
  - domain/infrastructure
  - domain/operations
created: '2026-06-27'
updated: '2026-06-27'
---

# Verify Layer 2 — API Canary (`--layer api`)

**Contract**: Headless end-to-end validation of the full SaaS pipeline. Uses Cognito admin APIs to create + authenticate a test user. No browser interaction. Each step is an independent assertion with clear pass/fail. The layer exits non-zero on any failure and reports which step failed. All test resources are cleaned up on completion (or best-effort on failure).

## Canary Flow

### Step 1-2: Auth Setup

| # | Action | API | Assertion |
|---|--------|-----|-----------|
| 1 | Create native Cognito test user | `cognito-idp.admin-create-user` + `admin-set-password` | User exists, password set |
| 2 | Authenticate and obtain JWT | `cognito-idp.admin-initiate-auth` (ADMIN_USER_PASSWORD_AUTH) | JWT returned, no error |

### Step 3-5: Application Access

| # | Action | API | Assertion |
|---|--------|-----|-----------|
| 3 | Health check with JWT | `GET /v1/health` (Authorization: Bearer <jwt>) | HTTP 200 |
| 4 | Create test org + team | `POST /v1/organizations`, `POST /v1/teams` | RBAC rows created |
| 5 | Upload tiny corpus via signed URL | `POST /v1/corpora` (signed URL upload) | S3 object + DB row present |

### Step 6-8: Training Pipeline

| # | Action | API | Assertion |
|---|--------|-----|-----------|
| 6 | Submit CPU training job (1 layer, 20 steps) | `POST /v1/training/start` | TrainingJob row created, Batch job submitted |
| 7 | Open SSE stream with signed token | `GET /v1/training/stream/{id}?token=...` | ≥1 metrics event received |
| 8 | Poll job to completion | `GET /v1/training/{id}` | status=completed |

### Step 9-11: Artifact + Usage + RBAC

| # | Action | API | Assertion |
|---|--------|-----|-----------|
| 9 | Assert model artifact in S3 + MLflow | `s3.head_object` + MLflow search API | Artifact exists, run finalized |
| 10 | Assert usage record created | `GET /v1/usage?org_id=...` | Record with correct org_id/user_id/gpu_seconds |
| 11 | RBAC negative test | Second user in different org calls `GET /v1/corpora` | HTTP 403 — cannot read first org's corpus |

### Step 12: Cleanup

| # | Action | API | Assertion |
|---|--------|-----|-----------|
| 12 | Delete test resources + test Cognito user | Various + `cognito-idp.admin-delete-user` | Cleanup succeeds (best-effort on failure) |

## Implementation Notes

- Layer 2 implicitly validates Layer 1 (infra must be healthy for API calls to work)
- The `--layer api` flag runs Layer 1 first, then proceeds to Layer 2
- Training job is deliberately tiny (1 layer, 20 steps) to minimize canary wall time
- If a step fails, the canary reports the failing step number + detail and exits non-zero
- Cleanup runs even on failure (best-effort — some resources may require manual cleanup)