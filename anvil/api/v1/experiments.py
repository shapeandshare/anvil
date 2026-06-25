# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Experiment tracking and management API endpoints.

This module provides FastAPI routes for listing, comparing, retrieving,
deleting experiments, and managing their MLflow artifacts and metrics.
All routes are prefixed with ``/v1`` and mounted under the ``router``.
"""

import asyncio
import json
import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse
from mlflow.exceptions import MlflowException
from mlflow.tracking import MlflowClient

from ...config import get_config, get_mlflow_browser_uri
from ...core.engine import LlamaModel
from ...services.tracking.tracking import TrackingService
from ...services.training.memory_estimator import estimate_training_memory

router = APIRouter()

GPU_MEMORY_METRIC = "system/gpu_memory_gb"
"""str: MLflow metric name for peak GPU memory usage in gigabytes."""

GPU_UTIL_METRIC = "system/gpu_util_pct"
"""str: MLflow metric name for peak GPU utilization percentage."""

# Type coercers for reconstructing typed hyperparameters from MLflow params.
# Maps hyperparameter names to their target types for deserialization
# from string-valued MLflow parameter storage.
_HYPERPARAM_COERCERS: dict[str, type] = {
    "n_layer": int,
    "n_embd": int,
    "n_head": int,
    "block_size": int,
    "num_steps": int,
    "learning_rate": float,
    "beta1": float,
    "beta2": float,
    "temperature": float,
}


def _hyperparams_from_mlflow(params: dict[str, str]) -> dict[str, Any]:
    """Reconstruct typed hyperparameters from string-valued MLflow params.

    Used as a fallback when the experiment has no linked TrainingConfig row.
    Coerces string values to their appropriate types using ``_HYPERPARAM_COERCERS``.

    Parameters
    ----------
    params : dict[str, str]
        Raw string-valued parameters as returned by MLflow.

    Returns
    -------
    dict[str, Any]
        Typed hyperparameters with string keys matching ``_HYPERPARAM_COERCERS``
        keys. Returns empty dict if no parameters match.
    """
    result: dict[str, Any] = {}
    for key, caster in _HYPERPARAM_COERCERS.items():
        raw = params.get(key)
        if raw is None:
            continue
        try:
            result[key] = caster(raw)
        except (ValueError, TypeError):
            continue
    return result


def _get_mlflow_experiment_id() -> str | None:
    """Retrieve the MLflow experiment ID for the anvil experiment.

    Queries MLflow for an experiment named ``anvil`` and returns its ID
    if found. Returns ``None`` if the experiment does not exist or if
    querying fails.

    Returns
    -------
    str | None
        MLflow experiment ID string, or ``None`` if not found or on error.
    """
    try:
        client = MlflowClient(tracking_uri=get_config()["mlflow_uri"])
        exp = client.get_experiment_by_name("anvil")
        return exp.experiment_id if exp else None
    except MlflowException:
        return None


@router.get("/experiments")
async def list_experiments(request: Request) -> dict[str, Any]:
    """List all experiments with enrichment data.

    Retrieves all experiments from the tracking service and enriches them
    with dataset/corpus names from the database and artifact availability
    flags. Also includes MLflow experiment metadata and browser URI.

    GET /v1/experiments

    Parameters
    ----------
    request : Request
        FastAPI request object used to construct absolute MLflow URLs.

    Returns
    -------
    dict
        Dictionary containing ``mlflow_experiment_id`` (str or None),
        ``mlflow_url`` (str or None), and ``experiments`` (list of dicts)
        with enriched experiment data.
    """
    tracking_svc = TrackingService()
    experiments = await tracking_svc.list_experiments()

    # Enrich with dataset/corpus names and artifact availability
    from ...db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        from ...db.repositories.corpora import CorpusRepository
        from ...db.repositories.datasets import DatasetRepository

        ds_repo = DatasetRepository(session)
        corp_repo = CorpusRepository(session)

        for exp in experiments:
            # Resolve dataset name from DB if not already set via MLflow tag
            if not exp.get("dataset_name"):
                ds_id = exp.get("dataset_id")
                if ds_id:
                    try:
                        ds = await ds_repo.get(int(ds_id))
                        if ds:
                            exp["dataset_name"] = ds.name
                    except (ValueError, OSError):
                        pass
            else:
                # Fall back to corpus name if no dataset_id
                corp_id = exp.get("corpus_id")
                if corp_id:
                    try:
                        corp = await corp_repo.get(int(corp_id))
                        if corp:
                            exp["dataset_name"] = corp.name
                    except (ValueError, OSError):
                        pass

            # Check artifact availability
            exp["artifact_available"] = (
                Path(f"data/models/experiment_{exp['id']}.json").exists()
                if exp.get("id")
                else False
            )

    mlflow_exp_id = _get_mlflow_experiment_id()
    return {
        "mlflow_experiment_id": mlflow_exp_id,
        "mlflow_url": (
            f"{get_mlflow_browser_uri(request)}/#/experiments/{mlflow_exp_id}"
            if mlflow_exp_id
            else None
        ),
        "experiments": experiments,
    }


@router.get("/experiments/compare")
async def compare_experiments(
    experiment_ids: list[int] = Query(...),
) -> dict[str, Any]:
    """Compare multiple experiments by ID.

    Retrieves a summary of each specified experiment including status,
    final loss, and creation timestamp for side-by-side comparison.

    GET /v1/experiments/compare?id=1&id=2&id=3

    Parameters
    ----------
    id : list[int]
        List of experiment IDs to compare. Required; at least one ID
        must be provided via query parameter.

    Returns
    -------
    dict
        Dictionary containing ``experiments`` list with summary dicts
        for each found experiment.
    """
    tracking_svc = TrackingService()
    experiments = []
    for eid in experiment_ids:
        exp = await tracking_svc.get_experiment(eid)
        if exp:
            experiments.append(
                {
                    "id": exp["id"],
                    "status": exp["status"],
                    "final_loss": exp["final_loss"],
                    "created_at": exp.get("created_at", ""),
                }
            )
    return {"experiments": experiments}


@router.get("/experiments/{experiment_id}")
async def get_experiment(
    experiment_id: int,
    request: Request,
) -> dict[str, Any]:
    """Retrieve a single experiment with full details.

    Fetches comprehensive experiment data including model architecture,
    hyperparameters, MLflow metrics and parameters, GPU utilization,
    memory estimates, and artifact availability.

    GET /v1/experiments/{id}

    Parameters
    ----------
    id : int
        Experiment ID to retrieve.
    request : Request
        FastAPI request object used to construct absolute MLflow URLs.

    Returns
    -------
    dict
        Full experiment details including ``id``, ``status``, ``run_name``,
        ``final_loss``, ``hyperparameters``, ``model_architecture``,
        ``memory_estimate``, ``gpu_memory_peak_gb``, ``gpu_util_peak_pct``,
        ``mlflow``, ``safetensors_artifacts``, and more.

    Raises
    ------
    HTTPException
        404 if the experiment is not found.
    """
    tracking_svc = TrackingService()
    exp = await tracking_svc.get_experiment(experiment_id)
    if exp is None:
        raise HTTPException(status_code=404, detail="Experiment not found")

    mlflow_run_id = exp.get("mlflow_run_id")
    params = exp.get("params", {})
    tags = exp.get("tags", {})

    # Model architecture from saved artifact
    model_architecture = None
    model_path = Path(f"data/models/experiment_{experiment_id}.json")
    if model_path.exists():
        try:
            with open(model_path) as f:
                model_data = json.load(f)
            vocab_size = model_data["vocab_size"]
            n_embd = model_data["n_embd"]
            n_head = model_data["n_head"]
            n_layer = model_data["n_layer"]
            block_size = model_data["block_size"]
            gpt = LlamaModel(vocab_size, n_embd, n_head, n_layer, block_size)
            model_architecture = {
                "vocab_size": vocab_size,
                "n_embd": n_embd,
                "n_head": n_head,
                "n_layer": n_layer,
                "block_size": block_size,
                "num_params": gpt.num_params(),
            }
        except (json.JSONDecodeError, OSError, ValueError, TypeError, KeyError):
            model_architecture = None

    # Hyperparameters from MLflow params
    hyperparameters = _hyperparams_from_mlflow(params)

    # MLflow data
    mlflow_data = None
    safetensors_artifacts = None
    gpu_memory_peak_gb = None
    gpu_util_peak_pct = None
    if mlflow_run_id:
        try:
            client = MlflowClient(tracking_uri=get_config()["mlflow_uri"])
            run = client.get_run(mlflow_run_id)
            mlflow_exp_id = _get_mlflow_experiment_id()
            mlflow_data = {
                "params": dict(run.data.params),
                "metrics": dict(run.data.metrics),
                "run_url": (
                    f"{get_mlflow_browser_uri(request)}/#/experiments/{mlflow_exp_id}/runs/{mlflow_run_id}"
                    if mlflow_exp_id
                    else None
                ),
            }
            # Peak GPU memory / utilization from per-step metric histories
            if GPU_MEMORY_METRIC in run.data.metrics:
                mem_hist = client.get_metric_history(mlflow_run_id, GPU_MEMORY_METRIC)
                if mem_hist:
                    gpu_memory_peak_gb = max(m.value for m in mem_hist)
            if GPU_UTIL_METRIC in run.data.metrics:
                util_hist = client.get_metric_history(mlflow_run_id, GPU_UTIL_METRIC)
                if util_hist:
                    gpu_util_peak_pct = max(m.value for m in util_hist)
            # T049: Query safetensors artifacts from MLflow
            safetensors_artifacts = await tracking_svc.get_safetensors_artifacts(
                mlflow_run_id
            )
        except MlflowException:
            mlflow_data = None

    # Calculate duration
    duration_seconds = None
    created_at = exp.get("created_at", "")
    completed_at = exp.get("completed_at")
    if created_at and completed_at:
        try:
            start_ts = int(created_at) / 1000 if created_at.isdigit() else None
            end_ts = int(completed_at) / 1000 if completed_at.isdigit() else None
            if start_ts and end_ts:
                duration_seconds = end_ts - start_ts
        except (ValueError, TypeError):
            pass

    # Estimated training memory footprint from architecture
    memory_estimate = None
    if model_architecture:
        est = estimate_training_memory(
            vocab_size=model_architecture["vocab_size"],
            n_embd=model_architecture["n_embd"],
            n_head=model_architecture["n_head"],
            n_layer=model_architecture["n_layer"],
            block_size=model_architecture["block_size"],
        )
        memory_estimate = {
            "param_count": est.param_count,
            "weights_mb": round(est.weights_bytes / (1024**2), 1),
            "gradients_mb": round(est.gradients_bytes / (1024**2), 1),
            "optimizer_mb": round(est.optimizer_bytes / (1024**2), 1),
            "kv_cache_mb": round(est.kv_cache_bytes / (1024**2), 1),
            "peak_mb": round(est.peak_mb, 1),
            "peak_gb": round(est.peak_gb, 3),
        }

    # Architecture type from safetensors config or tag
    architecture_type = tags.get("architectures")

    # Dataset/corpus name lookup
    dataset_name = exp.get("dataset_name")
    if not dataset_name:
        ds_id = params.get("dataset_id")
        if ds_id:
            try:
                from ...db.repositories.datasets import DatasetRepository
                from ...db.session import AsyncSessionLocal

                async with AsyncSessionLocal() as sess:
                    ds_repo = DatasetRepository(sess)
                    ds = await ds_repo.get(int(ds_id))
                    if ds:
                        dataset_name = ds.name
            except (ValueError, OSError):
                pass
        else:
            corp_id = params.get("corpus_id")
            if corp_id:
                try:
                    from ...db.repositories.corpora import CorpusRepository
                    from ...db.session import AsyncSessionLocal

                    async with AsyncSessionLocal() as sess:
                        corp_repo = CorpusRepository(sess)
                        corp = await corp_repo.get(int(corp_id))
                        if corp:
                            dataset_name = corp.name
                except (ValueError, OSError):
                    pass

    return {
        "id": exp["id"],
        "status": exp["status"],
        "run_name": exp["run_name"],
        "final_loss": exp["final_loss"],
        "config_id": None,
        "mlflow_run_id": mlflow_run_id,
        "created_at": exp.get("created_at", ""),
        "completed_at": exp.get("completed_at"),
        "dataset_name": dataset_name,
        "duration_seconds": duration_seconds,
        "hyperparameters": hyperparameters,
        "model_architecture": model_architecture,
        "memory_estimate": memory_estimate,
        "gpu_memory_peak_gb": gpu_memory_peak_gb,
        "gpu_util_peak_pct": gpu_util_peak_pct,
        "mlflow": mlflow_data,
        "safetensors_artifacts": safetensors_artifacts,
        "architecture_type": architecture_type,
        "input_digest": exp.get("input_digest"),
        "input_role": exp.get("input_role"),
        "engine_backend": exp.get("engine_backend", ""),
        "device": exp.get("device", ""),
    }


@router.get("/experiments/{experiment_id}/mlflow")
async def get_experiment_mlflow(experiment_id: int, request: Request) -> dict[str, Any]:
    """Retrieve full MLflow data for an experiment.

    Returns comprehensive MLflow run data including all parameters, metrics,
    metric histories, artifact paths, and safetensors artifact info.

    GET /v1/experiments/{id}/mlflow

    Parameters
    ----------
    id : int
        Experiment ID to retrieve MLflow data for.
    request : Request
        FastAPI request object used to construct absolute MLflow run URLs.

    Returns
    -------
    dict
        Dictionary containing ``mlflow_run_id``, ``params``, ``metrics``,
        ``metric_histories``, ``artifacts``, ``safetensors_artifacts``,
        and ``run_url``. Returns empty collections on error.

    Raises
    ------
    HTTPException
        404 if the experiment is not found.
    """
    tracking_svc = TrackingService()
    exp = await tracking_svc.get_experiment(experiment_id)
    if exp is None:
        raise HTTPException(status_code=404, detail="Experiment not found")

    mlflow_run_id = exp.get("mlflow_run_id")
    if not mlflow_run_id:
        return {
            "mlflow_run_id": None,
            "params": {},
            "metrics": {},
            "metric_histories": {},
            "artifacts": [],
            "safetensors_artifacts": None,
            "run_url": None,
        }

    try:
        client = MlflowClient(tracking_uri=get_config()["mlflow_uri"])
        run = client.get_run(mlflow_run_id)

        # Full per-step histories for all metrics
        metric_histories = {}
        for metric_name in run.data.metrics:
            history = client.get_metric_history(mlflow_run_id, metric_name)
            metric_histories[metric_name] = [
                {"step": m.step, "value": m.value, "timestamp": m.timestamp}
                for m in history
            ]

        # List artifact file names
        try:
            artifacts = client.list_artifacts(mlflow_run_id)
            artifact_paths = [a.path for a in artifacts]
        except MlflowException:
            artifact_paths = []

        # T049: Query safetensors artifact info
        safetensors_artifacts = await tracking_svc.get_safetensors_artifacts(
            mlflow_run_id
        )

        mlflow_exp_id = _get_mlflow_experiment_id()

        return {
            "mlflow_run_id": mlflow_run_id,
            "params": dict(run.data.params),
            "metrics": dict(run.data.metrics),
            "metric_histories": metric_histories,
            "artifacts": artifact_paths,
            "safetensors_artifacts": safetensors_artifacts,
            "run_url": (
                f"{get_mlflow_browser_uri(request)}/#/experiments/{mlflow_exp_id}/runs/{mlflow_run_id}"
                if mlflow_exp_id
                else None
            ),
        }
    except MlflowException as e:
        return {
            "mlflow_run_id": mlflow_run_id,
            "params": {},
            "metrics": {},
            "metric_histories": {},
            "artifacts": [],
            "safetensors_artifacts": None,
            "run_url": None,
            "error": str(e),
        }


@router.get("/experiments/{experiment_id}/metrics")
async def get_experiment_metrics(experiment_id: int) -> dict[str, Any]:
    """Retrieve the loss metric history for an experiment.

    Returns step-by-step loss values recorded during training via MLflow.

    GET /v1/experiments/{id}/metrics

    Parameters
    ----------
    id : int
        Experiment ID to retrieve metrics for.

    Returns
    -------
    dict
        Dictionary containing ``metrics`` list with ``step`` and ``loss``
        values, and ``mlflow_run_id``.

    Raises
    ------
    HTTPException
        404 if the experiment is not found.
    """
    tracking_svc = TrackingService()
    exp = await tracking_svc.get_experiment(experiment_id)
    if exp is None:
        raise HTTPException(status_code=404, detail="Experiment not found")

    mlflow_run_id = exp.get("mlflow_run_id")
    if not mlflow_run_id:
        return {"metrics": [], "mlflow_run_id": None}

    try:
        client = MlflowClient(tracking_uri=get_config()["mlflow_uri"])
        metric_history = client.get_metric_history(mlflow_run_id, "loss")
        metrics = [{"step": m.step, "loss": m.value} for m in metric_history]
        return {"metrics": metrics, "mlflow_run_id": mlflow_run_id}
    except MlflowException as e:
        return {"metrics": [], "mlflow_run_id": mlflow_run_id, "error": str(e)}


@router.delete("/experiments/{experiment_id}")
async def delete_experiment(experiment_id: int) -> dict[str, Any]:
    """Delete an experiment and its associated MLflow run.

    Removes the experiment from the tracking service and deletes the
    corresponding MLflow run if one is linked.

    DELETE /v1/experiments/{id}

    Parameters
    ----------
    id : int
        Experiment ID to delete.

    Returns
    -------
    dict
        Dictionary containing ``status: "deleted"``.

    Raises
    ------
    HTTPException
        404 if the experiment is not found.
    """
    tracking_svc = TrackingService()
    exp = await tracking_svc.get_experiment(experiment_id)
    if exp is None:
        raise HTTPException(status_code=404, detail="Experiment not found")

    mlflow_run_id = exp.get("mlflow_run_id")
    if mlflow_run_id:
        loop = asyncio.get_event_loop()
        try:
            client = (
                tracking_svc._client
                or await loop.run_in_executor(  # pylint: disable=protected-access
                    None,
                    lambda: tracking_svc._lazy_init(),  # pylint: disable=protected-access,unnecessary-lambda
                )
            )
            if client:
                await loop.run_in_executor(
                    None, lambda: client.delete_run(mlflow_run_id)
                )
        except MlflowException:
            pass
    return {"status": "deleted"}


@router.get("/experiments/{experiment_id}/runs/{run_id}/artifacts")
async def list_artifacts(
    experiment_id: int,
    run_id: str,
) -> dict[str, Any]:
    """List all safetensors export artifacts for a given experiment and run.

    Returns availability status, file metadata, and classification for each
    artifact including whether it is a safetensors model, config, or tokenizer.

    GET /v1/experiments/{experiment_id}/runs/{run_id}/artifacts

    Parameters
    ----------
    experiment_id : int
        ID of the experiment to list artifacts for.
    run_id : str
        MLflow run ID for the experiment.

    Returns
    -------
    dict
        Dictionary containing ``available`` (bool), ``files`` (list of dicts
        with ``path``, ``file_size``, ``is_safetensors``, ``is_config``,
        ``is_tokenizer``), and ``error`` (str or None).

    Raises
    ------
    HTTPException
        404 if the experiment is not found or has no associated MLflow run.
        400 if the run ID does not match the experiment.
    """
    tracking_svc = TrackingService()
    exp = await tracking_svc.get_experiment(experiment_id)
    if exp is None:
        raise HTTPException(status_code=404, detail="Experiment not found")
    if not exp.get("mlflow_run_id"):
        raise HTTPException(status_code=404, detail="No MLflow run associated")
    if exp["mlflow_run_id"] != run_id:
        raise HTTPException(status_code=400, detail="Run ID does not match experiment")

    artifacts_info = await tracking_svc.get_safetensors_artifacts(run_id)
    return artifacts_info


@router.get("/experiments/{experiment_id}/runs/{run_id}/download")
async def download_artifact(
    experiment_id: int,
    run_id: str,
    path: str = Query(..., description="Artifact file path to download"),
) -> FileResponse:
    """Download a single artifact file for a given experiment and run.

    Downloads an artifact from MLflow storage to a temporary location and
    serves it as a file attachment with the original filename preserved.

    GET /v1/experiments/{experiment_id}/runs/{run_id}/download?path=...

    Parameters
    ----------
    experiment_id : int
        ID of the experiment the artifact belongs to.
    run_id : str
        MLflow run ID for the experiment.
    path : str
        Artifact path to download (e.g., ``model.safetensors``,
        ``config.json``, ``tokenizer.json``).

    Returns
    -------
    FileResponse
        FastAPI FileResponse with the downloaded file as
        ``application/octet-stream``.

    Raises
    ------
    HTTPException
        404 if the experiment is not found, has no associated MLflow run,
        or the requested artifact path is not found.
        400 if the run ID does not match the experiment.
        500 if the download fails or the artifact is not a valid file.
    """
    tracking_svc = TrackingService()
    exp = await tracking_svc.get_experiment(experiment_id)
    if exp is None:
        raise HTTPException(status_code=404, detail="Experiment not found")
    if not exp.get("mlflow_run_id"):
        raise HTTPException(status_code=404, detail="No MLflow run associated")
    if exp["mlflow_run_id"] != run_id:
        raise HTTPException(status_code=400, detail="Run ID does not match experiment")

    artifacts_info = await tracking_svc.get_safetensors_artifacts(run_id)
    if not artifacts_info["available"]:
        raise HTTPException(
            status_code=404,
            detail="No safetensors artifacts found for this run",
        )

    # Verify the requested path exists in the artifact list
    matching = [f for f in artifacts_info["files"] if f["path"] == path]
    if not matching:
        raise HTTPException(
            status_code=404,
            detail=f"Artifact '{path}' not found. Available: {[f['path'] for f in artifacts_info['files']]}",
        )

    # Download artifact from MLflow to a temp location
    try:
        client = MlflowClient(tracking_uri=get_config()["mlflow_uri"])
        loop = asyncio.get_event_loop()
        local_path = await loop.run_in_executor(
            None,
            lambda: client.download_artifacts(run_id, path, dst_path=None),
        )
        if not os.path.isfile(local_path):
            raise HTTPException(
                status_code=500, detail="Downloaded artifact is not a file"
            )
        # Use the original filename for the download
        filename = os.path.basename(path)
        return FileResponse(
            path=local_path,
            filename=filename,
            media_type="application/octet-stream",
        )
    except HTTPException:  # pylint: disable=try-except-raise
        raise
    except (MlflowException, OSError) as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to download artifact: {e!s}"
        ) from e


@router.post("/experiments/{experiment_id}/retry-export")
async def retry_export(experiment_id: int) -> dict[str, Any]:
    """Retry safetensors export from a finished experiment's model artifact.

    Exports the model from an existing ``model.json`` artifact to safetensors
    format, logs the artifacts to MLflow, and returns the exported file paths.

    POST /v1/experiments/{experiment_id}/retry-export

    Parameters
    ----------
    experiment_id : int
        ID of the experiment to retry export for. The experiment must have
        a completed ``model.json`` artifact.

    Returns
    -------
    dict
        Dictionary containing ``status``, ``safetensors_path``,
        ``config_path``, and ``tokenizer_path``.

    Raises
    ------
    HTTPException
        404 if the experiment is not found or has no model artifact.
        500 if the export retry fails.
    """
    tracking_svc = TrackingService()
    exp = await tracking_svc.get_experiment(experiment_id)
    if exp is None:
        raise HTTPException(status_code=404, detail="Experiment not found")

    model_path = Path(f"data/models/experiment_{experiment_id}.json")
    if not model_path.exists():
        raise HTTPException(
            status_code=404,
            detail="No model artifact found for this experiment. Complete training first.",
        )

    output_dir = Path(f"data/models/export_{experiment_id}")
    output_dir.mkdir(parents=True, exist_ok=True)

    from ...services.training.export import SafetensorsExportService as ExportService

    loop = asyncio.get_event_loop()
    export_svc = ExportService()
    result = await loop.run_in_executor(
        None, lambda: export_svc.retry_export(str(model_path), str(output_dir))
    )

    if result["error"]:
        raise HTTPException(
            status_code=500, detail=f"Export retry failed: {result['error']}"
        )

    mlflow_run_id = exp.get("mlflow_run_id")
    if mlflow_run_id:
        if result.get("safetensors_path"):
            await tracking_svc.log_artifacts(
                mlflow_run_id,
                safetensors_path=result["safetensors_path"],
                config_path=result.get("config_path"),
                tokenizer_path=result.get("tokenizer_path"),
                mlmodel_path=result.get("mlmodel_path"),
                conda_path=result.get("conda_path"),
            )

    return {
        "status": "exported",
        "safetensors_path": result["safetensors_path"],
        "config_path": result["config_path"],
        "tokenizer_path": result["tokenizer_path"],
    }
