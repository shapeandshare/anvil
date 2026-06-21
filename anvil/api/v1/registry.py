"""Model registry API for registering, listing, and managing trained models.

Provides FastAPI routes for interacting with the MLflow Model Registry:
registering models from completed experiments, listing registered models,
retrieving model and version details, and deleting models/versions.
Model IDs are resolved via convention-based naming (``dataset-<id>`` or
``corpus-<id>``) or used directly as MLflow model names.
"""

import asyncio
from datetime import datetime, UTC

from fastapi import APIRouter, HTTPException, Query
from mlflow.tracking import MlflowClient

from ...config import get_mlflow_uri

router = APIRouter()


@router.post("/registry/models", status_code=201)
async def register_model(
    body: dict,
):
    """Register a trained model from a completed MLflow experiment.

    Extracts the experiment run information and registers the model artifact
    in the MLflow Model Registry under a convention-based name derived from
    the associated dataset or corpus.

    Parameters
    ----------
    body : dict
        Request body containing ``experiment_id`` (required) identifying the
        completed experiment. Optional ``dataset_id`` or ``corpus_id`` in the
        experiment params are used to derive the registry name.

    Returns
    -------
    dict
        Result of the model registration, including registered model name and
        version information.

    Raises
    ------
    HTTPException
        If ``experiment_id`` is missing (400), the experiment does not exist
        (400), the experiment status is not ``FINISHED`` (400), or the
        experiment has no MLflow run ID (400).
    """
    experiment_id = body.get("experiment_id")
    if not experiment_id:
        raise HTTPException(status_code=400, detail="experiment_id required")

    from ...services.tracking.tracking import TrackingService

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
        from ...db.repositories.datasets import DatasetRepository
        from ...db.session import AsyncSessionLocal

        async with AsyncSessionLocal() as sess:
            ds_repo = DatasetRepository(sess)
            ds = await ds_repo.get(int(dataset_id))
            if ds:
                registry_name = ds.name
    elif corpus_id is not None:
        from ...db.repositories.corpora import CorpusRepository
        from ...db.session import AsyncSessionLocal

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
    """List all registered models in the MLflow Model Registry.

    Parameters
    ----------
    search : str | None, optional
        Optional search query to filter registered models by name. If
        ``None``, all registered models are returned.

    Returns
    -------
    dict
        Dictionary with a ``models`` key containing a list of registered
        model summaries.
    """
    from ...services.tracking.tracking import TrackingService

    tracking_svc = TrackingService()
    models = await tracking_svc.list_registered_models(search=search)
    return {"models": models}


def _fmt_ts(ts: int | None) -> str | None:
    """Convert epoch-millis timestamp to ``YYYY-MM-DD HH:MM UTC`` string.

    Parameters
    ----------
    ts : int | None
        Epoch milliseconds timestamp, or ``None``.

    Returns
    -------
    str | None
        Formatted date string or ``None``.
    """
    if ts is None:
        return None
    try:
        return datetime.fromtimestamp(ts / 1000, tz=UTC).strftime("%Y-%m-%d %H:%M UTC")
    except (OSError, OverflowError, ValueError):
        return str(ts)


