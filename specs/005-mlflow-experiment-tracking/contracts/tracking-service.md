# Contract: `TrackingService` (internal service seam)

**Module**: `microgpt/services/tracking.py`
**Layer**: Service (consumed by `api/v1/*` routes and `cli.py`; depends on `config`, repositories, an injected MLflow client factory, and `metrics_collectors`)
**Async**: all public methods are `async`; blocking MLflow/pynvml calls wrapped in `run_in_executor`.

The single seam for ALL MLflow access (FR-006/008). No other module constructs `MlflowClient`.

## Construction

```
TrackingService(
    *,
    tracking_uri: str | None = None,        # default: get_config()["mlflow_uri"] — the HTTP server URI (R2)
    experiment_name: str = "microgpt-workbench",
    client_factory: Callable[[str], MlflowClientLike] | None = None,  # injected for tests (R12)
)
```
- `tracking_uri` MUST be the HTTP server URI; the service never opens sqlite directly.

## Capability detection

```
async def capabilities() -> TrackingCapabilities
# { genai_datasets: bool, server_backed: bool, mlflow_version: str }
```
- `genai_datasets` True only if `mlflow.genai.datasets` importable AND store is server-backed (FR-023). Expected True under the 3.x mandate.

## Run lifecycle

```
async def start_run(*, run_name: str, params: dict[str, Any],
                    engine_backend: str, device: str) -> str        # returns run_id; logs params incl. engine/device (FR-010/011)
async def log_metric(run_id, key, value, *, step) -> None           # FR-012/014 (best-effort)
async def log_final_metric(run_id, key, value) -> None              # FR-013
async def finish_run(run_id) -> None                                # FINISHED (FR-015)
async def fail_run(run_id, *, reason) -> None                       # FAILED + reason (FR-015)
async def reconcile_orphans() -> list[str]                          # FR-028; KILLED+failed in both stores; idempotent
```

## Input lineage (delegates to `MlflowInputResolver`)

```
async def log_dataset_input(run_id, *, dataset_id, role="training") -> str   # returns digest; FR-001/002/003
async def log_corpus_input(run_id, *, corpus_id) -> str                       # MetaDataset + file artifacts; FR-004
```
- Roles constrained to `training`|`validation`|`corpus`. Digest content-derived (FR-003).

## Artifacts & source-keyed model registry

```
async def log_artifacts(run_id, *, model_path, samples, vocab) -> None        # FR-017/018
async def register_source_model(*, run_id, dataset_id=None, corpus_id=None,
                                artifact_path="model.json") -> RegisteredVersionRef   # FR-019/029/030
```
- `register_source_model`: compute the **source-keyed name** (`dataset-<id>`/`corpus-<id>`/`default-source`), `create_registered_model(name)` (get-or-create), then `create_model_version(name, source="runs:/<run_id>/<artifact_path>", run_id=...)`. No flavor (FR-025). Called ONLY on successful completion (FR-030).

## Managed evaluation datasets (first-class under 3.x; capability-gated)

```
async def create_eval_dataset(*, name, tags=None) -> EvalDatasetRef    # FR-021
async def append_eval_records(*, name, records) -> int                  # FR-021
async def get_eval_dataset(*, name) -> EvalDatasetRef | None            # FR-021
```
- If `capabilities().genai_datasets` is False → raise `CapabilityUnavailable`; callers translate to a graceful message; runs are NEVER failed for this (FR-022/SC-007).

## Degraded mode (Constitution Article IX)

- When the destination is unreachable, `start_run` MUST NOT propagate a fatal error. Instead the service enters **degraded mode**: it returns a sentinel/no-op run handle, emits a one-time non-blocking warning, and all subsequent `log_*`/`finish`/`fail`/`register_*` calls become safe no-ops so training proceeds untracked (FR-009). `is_degraded` exposes the state for callers to surface the warning.
- GPU/accelerator and genai dependencies absent → graceful no-op, never an error solely for the missing optional dependency.

## Errors

- `CapabilityUnavailable` — genai unsupported; raised only to the eval-dataset API path, which translates it to a graceful response (FR-022). NEVER fails a training run.
- (`TrackingUnavailable` is handled internally as degraded mode per above — it is not surfaced as a run-failing error.)

## Invariants

- Local `Experiment.status` and MLflow run status always agree (FR-016).
- Registration is source-keyed and happens once per **successful** run (FR-019/030): 1 source → 1 registered model → N versions.
- No method constructs a second tracking client or reads a non-canonical URI.
