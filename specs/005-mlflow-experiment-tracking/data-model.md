# Phase 1 Data Model: MLflow Experiment & Data Lifecycle Tracking

**Date**: 2026-06-13

Two storage systems:
- **App DB** (`data/microgpt.db`, async SQLAlchemy + Alembic): the workbench's metadata, incl. the `Experiment` lifecycle record mirroring the MLflow run.
- **MLflow tracking store** (server-backed SQLite under `mlruns/`, reached over HTTP): source of truth for runs, params, metrics, inputs (lineage), artifacts, system metrics, the **model registry**, and managed evaluation datasets.

This feature minimally changes the App DB (Experiment lifecycle) and **deprecates** the local model-registry tables. No new app-side tables are introduced.

---

## A. App DB changes (Alembic migration required)

### A1. `Experiment` (MODIFIED) — table `experiments`

Becomes the lifecycle mirror of the MLflow run, created at run **start**.

| Field | Type | Change | Notes |
|---|---|---|---|
| `id` | int PK | unchanged | |
| `mlflow_run_id` | str(255), unique, nullable | unchanged | set at start now |
| `run_name` | str(255), nullable | **NEW** | human-meaningful name (FR-010) |
| `status` | str(20) | **semantics change** | `running` → `finished`/`failed` (was free-form `pending`→`completed`) |
| `config_id` | int FK→training_configs | unchanged | |
| `dataset_id` | int FK→datasets, nullable | unchanged | |
| `corpus_id` | int FK→corpora, nullable | **NEW** | parity with TrainingConfig; which source fed the run |
| `input_digest` | str(64), nullable | **NEW** | content digest of data fed (FR-003) |
| `input_role` | str(20), nullable | **NEW** | `training`/`validation`/`corpus` (FR-002) |
| `engine_backend` | str(16), nullable | **NEW** | `stdlib`/`torch` (FR-011/Q3) |
| `device` | str(16), nullable | **NEW** | `cpu`/`cuda`/`mps` (FR-011/Q3) |
| `final_loss` | float, nullable | unchanged | |
| `started_at` | datetime, nullable | **now populated** | set at start |
| `completed_at` | datetime, nullable | **now populated** | set at terminal event |
| `generated_samples` | text, nullable | unchanged | |
| `error_message` | str, nullable | **now populated** | failure/interruption reason (FR-015/028) |
| `created_at`/`updated_at` | datetime | unchanged (TimestampMixin) | |

**State transitions** (FR-015/016/028):
```
(create at start) → running
running → finished        # normal completion
running → failed          # exception during training (reason captured)
running → failed          # orphan reconciliation on startup (reason="interrupted/terminated")
```
Invariant: local `status` agrees with MLflow run status (`running↔RUNNING`, `finished↔FINISHED`, `failed↔FAILED|KILLED`).

**Validation**:
- Exactly one of `dataset_id`/`corpus_id` reflects the input actually fed (no phantom for unused reference).
- `input_digest`/`input_role` present once a run reaches `running` with a resolved input.
- `error_message` non-null whenever `status = failed`.
- `engine_backend`/`device` recorded for every run.

### A2. `RegisteredModel` / `ModelVersion` (DEPRECATED) — tables `registered_models`, `model_versions` (migration `006`)

- No new writes from training (`on_complete`) or `POST /v1/registry/models` — both target the MLflow registry instead (FR-019/027).
- Existing rows retained read-only during transition; a migration step moves them into the MLflow registry (best-effort) or marks legacy. Tables are NOT dropped in this feature (avoid data loss); dropping is a verified follow-up.

### A3. `TrainingConfig` (UNCHANGED)

Reused for hyperparameters; flattens into MLflow run params (FR-011).

### A4. `Dataset` / `Corpus` (UNCHANGED schema)

Reused as source-of-truth for input identity/source and for the **source-keyed registered-model name** (id-based slug). Content digest computed at run time (R6) — no digest column added.

---

## B. MLflow-native entities (no App DB tables)

