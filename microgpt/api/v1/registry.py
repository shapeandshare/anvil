from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from mlflow.tracking import MlflowClient

from microgpt.api.deps import get_db_session
from microgpt.db.repositories.models import ModelRepository
from microgpt.db.repositories.experiments import ExperimentRepository
from microgpt.services.models import ModelRegistryService

router = APIRouter()
MLFLOW_TRACKING_URI = "sqlite:///./mlruns/mlflow.db"


async def get_service(session: AsyncSession = Depends(get_db_session)):
    repo = ModelRepository(session)
    return ModelRegistryService(repo)


@router.post("/registry/models", status_code=201)
async def register_model(
    body: dict,
    svc: ModelRegistryService = Depends(get_service),
    session: AsyncSession = Depends(get_db_session),
):
    experiment_id = body.get("experiment_id")
    name = body.get("name")
    description = body.get("description")

    if not experiment_id:
        raise HTTPException(status_code=400, detail="experiment_id required")
    if not name or not name.strip():
        raise HTTPException(status_code=400, detail="name required")

    exp_repo = ExperimentRepository(session)
    experiment = await exp_repo.get(experiment_id)
    if experiment is None:
        raise HTTPException(status_code=400, detail="Experiment not found")
    if experiment.status != "completed":
        raise HTTPException(
            status_code=400,
            detail="Cannot register model from an experiment that is not completed",
        )

    from pathlib import Path
    experiment_artifact = Path("data/models") / f"experiment_{experiment_id}.json"
    artifact_source = str(experiment_artifact) if experiment_artifact.exists() else None

    hyperparameters = None
    from microgpt.db.models.training_config import TrainingConfig
    from sqlalchemy import select
    if experiment.config_id:
        result = await session.execute(
            select(TrainingConfig).where(TrainingConfig.id == experiment.config_id)
        )
        config = result.scalar_one_or_none()
        if config:
            hyperparameters = {
                "n_layer": config.n_layer,
                "n_embd": config.n_embd,
                "n_head": config.n_head,
                "block_size": config.block_size,
                "num_steps": config.num_steps,
                "learning_rate": config.learning_rate,
                "temperature": config.temperature,
            }

    dataset_name = None
    if experiment.dataset_id:
        from microgpt.db.models.training_config import Dataset
        result = await session.execute(
            select(Dataset).where(Dataset.id == experiment.dataset_id)
        )
        ds = result.scalar_one_or_none()
        if ds:
            dataset_name = ds.name

    result = await svc.register_model(
        experiment_id=experiment_id,
        name=name.strip(),
        description=description,
        artifact_source_path=artifact_source,
        final_loss=experiment.final_loss,
        dataset_name=dataset_name,
        hyperparameters=hyperparameters,
    )
    return result


@router.get("/registry/models")
async def list_registered_models(
    search: str | None = Query(None),
    svc: ModelRegistryService = Depends(get_service),
):
    models = await svc.list_models(search=search)
    return {"models": models}


@router.get("/registry/models/{model_id}")
async def get_model(
    model_id: int,
    svc: ModelRegistryService = Depends(get_service),
):
    model = await svc.get_model(model_id)
    if model is None:
        raise HTTPException(status_code=404, detail="Model not found")
    return model


@router.get("/registry/models/{model_id}/versions/{version}")
async def get_version(
    model_id: int,
    version: int,
    svc: ModelRegistryService = Depends(get_service),
):
    v = await svc.get_version(model_id, version)
    if v is None:
        raise HTTPException(status_code=404, detail="Version not found")
    return v


@router.delete("/registry/models/{model_id}/versions/{version}")
async def delete_version(
    model_id: int,
    version: int,
    svc: ModelRegistryService = Depends(get_service),
):
    name = await svc.delete_version(model_id, version)
    if name is None:
        raise HTTPException(status_code=404, detail="Model or version not found")
    return {"message": f"Version {version} of '{name}' deleted"}


@router.delete("/registry/models/{model_id}")
async def delete_model(
    model_id: int,
    svc: ModelRegistryService = Depends(get_service),
):
    name = await svc.delete_model(model_id)
    if name is None:
        raise HTTPException(status_code=404, detail="Model not found")
    return {"message": f"Model '{name}' and all versions deleted"}