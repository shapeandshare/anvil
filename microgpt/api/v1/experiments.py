from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from mlflow.tracking import MlflowClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from microgpt.api.deps import get_db_session
from microgpt.db.repositories import ExperimentRepository
from microgpt.services.experiments import ExperimentService

router = APIRouter()
MLFLOW_UI_URI = "http://127.0.0.1:5000"
MLFLOW_TRACKING_URI = "sqlite:///./mlruns/mlflow.db"


def _get_mlflow_experiment_id() -> str | None:
    try:
        client = MlflowClient(tracking_uri=MLFLOW_TRACKING_URI)
        exp = client.get_experiment_by_name("microgpt-workbench")
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
        "mlflow_url": f"{MLFLOW_UI_URI}/#/experiments/{mlflow_exp_id}" if mlflow_exp_id else None,
        "experiments": [
            {
                "id": e.id,
                "status": e.status,
                "final_loss": e.final_loss,
                "config_id": e.config_id,
                "mlflow_run_id": e.mlflow_run_id,
                "mlflow_run_url": f"{MLFLOW_UI_URI}/#/experiments/{mlflow_exp_id}/runs/{e.mlflow_run_id}" if (mlflow_exp_id and e.mlflow_run_id) else None,
                "created_at": str(e.created_at),
                "artifact_available": Path(f"data/models/experiment_{e.id}.json").exists(),
                "dataset_name": e.dataset.name if e.dataset_id else None,
            }
            for e in experiments
        ]
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
                    "generated_samples": exp.generated_samples,
                    "created_at": str(exp.created_at),
                }
            )
    return {"experiments": experiments}


@router.get("/experiments/{id}")
async def get_experiment(id: int, svc: ExperimentService = Depends(get_service)):
    exp = await svc.get_experiment(id)
    if exp is None:
        raise HTTPException(status_code=404, detail="Experiment not found")
    return {
        "id": exp.id,
        "status": exp.status,
        "final_loss": exp.final_loss,
        "generated_samples": exp.generated_samples,
        "config_id": exp.config_id,
        "created_at": str(exp.created_at),
    }


@router.delete("/experiments/{id}")
async def delete_experiment(id: int, svc: ExperimentService = Depends(get_service)):
    await svc.delete_experiment(id)
    return {"status": "deleted"}