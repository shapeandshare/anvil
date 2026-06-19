import asyncio

from fastapi import APIRouter, HTTPException, Query

from anvil.config import get_mlflow_uri
from mlflow.tracking import MlflowClient

router = APIRouter()


@router.post("/registry/models", status_code=201)
async def register_model(
    body: dict,
):
    experiment_id = body.get("experiment_id")
    if not experiment_id:
        raise HTTPException(status_code=400, detail="experiment_id required")

    from anvil.services.tracking import TrackingService

    tracking_svc = TrackingService()
    exp = await tracking_svc.get_experiment(experiment_id)
    if exp is None:
        raise HTTPException(status_code=400, detail="Experiment not found")

    status = exp.get("status") or ""
    if status != "FINISHED":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot register model from experiment with status '{exp.get('status')}' (must be FINISHED)",
        )

    mlflow_run_id = exp.get("mlflow_run_id")
    if not mlflow_run_id:
        raise HTTPException(status_code=400, detail="Experiment has no MLflow run ID")

    # Resolve registry name from the datasource's actual name
    registry_name = None
    params = exp.get("params", {})
    dataset_id = params.get("dataset_id")
    corpus_id = params.get("corpus_id")

    if dataset_id is not None:
        from anvil.db.repositories.datasets import DatasetRepository
        from anvil.db.session import AsyncSessionLocal

        async with AsyncSessionLocal() as sess:
            ds_repo = DatasetRepository(sess)
            ds = await ds_repo.get(int(dataset_id))
            if ds:
                registry_name = ds.name
    elif corpus_id is not None:
        from anvil.db.repositories.corpora import CorpusRepository
        from anvil.db.session import AsyncSessionLocal

        async with AsyncSessionLocal() as sess:
            corp_repo = CorpusRepository(sess)
            corpus = await corp_repo.get(int(corpus_id))
            if corpus:
                registry_name = corpus.name

    result = await tracking_svc.register_source_model(
        run_id=mlflow_run_id,
        name=registry_name,
        dataset_id=int(dataset_id) if dataset_id else None,
        corpus_id=int(corpus_id) if corpus_id else None,
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
async def get_model(model_id: str):
    from anvil.services.tracking import TrackingService

    tracking_svc = TrackingService()
    loop = asyncio.get_event_loop()

    # Resolve model_id to MLflow registered model name
    model_name = None
    try:
        id_as_int = int(model_id)
        # Integer: find by convention dataset-{id} or corpus-{id}
        models = await tracking_svc.list_registered_models()
        candidates = {f"dataset-{id_as_int}", f"corpus-{id_as_int}"}
        for m in models:
            if m.get("name") in candidates:
                model_name = m["name"]
                break
    except ValueError:
        # String: use as MLflow model name directly
        model_name = model_id

    if not model_name:
        raise HTTPException(status_code=404, detail="Model not found")

    # Query MLflow Model Registry for full model details
    client = MlflowClient(get_mlflow_uri())
    try:
        rm = await loop.run_in_executor(
            None, lambda: client.get_registered_model(model_name)
        )
    except Exception:
        raise HTTPException(status_code=404, detail="Model not found") from None

    # Get all versions with run metadata
    try:
        all_versions = await loop.run_in_executor(
            None,
            lambda: client.search_model_versions(f"name='{model_name}'"),
        )
    except Exception:
        all_versions = []

    versions_list = []
    for v in all_versions or []:
        run_data = {"params": {}, "metrics": {}}
        try:
            run = await loop.run_in_executor(
                None, lambda rid=v.run_id: client.get_run(rid)
            )
            if run and run.data:
                run_data["params"] = dict(run.data.params)
                run_data["metrics"] = dict(run.data.metrics)
        except Exception:
            pass

        versions_list.append({
            "version": int(v.version),
            "experiment_id": None,
            "dataset_name": run_data["params"].get("dataset_id"),
            "final_loss": run_data["metrics"].get("final_loss"),
            "hyperparameters": (
                dict(run_data["params"]) if run_data["params"] else None
            ),
            "created_at": (
                str(v.creation_timestamp)
                if v.creation_timestamp
                else None
            ),
        })

    return {
        "id": model_name,
        "name": rm.name,
        "description": rm.description if hasattr(rm, "description") else None,
        "versions": versions_list,
        "created_at": (
            str(rm.creation_timestamp)
            if hasattr(rm, "creation_timestamp") and rm.creation_timestamp
            else None
        ),
    }


@router.get("/registry/models/{model_id}/versions/{version}")
async def get_version(model_id: str, version: int):
    from anvil.services.tracking import TrackingService

    tracking_svc = TrackingService()
    loop = asyncio.get_event_loop()

    # Resolve model_id to MLflow registered model name
    model_name = None
    try:
        id_as_int = int(model_id)
        models = await tracking_svc.list_registered_models()
        candidates = {f"dataset-{id_as_int}", f"corpus-{id_as_int}"}
        for m in models:
            if m.get("name") in candidates:
                model_name = m["name"]
                break
    except ValueError:
        model_name = model_id

    if not model_name:
        raise HTTPException(status_code=404, detail="Model not found")

    # Query MLflow for the specific version
    client = MlflowClient(get_mlflow_uri())
    try:
        all_versions = await loop.run_in_executor(
            None,
            lambda: client.search_model_versions(f"name='{model_name}'"),
        )
    except Exception:
        raise HTTPException(status_code=404, detail="Model not found") from None

    target_version = None
    for v in all_versions or []:
        if int(v.version) == version:
            target_version = v
            break

    if target_version is None:
        raise HTTPException(status_code=404, detail="Version not found")

    # Get run data for this version
    run_data = {"params": {}, "metrics": {}}
    try:
        run = await loop.run_in_executor(
            None,
            lambda rid=target_version.run_id: client.get_run(rid),
        )
        if run and run.data:
            run_data["params"] = dict(run.data.params)
            run_data["metrics"] = dict(run.data.metrics)
    except Exception:
        pass

    return {
        "version": int(target_version.version),
        "experiment_id": None,
        "dataset_name": run_data["params"].get("dataset_id"),
        "final_loss": run_data["metrics"].get("final_loss"),
        "hyperparameters": (
            dict(run_data["params"]) if run_data["params"] else None
        ),
        "artifact_path": (
            target_version.source if hasattr(target_version, "source") else None
        ),
        "created_at": (
            str(target_version.creation_timestamp)
            if target_version.creation_timestamp
            else None
        ),
    }


@router.delete("/registry/models/{model_id}/versions/{version}")
async def delete_version(model_id: str, version: int):
    from anvil.services.tracking import TrackingService

    tracking_svc = TrackingService()
    loop = asyncio.get_event_loop()

    # Resolve model_id to MLflow registered model name
    model_name = None
    try:
        id_as_int = int(model_id)
        models = await tracking_svc.list_registered_models()
        candidates = {f"dataset-{id_as_int}", f"corpus-{id_as_int}"}
        for m in models:
            if m.get("name") in candidates:
                model_name = m["name"]
                break
    except ValueError:
        model_name = model_id

    if not model_name:
        raise HTTPException(status_code=404, detail="Model not found")

    client = MlflowClient(get_mlflow_uri())
    try:
        await loop.run_in_executor(
            None,
            lambda: client.delete_model_version(
                name=model_name,
                version=str(version),
            ),
        )
    except Exception as e:
        raise HTTPException(
            status_code=404,
            detail=f"Version not found or could not be deleted: {e}",
        ) from e

    return {"message": f"Version {version} of '{model_name}' deleted"}


@router.delete("/registry/models/{model_id}")
async def delete_model(model_id: str):
    from anvil.services.tracking import TrackingService

    tracking_svc = TrackingService()
    loop = asyncio.get_event_loop()

    # Resolve model_id to MLflow registered model name
    model_name = None
    try:
        id_as_int = int(model_id)
        models = await tracking_svc.list_registered_models()
        candidates = {f"dataset-{id_as_int}", f"corpus-{id_as_int}"}
        for m in models:
            if m.get("name") in candidates:
                model_name = m["name"]
                break
    except ValueError:
        model_name = model_id

    if not model_name:
        raise HTTPException(status_code=404, detail="Model not found")

    client = MlflowClient(get_mlflow_uri())
    try:
        await loop.run_in_executor(
            None,
            lambda: client.delete_registered_model(name=model_name),
        )
    except Exception as e:
        raise HTTPException(
            status_code=404,
            detail=f"Model not found or could not be deleted: {e}",
        ) from e

    return {"message": f"Model '{model_name}' and all versions deleted"}