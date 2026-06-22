---
title: 006 MLflow Experiment Tracking - quickstart
type: quickstart
tags:
  - type/spec
spec-refs:
  - docs/vault/Specs/006 MLflow Experiment Tracking/
related:
  - '[[006 MLflow Experiment Tracking]]'
created: ~
updated: ~
---
# Quickstart: MLflow Experiment & Data Lifecycle Tracking

End-to-end walkthrough (and manual acceptance script) for the implemented feature.

## Prerequisites

```bash
make setup      # venv, core deps (mlflow>=3.1,<4, psutil), DB init + alembic upgrade
                # GPU hosts auto-detected → installs the `gpu` extra (torch + nvidia-ml-py); CPU-only otherwise (Article IX)
make run        # web server + supervisor-managed `mlflow server` on 127.0.0.1:5000
```

Single canonical config (FR-006):
```bash
# .env  — one value drives writers AND readers
MICROGPT_MLFLOW_URI=http://127.0.0.1:5000     # HTTP tracking-server URI (NOT a sqlite path)
```

## 1. Reproducible provenance (US1)

```bash
curl -s -X POST localhost:8080/v1/training/start \
  -H 'content-type: application/json' \
  -d '{"num_steps":50,"n_embd":16,"dataset_id":1}'
# → { "run_id":0, "mlflow_run_id":"...", "experiment_id":1, "status":"running" }
```
In MLflow (`http://127.0.0.1:5000`): the run shows the dataset under **Inputs** as a `training` input with a content digest + source. Same content ⇒ same digest; changed content ⇒ different (FR-003). Repeat with `{"corpus_id":1}` → `corpus` input + files as artifacts. (SC-002/003)

## 2. Consistent destination, web + CLI (US2)

```bash
microgpt train --dataset 1        # CLI run, tracked identically to web (FR-008)
```
Both runs appear in the SAME server AND in `GET /v1/experiments`; none land in a stray `./mlruns` (SC-001/009).

## 3. Live + historical metrics + device provenance (US3)

```bash
curl -N localhost:8080/v1/training/stream/0      # live loss
```
MLflow charts per-step `loss`, a distinct `final_loss`, and run params include `engine_backend` (`stdlib`/`torch`) and `device` (`cpu`/`cuda`/`mps`). Two runs overlay on a shared step axis (SC-005).

## 4. Failure & orphan integrity (US4)

```bash
curl -s -X POST localhost:8080/v1/training/start -d '{"num_steps":-1,"dataset_id":1}'   # forced failure
kill -9 <training-worker-pid>     # simulate hard kill
make stop && make run             # startup reconciles orphaned RUNNING runs
```
`GET /v1/experiments` shows `status=failed` with an interruption reason; MLflow status agrees (FAILED/KILLED) (SC-004/010).

## 5. System metrics incl. MPS (US5)

Start any run → MLflow shows `system/cpu_*` and `system/memory_*`. On CUDA hosts, `system/gpu_*` via `nvidia-ml-py`; on Apple Silicon, MPS utilization/memory via the **custom collector**; no-accelerator hosts still record CPU/mem (SC-006).

## 6. Managed evaluation sets (US6 — first-class under 3.x)

```bash
curl -s -X POST localhost:8080/v1/eval-datasets -d '{"name":"trainer_eval_v1"}'
curl -s -X POST localhost:8080/v1/eval-datasets/trainer_eval_v1/records \
  -d '{"records":[{"prompt":"a","expected":"b"}]}'
curl -s localhost:8080/v1/eval-datasets/trainer_eval_v1     # persists + queryable by name
```
Works first-class with `mlflow>=3.1` + the HTTP server. If genai is unavailable, returns `{ "available": false, ... }` and runs continue (SC-007).

## 7. Source-keyed model registry (single source of truth)

```bash
# Train 3 successful runs on corpus "oldgrowth" (id=2)
for i in 1 2 3; do curl -s -X POST localhost:8080/v1/training/start -d '{"num_steps":30,"corpus_id":2}'; done
```
In MLflow **Models**: exactly **one** registered model for that source (`corpus-2`) with **3 versions** — one per successful run; failed runs add 0 versions. A new dataset/corpus → a new registered model. No parallel local-registry entry is created (SC-008/SC-011).

## Validation commands

```bash
make test        # full suite; coverage must stay at 100%
make lint        # ruff + black --check + isort --check + pylint
make typecheck   # mypy (strict)
```

## Acceptance → Success-Criteria map

| Step | Stories | Success Criteria |
|---|---|---|
| 1 | US1 | SC-002, SC-003 |
| 2 | US2 | SC-001, SC-009 |
| 3 | US3 | SC-005 |
| 4 | US4 | SC-004, SC-010 |
| 5 | US5 | SC-006 |
| 6 | US6 | SC-007 |
| 7 | registry | SC-008, SC-011 |