### B1. Training Run (MLflow Run)
- One per job; `run_name` set; `run_id` stored on `Experiment.mlflow_run_id`.
- **Params**: flattened `TrainingConfig` + `dataset_id`/`corpus_id` + `engine_backend` + `device` (+ existing `gpu_*`/`torch_version`).
- **Metrics**: `loss` per step (consistent axis), `final_loss` summary, optional eval metrics on the same axis.
- **Inputs (lineage)**: dataset/corpus via `log_input(context=...)` (B2).
- **Artifacts**: `model.json`, `samples.txt`, vocab/config (FR-017).
- **System metrics**: `system/cpu_*`, `system/memory_*`, `system/gpu_*` (CUDA via MLflow; MPS via custom collector — B5).
- **Status**: `RUNNING` → `FINISHED`/`FAILED`/`KILLED`.

### B2. Run Input (MLflow Dataset + context)
| Representation | When | Construction | context |
|---|---|---|---|
| Tabular dataset | loadable into a frame | `from_pandas(df, source=<uri>, name=<name@ver>, digest=<hash>)` | `training`/`validation` |
| Metadata-only | corpus / non-tabular | `MetaDataset(source=LocalDatasetSource(root), name="corpus_<id>", digest=<hash>)` + files as artifacts | `corpus` |

Identity (FR-003): `digest` content-derived → identical content ⇒ identical digest.

### B3. Registered Model (MLflow Model Registry) — single source of truth, **source-keyed**
- Name derived from a **stable per-source key based on the immutable DB id** (NOT the mutable source name): `dataset-<id>` / `corpus-<id>` / literal `default-source` (FR-029). Renaming a dataset/corpus does not change the slug, so versions keep accumulating under the same registered model.
- Each **successful** run → `create_registered_model(name)` (get-or-create) + `create_model_version(name, source="runs:/<run_id>/model.json", run_id=...)` → one new version (FR-019/030).
- Relationship: **1 input source → 1 registered model → N versions** (one per successful experiment on that source).
- Failed/interrupted/orphaned runs create **0** versions (FR-030).
- Replaces deprecated local `RegisteredModel`/`ModelVersion`.

### B4. Managed Evaluation Set (MLflow GenAI `EvaluationDataset`) — first-class under 3.x
- `create_dataset(name, experiment_id, tags)`; `merge_records`; `to_df`/`search_datasets`.
- Requires server-backed store (R2); falls back to per-run lineage if unavailable (FR-022).

### B5. Resource-Utilization Series
- CPU/mem (psutil via MLflow), CUDA GPU (`nvidia-ml-py` via MLflow built-in), MPS (custom collector on a background thread logging `system/gpu_*`-style metrics). **MPS source**: utilization % via `ioreg`/IOKit `AGXAccelerator → PerformanceStatistics → Device Utilization %`; memory via the same `PerformanceStatistics` block / `torch.mps` memory APIs. Stdlib `subprocess` only — **no new dependency, no `sudo`**. Note: `psutil` and `torch.mps` do **not** expose GPU utilization (torch.mps is memory-only), so `ioreg` is the utilization source.

### B6. Tracking Destination (configuration)
- Canonical HTTP server URI from `get_config()["mlflow_uri"]`; sqlite is the server backend-store only; capability level detected at startup (FR-023).

---

## C. Entity relationships

```
TrainingConfig 1───* Experiment ───1 (mirrors) MLflow Run
                          │  status, run_name,     ├── params (config + engine_backend + device)
            dataset_id ───┤  input_digest/role,    ├── metrics (loss/step, final_loss, eval)
            corpus_id  ───┤  engine_backend/device  ├── inputs ──> Dataset/Corpus (digest, context)
                          │                         ├── artifacts (model.json, samples.txt)
Dataset / Corpus ─────────┤                         ├── system metrics (cpu/mem/cuda/mps)
   (source identity) ─────┼──(source-keyed)──> Registered Model (1 per source) ──* Versions (1 per success)
                          │                         MLflow Model Registry (single source of truth)
                          └──────────────────> MLflow GenAI EvaluationDataset (eval sets)
```

`Experiment.mlflow_run_id` joins App DB ↔ MLflow. The input source (Dataset/Corpus) determines the registered-model identity. Local model-registry tables are detached (deprecated).
