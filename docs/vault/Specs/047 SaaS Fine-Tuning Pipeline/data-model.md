---
title: 047 SaaS Fine-Tuning Pipeline — Data Model
type: design
tags:
  - type/design
  - domain/training
  - domain/infrastructure
status: draft
created: '2026-07-02'
updated: '2026-07-02'
---

# Data Model: 047 SaaS Fine-Tuning Pipeline

> **MVP note (2026-07-02):** The MVP reuses the **existing `LoRAAdapter` ORM model** (see
> §4) and adds **no new tables**. The "SaaS FineTune Job", "Usage Metering Record", and
> "SaaS Configuration" entities below are **DEFERRED** — they belong to the AWS Batch /
> metering / tenancy follow-on specs and are documented here only as the target shape. The
> MVP's only data-layer change is finally *populating* a `LoRAAdapter` row on completion
> (currently never created — a pre-existing bug fixed by this spec).

## Entities

### 1. SaaS FineTune Job

Extends the existing `AssetDownloadJob`/training-run pattern for SaaS fine-tune lifecycle.

| Field | Type | Source | Description |
|-------|------|--------|-------------|
| `id` | `int` (PK) | `asset_download_job.id`-like | Auto-increment |
| `external_model_id` | `int` (FK) | `external_models.id` | Base model to fine-tune |
| `run_id` | `int` (FK) | Existing training run | Links to `TrainingRun` / `run_id` |
| `org_id` | `str` | SaaS context | Org scope for concurrency gating |
| `adapter_id` | `str` | Generated | Scoped ID, e.g. `"saas-run_42"` |
| `resource_spec` | `JSON` | `ResourceSpec` | GPU shape: `gpus_per_node`, `vcpus`, `memory_mb` |
| `status` | `str` | 5-state enum | `pending → running → completing → completed | failed` |
| `retry_count` | `int` | Default 0 | Incremented on spot interruption retry |
| `batch_job_id` | `str | None` | AWS Batch | Set on Batch submission |
| `config_s3_key` | `str | None` | S3 | Config payload location |
| `started_at` | `datetime | None` | — | First Batch execution attempt |
| `completed_at` | `datetime | None` | — | Terminal state |
| `error_message` | `str | None` | — | Human-readable failure description |

**State transitions**:
```
pending → running → completing → completed
                                  → failed
```
- `pending`: queued, awaiting concurrency slot
- `running`: Batch GPU job executing PEFT
- `completing`: PEFT done, adapter being stored/registered
- `completed`: adapter in LakeFS, metering recorded
- `failed`: terminal for both retry-exhausted and fatal errors

**Retry policy**: Up to 3 retries on spot interruption with exponential backoff (30s / 90s / 270s). Retry increments `retry_count` and resets `status` to `pending`.

### 2. Usage Metering Record

Tracks GPU-hour consumption per SaaS fine-tune for billback (AD-9).

| Field | Type | Source | Description |
|-------|------|--------|-------------|
| `id` | `int` (PK) | New or extended | Auto-increment |
| `run_id` | `int` (FK) | Training run | Links to the fine-tune run |
| `org_id` | `str` | SaaS context | Billable org |
| `gpu_hours` | `float` | `job_events` | Wall-clock GPU time |
| `method` | `str` | Config | `lora` or `qlora` |
| `gpu_shape` | `str` | `ResourceSpec` | e.g. `"g5.xlarge"` |
| `metered_at` | `datetime` | — | When billing record was finalized |

### 3. SaaS Configuration

Per-org SaaS connectivity and concurrency settings.

| Field | Type | Source | Description |
|-------|------|--------|-------------|
| `org_id` | `str` (PK) | SaaS auth | Org identifier |
| `enabled` | `bool` | Config | SaaS fine-tune availability |
| `max_concurrent_jobs` | `int` | Config (default 1) | Per-org concurrency limit (FR-023c) |
| `endpoint` | `str | None` | Config | SaaS API endpoint |
| `credentials_ref` | `str | None` | Secrets | Reference to stored credentials |

### 4. Adapter (SaaS)

Reuses the existing `LoRAAdapter` ORM model — no new schema needed. The `storage_path` points to LakeFS or local storage depending on deployment.

Key reused fields:
- `external_model_id`, `run_id`, `adapter_id`, `label`
- `method`, `storage_path`, `final_loss`, `final_step`
- `lora_rank`, `lora_alpha`, `lora_target_modules`, `lora_dropout`, `lora_bias`

## Relationships

```
ExternalModel (1) ──── (N) LoRAAdapter
                          │
                          └── SaaS FineTune Job (1:1 via run_id)
                                    │
                                    └── UsageMeteringRecord (1:N)
```

## Validation Rules

| Rule | Description |
|------|-------------|
| **Concurrency gate** | Per-org `max_concurrent_jobs` enforced before `pending` → `running` (FR-023c) |
| **ResourceSpec validity** | `gpus_per_node >= 1` for GPU fine-tunes (FR-023a) |
| **Base asset presence** | Base model `asset_availability = ASSETS_AVAILABLE` before submission |
| **Version match** | LakeFS base model version must match fine-tune config version; mismatch → fail fast |
| **Retry limit** | `retry_count <= 3`; exceeding → `failed` terminal state |

## Enums

### SaaS FineTune Job Status

```python
class SaasFinetuneJobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETING = "completing"
    COMPLETED = "completed"
    FAILED = "failed"
```

### ComputeShape (existing, in spec 032 contract)

```python
class ComputeShape(StrEnum):
    CPU = "cpu"
    GPU = "gpu"
    MULTI_GPU = "multi-gpu"
    MULTI_NODE = "multi-node"
```
