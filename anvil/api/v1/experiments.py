import asyncio
import json
import os
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from mlflow.tracking import MlflowClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from anvil.api.deps import get_db_session
from anvil.config import get_config, get_mlflow_uri
from anvil.core.engine import LlamaModel
from anvil.db.models.training_config import TrainingConfig
from anvil.db.repositories import ExperimentRepository
from anvil.services.experiments import ExperimentService
from anvil.services.tracking import TrackingService

router = APIRouter()


def _get_mlflow_experiment_id() -> str | None:
    try:
        client = MlflowClient(tracking_uri=get_config()["mlflow_uri"])
        exp = client.get_experiment_by_name("anvil")
        return exp.experiment_id if exp else None
    except Exception:
        return None


async def get_service(session: AsyncSession = Depends(get_db_session)):
    repo = ExperimentRepository(session)
    return ExperimentService(repo)


@router.get("/experiments")
async def list_experiments(svc: ExperimentService = Depends(get_service)):
    experiments = await svc.list_experiments()
    mlflow_exp_id = _get_mlflow_experiment_id()
    return {
        "mlflow_experiment_id": mlflow_exp_id,
        "mlflow_url": (
            f"{get_mlflow_uri()}/#/experiments/{mlflow_exp_id}"
            if mlflow_exp_id
            else None
        ),
        "experiments": [
            {
                "id": e.id,
                "status": e.status,
                "run_name": e.run_name,
                "final_loss": e.final_loss,
                "config_id": e.config_id,
                "mlflow_run_id": e.mlflow_run_id,
                "mlflow_run_url": (
                    f"{get_mlflow_uri()}/#/experiments/{mlflow_exp_id}/runs/{e.mlflow_run_id}"
                    if (mlflow_exp_id and e.mlflow_run_id)
                    else None
                ),
                "created_at": str(e.created_at),
                "artifact_available": Path(
                    f"data/models/experiment_{e.id}.json"
                ).exists(),
                "dataset_name": e.dataset.name if e.dataset_id else None,
                "input_digest": e.input_digest,
                "input_role": e.input_role,
                "engine_backend": e.engine_backend,
                "device": e.device,
            }
            for e in experiments
        ],
    }


@router.get("/experiments/compare")
async def compare_experiments(
    id: list[int] = Query(...), svc: ExperimentService = Depends(get_service)
):
    experiments = []
    for eid in id:
        exp = await svc.get_experiment(eid)
        if exp:
            experiments.append(
                {
                    "id": exp.id,
                    "status": exp.status,
                    "final_loss": exp.final_loss,
                    "created_at": str(exp.created_at),
                }
            )
    return {"experiments": experiments}