@router.get("/registry/models/{model_id}")
async def get_model(model_id: str):
    """Retrieve details for a specific registered model and all its versions.

    Resolves ``model_id`` to an MLflow registered model name using
    convention-based lookup (``dataset-<id>`` or ``corpus-<id>``) for integer
    IDs, or uses the value directly for string IDs. Fetches full model details
    including all versions with associated run metadata.

    Parameters
    ----------
    model_id : str
        The model identifier. Can be an integer (resolved to
        ``dataset-<id>`` or ``corpus-<id>``) or a string used directly
        as the MLflow registered model name.

    Returns
    -------
    dict
        Model details including ``id``, ``name``, ``description``,
        ``versions`` (list of version objects), and ``created_at``.

    Raises
    ------
    HTTPException
        If the model cannot be found (404).
    """
    from ...services.tracking.tracking import TrackingService

    tracking_svc = TrackingService()
    loop = asyncio.get_event_loop()

    # Resolve model_id to MLflow registered model name
    model_name = None
    models: list[dict] = []
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
        # Fallback: try matching by experiment_id (e.g. demo models
        # registered under a dataset/corpus name, not dataset-X).
        try:
            id_as_int = int(model_id)
            for m in models:
                if m.get("id") == id_as_int:
                    model_name = m["name"]
                    break
        except (ValueError, TypeError):
            pass

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
        run_data = {"params": {}, "metrics": {}, "tags": {}}
        try:
            run = await loop.run_in_executor(
                None, lambda rid=v.run_id: client.get_run(rid)
            )
            if run and run.data:
                run_data["params"] = dict(run.data.params)
                run_data["metrics"] = dict(run.data.metrics)
                run_data["tags"] = dict(run.data.tags)
        except Exception:
            pass

        # Resolve experiment_id from MLflow run tag (same pattern as
        # TrackingService.list_registered_models).
        experiment_id: int | None = None
        raw_exp = run_data["tags"].get("anvil.experiment_id")
        if raw_exp is not None:
            try:
                experiment_id = int(raw_exp)
            except (ValueError, TypeError):
                pass

        # Resolve dataset/corpus name from DB if the run has a source ID.
        dataset_name: str | None = None
        ds_id_raw = run_data["params"].get("dataset_id")
        corp_id_raw = run_data["params"].get("corpus_id")
        if ds_id_raw is not None:
            try:
                from ...db.repositories.datasets import DatasetRepository
                from ...db.session import AsyncSessionLocal

                async with AsyncSessionLocal() as sess:
                    ds_repo = DatasetRepository(sess)
                    ds = await ds_repo.get(int(ds_id_raw))
                    if ds:
                        dataset_name = ds.name
            except Exception:
                dataset_name = f"Dataset #{ds_id_raw}"
        elif corp_id_raw is not None:
            try:
                from ...db.repositories.corpora import CorpusRepository
                from ...db.session import AsyncSessionLocal

                async with AsyncSessionLocal() as sess:
                    corp_repo = CorpusRepository(sess)
                    corp = await corp_repo.get(int(corp_id_raw))
                    if corp:
                        dataset_name = corp.name
            except Exception:
                dataset_name = f"Corpus #{corp_id_raw}"

        versions_list.append(
            {
                "version": int(v.version),
                "experiment_id": experiment_id,
                "dataset_name": dataset_name,
                "final_loss": run_data["metrics"].get("final_loss"),
                "hyperparameters": (
                    dict(run_data["params"]) if run_data["params"] else None
                ),
                "created_at": _fmt_ts(v.creation_timestamp),
            }
        )

    return {
        "id": model_name,
        "name": rm.name,
        "description": rm.description if hasattr(rm, "description") else None,
        "versions": versions_list,
        "created_at": _fmt_ts(
            rm.creation_timestamp if hasattr(rm, "creation_timestamp") else None
        ),
    }


