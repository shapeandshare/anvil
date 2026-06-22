# Phase 0 Research: MLflow Experiment & Data Lifecycle Tracking

**Date**: 2026-06-13 | **MLflow target**: 3.x (`>=3.1,<4`; APIs verified against 3.13.0)

Grounded in (a) direct reads of the post-`main` codebase and (b) MLflow 3.x API introspection / official docs. Each entry: Decision → Rationale → Alternatives.

---

## R1. MLflow version: bump to 3.x (mandate)

**Decision**: Change `pyproject.toml` from the shipped `mlflow>=2.16,<3` to **`mlflow>=3.1,<4`**. Planning MUST verify clean resolution against existing pins (`pydantic<3`, `torch>=2.0`, `alembic<2`).

**Rationale**: User mandate ("we must have mlflow>3"); double-check confirmed `main` pinned 2.x (commit `3f139bf`). MLflow 2.x lacks `mlflow.genai` managed datasets (US6/FR-021). 3.x provides them and keeps the lineage/system-metrics/registry APIs already used.

**Alternatives**: Stay on 2.x with US6 deferred (rejected by mandate); unbounded `mlflow` (rejected — keep `<4` to guard a future breaking major).

---

## R2. Canonical tracking destination = HTTP server URI

**Decision**: `MICROGPT_MLFLOW_URI` resolves to the running tracking server's HTTP URI (default `http://127.0.0.1:5000`). The sqlite path (`sqlite:///<abs>/mlruns/mlflow.db`) is the server's `--backend-store-uri` only. All clients use `MlflowClient(tracking_uri=<http>)` / `mlflow.set_tracking_uri(<http>)`; none open sqlite directly.

**Rationale**: `mlflow.genai` managed datasets **reject FileStore** and require a SQL/server-backed store — only the HTTP server qualifies (US6). Also avoids multi-writer SQLite contention for concurrent runs, fully supports the Model Registry, matches the supervisor-managed server + UI links, and fixes the `./mlruns` vs `mlruns` divergence (only the server touches the file).

**Alternatives**: Direct sqlite file URI for clients (rejected — breaks genai, risks contention); split write/UI URIs (rejected — two config values, more drift).

---

## R3. Single seam: `TrackingService`

**Decision**: `anvil/services/tracking.py` owns URI resolution, client construction (injectable factory for tests), experiment get-or-create, run lifecycle, params/metrics, lineage, artifacts, source-keyed registration, genai datasets, and orphan reconciliation. Routes (`training.py`, `experiments.py`, `registry.py`, new `eval_datasets.py`) and `cli.py` depend on it; the four hardcoded `MlflowClient(tracking_uri="sqlite:///./mlruns/mlflow.db")` literals are removed.

**Rationale**: Layer discipline; eliminates duplication; one implementation for web+CLI (FR-008). Blocking MLflow calls wrapped in `run_in_executor` (mirrors existing `train()` executor usage).

**Alternatives**: Per-route helpers reading config (rejected — leaves duplication, hampers CLI parity + reconciliation reuse).

---

## R4. Run lifecycle record created at START

**Decision**: Create the local `Experiment` row at run *start* (`status="running"`, `started_at`, `run_name`, `mlflow_run_id`), update to `finished`/`failed` at terminal events. Persist `completed_at`/`error_message` (columns exist, unused today).

**Rationale**: Today the `Experiment` row is created **only in `on_complete`** (`api/v1/training.py` line 124), so a crashed run has an MLflow run stuck `RUNNING` and **no local row** — making FR-015/016 and US4 impossible. Creating at start is the prerequisite for failure marking + reconciliation.

**Alternatives**: Reconstruct failures from MLflow only (rejected — the workbench UI reads the local `experiments` table).

---

## R5. Status vocabulary & orphan reconciliation

**Decision**: Local statuses `running` → (`finished` | `failed`). MLflow `RUNNING` → (`FINISHED` | `FAILED` | `KILLED`). On FastAPI `lifespan` startup, reconcile: `MlflowClient.search_runs(filter_string="attributes.status = 'RUNNING'")` + local non-terminal `Experiment`s with no live owner → `set_terminated(run_id, status="KILLED")` + `mark_failed(reason="interrupted/terminated")` in both stores. Idempotent.

