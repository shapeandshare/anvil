from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from anvil.api.deps import get_db_session
from anvil.db.repositories.experiments import ExperimentRepository
from anvil.db.repositories.models import ModelRepository
from anvil.services.models import ModelRegistryService

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

    from anvil.services.tracking import TrackingService

    # Resolve registry name from the datasource's actual name
    registry_name = None
    if experiment.dataset_id is not None:
        registry_name = experiment.dataset.name if experiment.dataset else None
    elif experiment.corpus_id is not None:
        from anvil.db.repositories.corpora import CorpusRepository
        from anvil.db.session import AsyncSessionLocal

        async with AsyncSessionLocal() as sess:
            corp_repo = CorpusRepository(sess)
            corpus = await corp_repo.get(experiment.corpus_id)
            if corpus:
                registry_name = corpus.name

    tracking_svc = TrackingService()
    result = await tracking_svc.register_source_model(
        run_id=experiment.mlflow_run_id,
        name=registry_name,
        dataset_id=experiment.dataset_id,
        corpus_id=experiment.corpus_id,
    )
    return result


@router.get("/registry/models")
async def list_registered_models(
    search: str | None = Query(None),
):
    from anvil.services.tracking import TrackingService

    tracking_svc = TrackingService()
    models = await tracking_svc.list_registered_models(search=search)
    return {"models": models}


@router.get("/registry/models/{model_id}")
async def get_model(
    model_id: int,
    session: AsyncSession = Depends(get_db_session),
):
    # Try local DB first (registered_models.id path)
    repo = ModelRepository(session)
    svc = ModelRegistryService(repo)
    model = await svc.get_model(model_id)
    if model is not None:
        return model

    # Fallback: treat model_id as experiment_id
    from anvil.db.repositories.experiments import ExperimentRepository

    exp_repo = ExperimentRepository(session)
    exp = await exp_repo.get(model_id)
    if exp is None:
        raise HTTPException(status_code=404, detail="Model not found")

    from datetime import timezone

    return {
        "id": exp.id,
        "name": exp.run_name or f"experiment-{exp.id}",
        "description": f"Trained on dataset {exp.dataset_id or exp.corpus_id or '?'}",
        "versions": [
            {
                "version": 1,
                "experiment_id": exp.id,
                "dataset_name": exp.dataset.name if exp.dataset_id else None,
                "final_loss": exp.final_loss,
                "hyperparameters": None,
                "created_at": str(exp.completed_at or exp.created_at),
            }
        ],
        "created_at": str(exp.created_at),
    }


@router.get("/registry/models/{model_id}/versions/{version}")
async def get_version(
    model_id: int,
    version: int,
    session: AsyncSession = Depends(get_db_session),
):
    # Try local DB first
    repo = ModelRepository(session)
    svc = ModelRegistryService(repo)
    v = await svc.get_version(model_id, version)
    if v is not None:
        return v

    # Fallback: treat model_id as experiment_id
    from anvil.db.repositories.experiments import ExperimentRepository

    exp_repo = ExperimentRepository(session)
    exp = await exp_repo.get(model_id)
    if exp is None:
        raise HTTPException(status_code=404, detail="Version not found")

    return {
        "version": version,
        "experiment_id": exp.id,
        "dataset_name": exp.dataset.name if exp.dataset_id else None,
        "final_loss": exp.final_loss,
        "hyperparameters": None,
        "artifact_path": f"data/models/experiment_{exp.id}.json",
        "created_at": str(exp.completed_at or exp.created_at),
    }


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
