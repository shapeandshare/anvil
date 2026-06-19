import asyncio
import json
import os
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse
from mlflow.tracking import MlflowClient

from anvil.config import get_config, get_mlflow_browser_uri
from anvil.core.engine import LlamaModel
from anvil.services.memory_estimator import estimate_training_memory
from anvil.services.tracking import TrackingService

router = APIRouter()

GPU_MEMORY_METRIC = "system/gpu_memory_gb"
GPU_UTIL_METRIC = "system/gpu_util_pct"

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


def _hyperparams_from_mlflow(params: dict[str, str]) -> dict:
    """Reconstruct typed hyperparameters from string-valued MLflow params.

    Used as a fallback when the experiment has no linked TrainingConfig row.
    """
    result: dict = {}
    for key, caster in _HYPERPARAM_COERCERS.items():
        raw = params.get(key)
        if raw is None:
            continue
        try:
            result[key] = caster(raw)
        except (ValueError, TypeError):
            continue
    if "use_gpu" in params:
        result["use_gpu"] = str(params["use_gpu"]).lower() in ("true", "1", "yes")
    return result


def _get_mlflow_experiment_id() -> str | None:
    try:
        client = MlflowClient(tracking_uri=get_config()["mlflow_uri"])
        exp = client.get_experiment_by_name("anvil")
        return exp.experiment_id if exp else None
    except Exception:
        return None


@router.get("/experiments")
async def list_experiments(request: Request):
    tracking_svc = TrackingService()
    experiments = await tracking_svc.list_experiments()

    # Enrich with dataset names and artifact availability
    from anvil.db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        from anvil.db.repositories.datasets import DatasetRepository

        ds_repo = DatasetRepository(session)

        for exp in experiments:
            ds_id = exp.get("dataset_id")
            if ds_id:
                try:
                    ds = await ds_repo.get(int(ds_id))
                    if ds:
                        exp["dataset_name"] = ds.name
                except Exception:
                    pass

            # Check artifact availability
            exp["artifact_available"] = Path(
                f"data/models/experiment_{exp['id']}.json"
            ).exists() if exp.get("id") else False

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
    id: list[int] = Query(...),
):
    tracking_svc = TrackingService()
    experiments = []
    for eid in id:
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


@router.get("/experiments/{id}")
async def get_experiment(
    id: int,
    request: Request,
):
    tracking_svc = TrackingService()
    exp = await tracking_svc.get_experiment(id)
    if exp is None:
        raise HTTPException(status_code=404, detail="Experiment not found")

    mlflow_run_id = exp.get("mlflow_run_id")
    params = exp.get("params", {})
    tags = exp.get("tags", {})

    # Model architecture from saved artifact
    model_architecture = None
    model_path = Path(f"data/models/experiment_{id}.json")
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
        except Exception:
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
                mem_hist = client.get_metric_history(
                    mlflow_run_id, GPU_MEMORY_METRIC
                )
                if mem_hist:
                    gpu_memory_peak_gb = max(m.value for m in mem_hist)
            if GPU_UTIL_METRIC in run.data.metrics:
                util_hist = client.get_metric_history(
                    mlflow_run_id, GPU_UTIL_METRIC
                )
                if util_hist:
                    gpu_util_peak_pct = max(m.value for m in util_hist)
            # T049: Query safetensors artifacts from MLflow
            safetensors_artifacts = await tracking_svc.get_safetensors_artifacts(
                mlflow_run_id
            )
        except Exception:
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
            use_gpu=False,
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

    # Dataset name lookup
    dataset_name = exp.get("dataset_name")
    if not dataset_name:
        ds_id = params.get("dataset_id")
        if ds_id:
            try:
                from anvil.db.repositories.datasets import DatasetRepository
                from anvil.db.session import AsyncSessionLocal

                async with AsyncSessionLocal() as sess:
                    ds_repo = DatasetRepository(sess)
                    ds = await ds_repo.get(int(ds_id))
                    if ds:
                        dataset_name = ds.name
            except Exception:
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


@router.get("/experiments/{id}/mlflow")
async def get_experiment_mlflow(id: int, request: Request):
    tracking_svc = TrackingService()
    exp = await tracking_svc.get_experiment(id)
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
        except Exception:
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
    except Exception as e:
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


@router.get("/experiments/{id}/metrics")
async def get_experiment_metrics(id: int):
    tracking_svc = TrackingService()
    exp = await tracking_svc.get_experiment(id)
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
    except Exception as e:
        return {"metrics": [], "mlflow_run_id": mlflow_run_id, "error": str(e)}


@router.delete("/experiments/{id}")
async def delete_experiment(id: int):
    tracking_svc = TrackingService()
    exp = await tracking_svc.get_experiment(id)
    if exp is None:
        raise HTTPException(status_code=404, detail="Experiment not found")

    mlflow_run_id = exp.get("mlflow_run_id")
    if mlflow_run_id:
        loop = asyncio.get_event_loop()
        try:
            client = tracking_svc._client or await loop.run_in_executor(
                None, lambda: tracking_svc._lazy_init()
            )
            if client:
                await loop.run_in_executor(
                    None, lambda: client.delete_run(mlflow_run_id)
                )
        except Exception:
            pass
    return {"status": "deleted"}


@router.get("/experiments/{experiment_id}/runs/{run_id}/artifacts")
async def list_artifacts(
    experiment_id: int,
    run_id: str,
):
    """List all safetensors export artifacts for a given experiment/run.

    Returns the same structure as get_safetensors_artifacts:
      available: bool
      files: list of {path, file_size, is_safetensors, is_config, is_tokenizer}
      error: str or None
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
):
    """Download a single artifact file for a given experiment/run.

    The path parameter is the artifact path as returned by the artifacts endpoint
    (e.g. 'model.safetensors', 'config.json', 'tokenizer.json').
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
            lambda: client.download_artifacts(
                run_id, path, dst_path=None
            ),
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
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to download artifact: {e!s}"
        ) from e


@router.post("/experiments/{experiment_id}/retry-export")
async def retry_export(experiment_id: int):
    """Retry safetensors export from a finished experiment's model.json."""
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

    from anvil.services.export import SafetensorsExportService as ExportService

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