**Rationale**: Hard kills/OOM/power-loss run no in-process handler (FR-028); startup is the only reliable owner-less point and already exists in `lifespan` (`api/app.py`). (`main` currently sets only `pending → completed`; no `failed` path at all.)

**Alternatives**: Heartbeat/timeout sweep (deferred — adds a knob + loop); exception-handler-only (rejected — misses hard kills).

---

## R6. Dataset/corpus input lineage + content digest

**Decision**: `MlflowInputResolver` (FR-005) decides representation and computes a content-derived digest:
- Dataset (loadable): `mlflow.data.from_pandas(df, source=<uri>, name=<name@ver>, digest=<content hash>)`, `log_input(context="training")`; validation split → `context="validation"`.
- Corpus (non-tabular files): `MetaDataset(source=LocalDatasetSource(root), name="corpus_<id>", digest=<content hash>)` + `log_input(context="corpus")` + source files as run artifacts (FR-004).
- Digest = stable hash over the materialized docs/files so identical content ⇒ identical digest (FR-003); passed explicitly as `digest=`.

**Rationale**: MLflow has no corpus primitive (FR-024 forbids a bespoke store); composing from `from_*`/`MetaDataset` + artifacts + `log_input(context=...)` keeps everything inspectable. Datasets/corpora have no digest column, so compute at run time from the exact docs fed.

**Alternatives**: Persist a digest column (deferred); IDs-as-provenance (rejected — not content-derived, fails FR-003).

---

## R7. Backend/device provenance

**Decision**: Record resolved engine backend (`stdlib`/`torch`) and device (`cpu`/`cuda`/`mps`) as run params/tags on every run, via `TrackingService` using `anvil.gpu.resolve_device()`/`detect_gpu()`.

**Rationale**: FR-011/Q3 — loss/speed differences may be due to CPU-vs-GPU, not config. `main` already logs `gpu_available`/`gpu_backend`/`gpu_device_name`/`torch_version` in `api/v1/training.py`; this consolidates that into `TrackingService` and adds the resolved `engine`+`device` so web and CLI record it consistently.

**Alternatives**: Omit device (rejected); GPU-only (rejected — CPU runs need the label for contrast).

---

## R8. Custom (non-flavor) model registration — source-keyed, auto on success

**Decision**: On **successful** completion, log `model.json` as a run artifact (FR-017), then register via a **source-keyed** registered model:
- Derive the registered-model name from a stable per-source key (id-based slug, e.g. `dataset-<id>` / `corpus-<id>`; default input → `default-source`). Renaming the source must not fork it (FR-029).
- `MlflowClient.create_registered_model(name)` (idempotent get-or-create) + `create_model_version(name, source="runs:/<run_id>/model.json", run_id=...)` → one new version per successful run (FR-019/030). No flavor/pyfunc (FR-025).
- Deprecate the local `RegisteredModel`/`ModelVersion` write path (`services/models.py`); redirect/retire `POST /v1/registry/models`.