@router.get("/experiments/{id}")
async def get_experiment(
    id: int,
    svc: ExperimentService = Depends(get_service),
    session: AsyncSession = Depends(get_db_session),
):
    exp = await svc.get_experiment(id)
    if exp is None:
        raise HTTPException(status_code=404, detail="Experiment not found")

    # Load training config
    config = None
    if exp.config_id:
        result = await session.execute(
            select(TrainingConfig).where(TrainingConfig.id == exp.config_id)
        )
        config = result.scalar_one_or_none()

    # Calculate duration
    duration_seconds = None
    if exp.started_at and exp.completed_at:
        duration_seconds = (exp.completed_at - exp.started_at).total_seconds()

    # Model architecture from saved artifact
    model_architecture = None
    model_path = Path(f"data/models/experiment_{exp.id}.json")
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

    # Hyperparameters from config
    hyperparameters = {}
    if config:
        hyperparameters = {
            "n_layer": config.n_layer,
            "n_embd": config.n_embd,
            "n_head": config.n_head,
            "block_size": config.block_size,
            "num_steps": config.num_steps,
            "learning_rate": config.learning_rate,
            "beta1": config.beta1,
            "beta2": config.beta2,
            "temperature": config.temperature,
            "use_gpu": config.use_gpu,
            "dataset_id": config.dataset_id,
            "corpus_id": config.corpus_id,
        }

    # MLflow data
    mlflow_data = None
    safetensors_artifacts = None
    if exp.mlflow_run_id:
        try:
            client = MlflowClient(tracking_uri=get_config()["mlflow_uri"])
            run = client.get_run(exp.mlflow_run_id)
            mlflow_exp_id = _get_mlflow_experiment_id()
            mlflow_data = {
                "params": dict(run.data.params),
                "metrics": dict(run.data.metrics),
                "run_url": (
                    f"{get_mlflow_uri()}/#/experiments/{mlflow_exp_id}/runs/{exp.mlflow_run_id}"
                    if mlflow_exp_id
                    else None
                ),
            }
            # T049: Query safetensors artifacts from MLflow
            tracking_svc = TrackingService(tracking_uri=get_config()["mlflow_uri"])
            safetensors_artifacts = await tracking_svc.get_safetensors_artifacts(
                exp.mlflow_run_id
            )
        except Exception:
            mlflow_data = None

    # Architecture type from safetensors config or tag
    architecture_type = None
    if exp.mlflow_run_id:
        try:
            client = MlflowClient(tracking_uri=get_config()["mlflow_uri"])
            run = client.get_run(exp.mlflow_run_id)
            tags = dict(run.data.tags)
            architecture_type = tags.get("architectures")
        except Exception:
            pass

    return {
        "id": exp.id,
        "status": exp.status,
        "run_name": exp.run_name,
        "final_loss": exp.final_loss,
        "config_id": exp.config_id,
        "mlflow_run_id": exp.mlflow_run_id,
        "created_at": str(exp.created_at),
        "completed_at": str(exp.completed_at) if exp.completed_at else None,
        "dataset_name": exp.dataset.name if exp.dataset_id else None,
        "duration_seconds": duration_seconds,
        "hyperparameters": hyperparameters,
        "model_architecture": model_architecture,
        "mlflow": mlflow_data,
        "safetensors_artifacts": safetensors_artifacts,
        "architecture_type": architecture_type,
        "input_digest": exp.input_digest,
        "input_role": exp.input_role,
        "engine_backend": exp.engine_backend,
        "device": exp.device,
    }


@router.get("/experiments/{id}/mlflow")
async def get_experiment_mlflow(id: int, svc: ExperimentService = Depends(get_service)):
    exp = await svc.get_experiment(id)
    if exp is None:
        raise HTTPException(status_code=404, detail="Experiment not found")
    if not exp.mlflow_run_id:
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
        run = client.get_run(exp.mlflow_run_id)

        # Full per-step histories for all metrics
        metric_histories = {}
        for metric_name in run.data.metrics:
            history = client.get_metric_history(exp.mlflow_run_id, metric_name)
            metric_histories[metric_name] = [
                {"step": m.step, "value": m.value, "timestamp": m.timestamp}
                for m in history
            ]

        # List artifact file names
        try:
            artifacts = client.list_artifacts(exp.mlflow_run_id)
            artifact_paths = [a.path for a in artifacts]
        except Exception:
            artifact_paths = []

        # T049: Query safetensors artifact info
        tracking_svc = TrackingService(tracking_uri=get_config()["mlflow_uri"])
        safetensors_artifacts = await tracking_svc.get_safetensors_artifacts(
            exp.mlflow_run_id
        )

        mlflow_exp_id = _get_mlflow_experiment_id()

        return {
            "mlflow_run_id": exp.mlflow_run_id,
            "params": dict(run.data.params),
            "metrics": dict(run.data.metrics),
            "metric_histories": metric_histories,
            "artifacts": artifact_paths,
            "safetensors_artifacts": safetensors_artifacts,
            "run_url": (
                f"{get_mlflow_uri()}/#/experiments/{mlflow_exp_id}/runs/{exp.mlflow_run_id}"
                if mlflow_exp_id
                else None
            ),
        }
    except Exception as e:
        return {
            "mlflow_run_id": exp.mlflow_run_id,
            "params": {},
            "metrics": {},
            "metric_histories": {},
            "artifacts": [],
            "safetensors_artifacts": None,
            "run_url": None,
            "error": str(e),
        }


