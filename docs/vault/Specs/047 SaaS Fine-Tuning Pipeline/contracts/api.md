---
title: 047 SaaS Fine-Tuning Pipeline — API Contracts
type: contract
tags:
  - type/contract
  - domain/training
  - domain/infrastructure
status: draft
created: '2026-07-02'
updated: '2026-07-02'
---

# API Contracts: SaaS Fine-Tuning Pipeline

> **MVP note (2026-07-02):** In the MVP, SaaS fine-tunes are submitted through the
> **existing** `POST /training/start` route (with `compute_backend="saas"`) and observed via
> the existing `GET /training/stream/{run_id}` SSE endpoint — no new API surface is required
> to ship the MVP. The dedicated `/saas/finetune/*` endpoints, the `429` per-org concurrency
> response, the version-mismatch/base-asset errors, and the `/usage` metering endpoint below
> are **DEFERRED** (they depend on tenancy + metering + LakeFS, which do not yet exist).
> They are documented here as the target shape for the follow-on specs.

## Base URL

All endpoints are mounted under the existing `anvil/api/v1/` router. SaaS fine-tune endpoints are prefixed with `/saas/finetune/`.

---

## POST /saas/finetune/submit

Submit a fine-tune for SaaS execution. The request body extends the existing `TrainConfig`.

### Request

```json
{
  "method": "lora",
  "base_model_ref": "tinyllama-1.1b",
  "compute_backend": "saas",
  "lora_rank": 8,
  "lora_alpha": 16,
  "lora_dropout": 0.05,
  "num_steps": 500,
  "learning_rate": 5e-4,
  "dataset_id": 42,
  "org_id": "org-acme"
}
```

### Response (200 — Accepted)

```json
{
  "run_id": 101,
  "adapter_id": "saas-run_101",
  "status": "pending",
  "resource_spec": {
    "gpus_per_node": 1,
    "vcpus": 4,
    "memory_mb": 16384
  }
}
```

### Response (429 — Concurrency Limit)

```json
{
  "error": "org 'org-acme' has 1 running job(s), max concurrent is 1",
  "retry_after_seconds": 120
}
```

### Response (400 — Base Asset Unavailable)

```json
{
  "error": "base model 'tinyllama-1.1b' assets not available in LakeFS for org 'org-acme'",
  "resolution": "run asset acquisition first"
}
```

### Response (400 — Version Mismatch)

```json
{
  "error": "base model version mismatch: fine-tune expects 'tinyllama-1.1b' but LakeFS has version 'tinyllama-1.1b-v2' for org 'org-acme'"
}
```

---

## GET /saas/finetune/{run_id}/status

Poll the current state of a SaaS fine-tune job.

### Response

```json
{
  "run_id": 101,
  "status": "running",
  "retry_count": 0,
  "started_at": "2026-07-02T12:00:00Z",
  "progress": {
    "current_step": 250,
    "total_steps": 500,
    "current_loss": 1.23
  }
}
```

---

## GET /saas/finetune/{run_id}/stream

SSE event stream (reuses existing `GET /training/stream/{run_id}`).

Events: `submitted`, `metrics`, `milestone`, `complete`, `error`, `heartbeat`

---

## POST /saas/finetune/{run_id}/stop

Signal cancellation of a running SaaS fine-tune.

### Response (200)

```json
{
  "run_id": 101,
  "status": "failed",
  "error_message": "Training cancelled by user"
}
```

---

## GET /saas/finetune/usage

Retrieve metering summary for an org.

### Query Parameters

| Param | Type | Description |
|-------|------|-------------|
| `org_id` | `str` | Org to query |
| `since` | `datetime` | Start of metering period |
| `until` | `datetime` | End of metering period |

### Response

```json
{
  "org_id": "org-acme",
  "period": {
    "since": "2026-06-01T00:00:00Z",
    "until": "2026-07-01T00:00:00Z"
  },
  "total_gpu_hours": 12.5,
  "jobs": [
    {
      "run_id": 101,
      "method": "lora",
      "gpu_hours": 6.2,
      "completed_at": "2026-06-15T14:30:00Z"
    }
  ]
}
```

---

## Error Codes

| HTTP Status | Code | Description |
|-------------|------|-------------|
| 400 | `BASE_ASSET_UNAVAILABLE` | Base model not yet in LakeFS |
| 400 | `VERSION_MISMATCH` | LakeFS version differs from config |
| 400 | `INVALID_RESOURCE_SPEC` | `gpus_per_node < 1` for fine-tune |
| 429 | `CONCURRENCY_LIMIT` | Per-org concurrency limit exceeded |
| 500 | `SAAS_UNAVAILABLE` | SaaS backend not configured or unreachable |