**Rationale**: Engine is custom JSON (stdlib + torch both serialize to JSON), so no HF/PyTorch flavor applies; MLflow model versions can point at any artifact URI. Source-keying (user's model: 1 source → many experiments → many versions → 1 registered model) gives clean hygiene + a real versioning story, replacing `main`'s `anvil-experiment-{id}` (one throwaway model per run). Resolves the dual-system contradiction (SC-008/SC-011).

**Alternatives**: Per-experiment auto-register (current `main` — rejected, registry pollution); explicit promotion only (rejected by user); one global shared model (rejected — loses per-source separation); `pyfunc` wrapper (deferred).

**Transition (FR-027)**: migrate existing local `ModelVersion` rows into MLflow registered models (best-effort, pointing at `artifact_path`) or mark legacy; never orphan/duplicate.

---

## R9. System metrics: CUDA via MLflow + custom MPS collector

**Decision**: Call `mlflow.enable_system_metrics_logging()` once at process start (web `lifespan` + CLI training entry). Add `nvidia-ml-py` for CUDA capture (MLflow built-in). Since MLflow does **not** cover Apple Silicon MPS, implement a **custom MPS collector** (`metrics_collectors.py`) that samples MPS utilization/memory on a background thread and logs `system/gpu_*`-style metrics to the active run; capability-gated so non-MPS/non-CUDA hosts degrade gracefully (CPU/mem always recorded).

MPS **mechanism (verified)**: the collector obtains MPS **utilization %** by parsing the world-readable IOKit property dictionary `ioreg -r -c AGXAccelerator -d 2` → `PerformanceStatistics` → `Device Utilization %` (the same source Activity Monitor uses; no elevated privileges required). MPS **memory** comes from the same `PerformanceStatistics` block (`In use system memory` / `Alloc system memory`) and/or `torch.mps` memory APIs. This uses **stdlib `subprocess` only — no new dependency** — and **no `sudo`**. If `ioreg` is unavailable or its output cannot be parsed, the collector degrades to memory-only (or no-op) without error (Article IX).

**Rationale**: FR-020/FR-031/Q4→B require accelerator metrics on ALL accelerators incl. MPS; MPS is the primary dev platform. Verification of the platform APIs established that **neither `psutil` nor `torch.mps` can provide GPU utilization**: `psutil` has no GPU coverage, and `torch.mps` exposes **memory only** (`current_allocated_memory`/`driver_allocated_memory`/`recommended_max_memory`) with **no utilization API**. The only non-privileged source of MPS utilization % is the IOKit `AGXAccelerator → PerformanceStatistics` dictionary (read via `ioreg`). `psutil` (declared) still supplies host CPU/mem.

**Alternatives**: `powermetrics --samplers gpu_power` (rejected — **requires `sudo`/root**, unusable for an unprivileged in-process collector); `torch.mps` for utilization (rejected — memory only, no utilization counter); third-party packages such as `darwin-perf`/IOReport ctypes bindings (rejected — add a dependency/native build; the stdlib `ioreg` parse suffices and matches the lean-dependency ethos); CUDA-only scope (rejected by user); drop accelerator metrics (rejected — SC-006); per-run manual instrumentation (rejected — must be automatic).

---

## R10. Managed evaluation datasets (first-class under 3.x)

**Decision**: Implement create/append/query via `mlflow.genai.create_dataset`, `EvaluationDataset.merge_records`, `search_datasets`, `to_df`. Detect availability at runtime (`try: import mlflow.genai.datasets`) AND that the store is server-backed (R2). With the 3.x mandate + HTTP server this is the expected primary path; otherwise degrade to per-run lineage and inform the user (FR-022) without failing runs.

**Rationale**: Version mandate made US6 first-class; R2 server URI makes it possible (FileStore rejected by genai). Distinct from the existing `POST /v1/eval/perplexity` (raw-text perplexity, unrelated).

**Alternatives**: Always-fallback (rejected — first-class per mandate).

---

## R11. Dependency declaration

**Decision**: `pyproject.toml` → `mlflow>=3.1,<4` (core dep bump); add `nvidia-ml-py>=12,<13` to the **`gpu` optional extra** (alongside `torch`), per Constitution Article I (GPU is opt-in). `psutil` already declared (core).

**Rationale**: FR-026/FR-031. Pin to a genai-providing 3.x; `<4` guards a future major. `nvidia-ml-py` is GPU-only, so it belongs in the opt-in `gpu` extra (auto-installed on capable hosts per Article IX); CPU-only installs omit it and degrade GPU-metric capture silently. MPS collector uses psutil/stdlib (no extra dep).

**Alternatives**: No upper bound (rejected per mandate + safety).

---

## R12. Testing strategy under 100% coverage + real-MLflow convention

**Decision**: Unit tests inject a fake tracking client into `TrackingService` (constructor `client_factory`) to assert lineage/lifecycle/registration/genai calls deterministically. Integration tests (orphan reconciliation, genai datasets, source-keyed versioning) run against a real server-backed sqlite store in a temp dir via a fixture. The MPS collector is tested with the platform sampler monkeypatched (so CI without MPS still covers the branch). CLI e2e runs a tiny job and asserts a tracked run + a registered version appear.

**Rationale**: Existing suite uses real MLflow with no mocking, but failure/orphan/registration/MPS branches need determinism to hit `fail_under=100` without flakiness. Injected factory keeps production wiring on the canonical URI.

**Alternatives**: Real MLflow everywhere (rejected — non-deterministic error/MPS paths); module-level mock of `mlflow` (rejected — brittle).