@router.get("/experiments/{id}/metrics")
async def get_experiment_metrics(
    id: int, svc: ExperimentService = Depends(get_service)
):
    exp = await svc.get_experiment(id)
    if exp is None:
        raise HTTPException(status_code=404, detail="Experiment not found")
    if not exp.mlflow_run_id:
        return {"metrics": [], "mlflow_run_id": None}
    try:
        client = MlflowClient(tracking_uri=get_config()["mlflow_uri"])
        metric_history = client.get_metric_history(exp.mlflow_run_id, "loss")
        metrics = [{"step": m.step, "loss": m.value} for m in metric_history]
        return {"metrics": metrics, "mlflow_run_id": exp.mlflow_run_id}
    except Exception as e:
        return {"metrics": [], "mlflow_run_id": exp.mlflow_run_id, "error": str(e)}


@router.delete("/experiments/{id}")
async def delete_experiment(id: int, svc: ExperimentService = Depends(get_service)):
    await svc.delete_experiment(id)
    return {"status": "deleted"}


@router.get("/experiments/{experiment_id}/runs/{run_id}/download/safetensors")
async def download_safetensors(
    experiment_id: int,
    run_id: str,
    svc: ExperimentService = Depends(get_service),
):
    """Download safetensors checkpoint for a given experiment/run.

    The run_id is the MLflow run ID. Looks up the file from MLflow artifact store
    and streams it to the client.
    """
    exp = await svc.get_experiment(experiment_id)
    if exp is None:
        raise HTTPException(status_code=404, detail="Experiment not found")
    if not exp.mlflow_run_id:
        raise HTTPException(status_code=404, detail="No MLflow run associated")
    if exp.mlflow_run_id != run_id:
        raise HTTPException(status_code=400, detail="Run ID does not match experiment")

    tracking_svc = TrackingService(tracking_uri=get_config()["mlflow_uri"])
    artifacts_info = await tracking_svc.get_safetensors_artifacts(run_id)
    if not artifacts_info["available"]:
        raise HTTPException(
            status_code=404,
            detail="No safetensors artifacts found for this run",
        )

    safetensors_file = next(
        (f for f in artifacts_info["files"] if f["is_safetensors"]), None
    )
    if safetensors_file is None:
        raise HTTPException(
            status_code=404,
            detail="No safetensors file found",
        )

    # Download artifact from MLflow to a temp location
    try:
        client = MlflowClient(tracking_uri=get_config()["mlflow_uri"])
        loop = asyncio.get_event_loop()
        local_path = await loop.run_in_executor(
            None,
            lambda: client.download_artifacts(
                run_id, safetensors_file["path"], dst_path=None
            ),
        )
        if not os.path.isfile(local_path):
            raise HTTPException(
                status_code=500, detail="Downloaded artifact is not a file"
            )
        return FileResponse(
            path=local_path,
            filename="model.safetensors",
            media_type="application/octet-stream",
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to download safetensors: {str(e)}"
        )


@router.post("/experiments/{experiment_id}/retry-export")
async def retry_export(experiment_id: int, svc: ExperimentService = Depends(get_service)):
    """Retry safetensors export from a finished experiment's model.json."""
    exp = await svc.get_experiment(experiment_id)
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

    if exp.mlflow_run_id:
        tracking_svc = TrackingService(tracking_uri=get_config()["mlflow_uri"])
        if result.get("safetensors_path"):
            await tracking_svc.log_artifacts(
                exp.mlflow_run_id,
                safetensors_path=result["safetensors_path"],
                config_path=result.get("config_path"),
                tokenizer_path=result.get("tokenizer_path"),
            )

    return {
        "status": "exported",
        "safetensors_path": result["safetensors_path"],
        "config_path": result["config_path"],
        "tokenizer_path": result["tokenizer_path"],
    }