@router.get("/registry/models/{model_id}/versions/{version}")
async def get_version(model_id: str, version: int):
    """Retrieve details for a specific version of a registered model.

    Resolves ``model_id`` using convention-based lookup and fetches the
    specific version's details including run metadata.

    Parameters
    ----------
    model_id : str
        The model identifier.
    version : int
        The version number to retrieve.

    Returns
    -------
    dict
        Version details including ``version``, ``dataset_name``,
        ``final_loss``, ``hyperparameters``, ``artifact_path``, and
        ``created_at``.

    Raises
    ------
    HTTPException
        If the model or version is not found (404).
    """
    from ...services.tracking.tracking import TrackingService

    tracking_svc = TrackingService()
    loop = asyncio.get_event_loop()

    # Resolve model_id to MLflow registered model name
    model_name = None
    models: list[dict] = []
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
        try:
            id_as_int = int(model_id)
            for m in models:
                if m.get("id") == id_as_int:
                    model_name = m["name"]
                    break
        except (ValueError, TypeError):
            pass

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
    run_data = {"params": {}, "metrics": {}, "tags": {}}
    try:
        run = await loop.run_in_executor(
            None,
            lambda rid=target_version.run_id: client.get_run(rid),
        )
        if run and run.data:
            run_data["params"] = dict(run.data.params)
            run_data["metrics"] = dict(run.data.metrics)
            run_data["tags"] = dict(run.data.tags)
    except Exception:
        pass

    # Resolve experiment_id from MLflow run tag.
    experiment_id: int | None = None
    raw_exp = run_data["tags"].get("anvil.experiment_id")
    if raw_exp is not None:
        try:
            experiment_id = int(raw_exp)
        except (ValueError, TypeError):
            pass

    # Resolve dataset/corpus name from DB if the run has a source ID.
    dataset_name: str | None = None
    ds_id_raw = run_data["params"].get("dataset_id")
    corp_id_raw = run_data["params"].get("corpus_id")
    if ds_id_raw is not None:
        try:
            from ...db.repositories.datasets import DatasetRepository
            from ...db.session import AsyncSessionLocal

            async with AsyncSessionLocal() as sess:
                ds_repo = DatasetRepository(sess)
                ds = await ds_repo.get(int(ds_id_raw))
                if ds:
                    dataset_name = ds.name
        except Exception:
            dataset_name = f"Dataset #{ds_id_raw}"
    elif corp_id_raw is not None:
        try:
            from ...db.repositories.corpora import CorpusRepository
            from ...db.session import AsyncSessionLocal

            async with AsyncSessionLocal() as sess:
                corp_repo = CorpusRepository(sess)
                corp = await corp_repo.get(int(corp_id_raw))
                if corp:
                    dataset_name = corp.name
        except Exception:
            dataset_name = f"Corpus #{corp_id_raw}"

    return {
        "version": int(target_version.version),
        "experiment_id": experiment_id,
        "dataset_name": dataset_name,
        "final_loss": run_data["metrics"].get("final_loss"),
        "hyperparameters": (dict(run_data["params"]) if run_data["params"] else None),
        "artifact_path": (
            target_version.source if hasattr(target_version, "source") else None
        ),
        "created_at": _fmt_ts(target_version.creation_timestamp),
    }


@router.delete("/registry/models/{model_id}/versions/{version}")
async def delete_version(model_id: str, version: int):
    """Delete a specific version of a registered model.

    Parameters
    ----------
    model_id : str
        The model identifier.
    version : int
        The version number to delete.

    Returns
    -------
    dict
        Confirmation message.

    Raises
    ------
    HTTPException
        If the model or version is not found, or deletion fails (404).
    """
    from ...services.tracking.tracking import TrackingService

    tracking_svc = TrackingService()
    loop = asyncio.get_event_loop()

    # Resolve model_id to MLflow registered model name
    model_name = None
    models: list[dict] = []
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
        try:
            id_as_int = int(model_id)
            for m in models:
                if m.get("id") == id_as_int:
                    model_name = m["name"]
                    break
        except (ValueError, TypeError):
            pass

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
    """Delete a registered model and all its versions.

    Parameters
    ----------
    model_id : str
        The model identifier.

    Returns
    -------
    dict
        Confirmation message.

    Raises
    ------
    HTTPException
        If the model cannot be found or deletion fails (404).
    """
    from ...services.tracking.tracking import TrackingService

    tracking_svc = TrackingService()
    loop = asyncio.get_event_loop()

    # Resolve model_id to MLflow registered model name
    model_name = None
    models: list[dict] = []
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
        try:
            id_as_int = int(model_id)
            for m in models:
                if m.get("id") == id_as_int:
                    model_name = m["name"]
                    break
        except (ValueError, TypeError):
            pass

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
