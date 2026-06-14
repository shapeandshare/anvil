from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from microgpt.api.deps import get_db_session
from microgpt.db.repositories.experiments import ExperimentRepository
from microgpt.db.repositories.models import ModelRepository
from microgpt.services.models import ModelRegistryService

router = APIRouter()


async def get_service(session: AsyncSession = Depends(get_db_session)):
    repo = ModelRepository(session)
    return ModelRegistryService(repo)


@router.post("/registry/models", status_code=201)
async def register_model(
    body: dict,
    session: AsyncSession = Depends(get_db_session),
):
    experiment_id = body.get("experiment_id")
    if not experiment_id:
        raise HTTPException(status_code=400, detail="experiment_id required")

    exp_repo = ExperimentRepository(session)
    experiment = await exp_repo.get(experiment_id)
    if experiment is None:
        raise HTTPException(status_code=400, detail="Experiment not found")
    if experiment.status != "finished":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot register model from an experiment with status '{experiment.status}' (must be 'finished')",
        )
    if not experiment.mlflow_run_id:
        raise HTTPException(status_code=400, detail="Experiment has no MLflow run ID")

    from microgpt.services.tracking import TrackingService

    tracking_svc = TrackingService()
    result = await tracking_svc.register_source_model(
        run_id=experiment.mlflow_run_id,
        dataset_id=experiment.dataset_id,
        corpus_id=experiment.corpus_id,
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
