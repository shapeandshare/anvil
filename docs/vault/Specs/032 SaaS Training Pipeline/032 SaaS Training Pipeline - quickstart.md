---
title: 032 SaaS Training Pipeline - quickstart
type: quickstart
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

# Quickstart: SaaS Training Pipeline Development

This quickstart covers developing and testing the SaaS training pipeline (S3FileStore, RedisEventBus, BatchJobQueue, BatchComputeBackend, compute worker, reconciler, SSE streaming, and usage metering).

## Prerequisites

- All prerequisites from [[Specs/029 SaaS Dev Stack/029 SaaS Dev Stack - quickstart|029 SaaS Dev Stack]]
- Docker Desktop (macOS) or Docker Engine (Linux)
- AWS CLI configured (for Batch testing against dev AWS)

---

## Local Development (Docker Compose)

The fastest iteration loop uses the docker compose stack:

```bash
# Start the full SaaS emulation stack
docker compose up

# Services:
#   postgres:5432  — anvil_app + anvil_mlflow databases
#   redis:6379     — pub/sub for SSE
#   minio:9000     — S3-compatible API
#   mlflow:5000    — MLflow with Postgres backend, MinIO artifacts
#   anvil-web:8080 — FastAPI with hot-reload
```

In this mode, training runs in-process (not Batch), writing to MinIO and PostgreSQL. SSE streams through Redis. This validates the full pipeline except the Batch dispatch path.

### Testing the pipeline

```bash
# Submit a training job (SaaS mode, in-process compute)
curl -X POST http://localhost:8080/v1/training/start \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "corpus_id": 1,
    "config": {"n_embd": 16, "n_layer": 1, "n_head": 4, "num_steps": 100},
    "resource_spec": {"node_count": 1, "gpus_per_node": 0, "vcpus": 2, "memory_mb": 4096}
  }'

# Open SSE stream (browser or curl)
curl -N http://localhost:8080/v1/training/stream/1?token=$SSE_TOKEN

# Poll events (if SSE fails)
curl http://localhost:8080/v1/training/1/events?since=0

# Check status
curl http://localhost:8080/v1/training/1

# Cancel job
curl -X POST http://localhost:8080/v1/training/1/cancel
```

---

## Developing Against Dev AWS

For full Batch dispatch validation:

```bash
pip install anvil[aws]

ANVIL_MODE=saas \
DATABASE_URL=postgresql+asyncpg://dev:...@dev-rds.aws:5432/anvil_app \
REDIS_URL=redis://dev-redis.aws:6379 \
S3_DATA_BUCKET=anvil-data-dev \
MLFLOW_TRACKING_URI=http://dev-mlflow.internal:5000 \
uvicorn anvil._saas.app:app --reload
```

Training dispatches to Batch in this mode. Compute runs in a separate pod.

---

## Key Implementation Files

| File | Purpose |
|------|---------|
| `anvil/db/models/training_job.py` | TrainingJob ORM model |
| `anvil/db/models/job_event.py` | JobEvent append-only model |
| `anvil/db/models/usage_record.py` | UsageRecord ORM model |
| `anvil/_saas/implementations/s3_file_store.py` | S3-backed FileStore |
| `anvil/_saas/implementations/redis_event_bus.py` | Redis pub/sub EventBus |
| `anvil/_saas/implementations/batch_job_queue.py` | AWS Batch JobQueue |
| `anvil/_saas/implementations/batch_compute_backend.py` | Batch ComputeBackend |
| `anvil/_saas/compute_worker.py` | Batch compute pod entrypoint |
| `anvil/_saas/reconciler.py` | Job state reconciler |
| `anvil/api/v1/training.py` | Training API endpoints + SSE |
| `anvil/api/static/js/sse.js` | SSE client with polling fallback |

---

## Testing

```bash
# Run all tests
make test

# Run specific integration tests
pytest tests/integration/test_reconciler.py -v
pytest tests/integration/test_sse_resilience.py -v

# Lint + typecheck
make lint
make typecheck
```

---

## Local Mode Verification

Confirm the existing local in-process training flow is unchanged:

```bash
# Clean install (no SaaS extras)
pip install .
anvil serve

# → Verify: upload corpus, start training, SSE stream shows metrics,
#   model downloads from data/models/
```