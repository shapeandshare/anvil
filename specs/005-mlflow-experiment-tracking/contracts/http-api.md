# Contract: HTTP API deltas (v1 routes)

**Base**: `/v1` (FastAPI). Only deltas from current (post-`main`) behavior are listed. All MLflow access goes through `TrackingService`.

## POST `/v1/training/start` (MODIFIED)

**Request** (unchanged shape): `config` JSON with hyperparameters + optional `dataset_id`/`corpus_id`/`use_gpu`/`device`.

**New behavior**:
1. Resolve canonical tracking URI from config (remove the hardcoded `MLFLOW_TRACKING_URI` literal, line 21).
2. Resolve `engine_backend`+`device` (via `anvil.gpu`); `TrackingService.start_run(run_name, params, engine_backend, device)` → `mlflow_run_id`.
3. **Create the local `Experiment` row immediately** (`status="running"`, `started_at`, `run_name`, `mlflow_run_id`, resolved `dataset_id`/`corpus_id`, `engine_backend`, `device`). (Previously created only in `on_complete`.)
4. Attach input lineage (`log_dataset_input`/`log_corpus_input`) → store `input_digest`/`input_role`.
5. On success → `finish_run` + status `finished` + `final_loss` + `log_artifacts` + **`register_source_model`** (source-keyed; replaces the `anvil-experiment-{id}` auto-register, lines 139–155).
6. On exception → `fail_run(reason=...)` + status `failed` + `error_message`; NO model version created.

**Response** (extended): `{ "run_id": int, "mlflow_run_id": str | null, "experiment_id": int, "status": "running", "tracking": "active" | "degraded" }`.

**Tracking unavailable (Article IX / FR-009)**: NO `5xx`. Training still starts; the response sets `"tracking": "degraded"` (and `mlflow_run_id: null`) and the SSE stream emits a non-blocking `warning` event. The run is never blocked or errored solely because the tracking server is down.

## GET `/v1/training/stream/{run_id}` (UNCHANGED)

SSE metrics stream (already emits `device` in metric events).

## GET `/v1/experiments` (MODIFIED)

- Derive MLflow client + UI base URL from config (remove `MLFLOW_TRACKING_URI` / `MLFLOW_UI_URI` literals).
- Expose `run_name`, `status` (`running`/`finished`/`failed`), `input_digest`, `input_role`, `engine_backend`, `device` (FR-007).

## POST `/v1/registry/models` (MODIFIED — redirect to MLflow registry)

- Targets the **MLflow model registry**, not local tables (FR-019/027). Since registration is now automatic per successful run, this endpoint becomes a manual re-register/promote that MUST resolve the **same source-keyed** registered model (`dataset-<id>`/`corpus-<id>`) for the experiment's input source.
- Validates the experiment is `finished` (was `completed`).

**Response**: `{ "name": str, "version": int, "run_id": str, "source": "runs:/<run_id>/model.json" }`.

**Deprecation**: local-registry write path removed; `GET /v1/registry/models*` read endpoints proxy the MLflow registry or are marked legacy/read-only (decided in tasks).

## GET/POST `/v1/eval-datasets` (NEW — first-class under 3.x; capability-gated)

- `POST /v1/eval-datasets` create; `POST /v1/eval-datasets/{name}/records` append; `GET /v1/eval-datasets/{name}` query (FR-021).
- If `capabilities().genai_datasets` is False → `200` `{ "available": false, "reason": ... }` (graceful), never a `5xx` that fails a run (FR-022/SC-007).

## Startup — FastAPI `lifespan` (MODIFIED, `api/app.py`)

- After engine init / `create_all` and MLflow server start: call `mlflow.enable_system_metrics_logging()` once, then `TrackingService.reconcile_orphans()` before serving (FR-020/028). Idempotent.

## CLI parity — `anvil train` (MODIFIED, `cli.py`)

- Route through `TrainingService` + `TrackingService` so CLI runs are tracked identically (create run, lifecycle, lineage, metrics, system metrics, source-keyed registration) — FR-008. Add `--dataset` alongside `--corpus`/`--gpu`/`--device`.
