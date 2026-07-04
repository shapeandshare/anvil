# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""API routes for external model import and registry."""

from __future__ import annotations

import asyncio
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import update

from ...db.models.evaluation_run import EvaluationRun
from ...db.session import AsyncSessionLocal
from ...services.model_import.model_asset_service import (
    DuplicateDownloadError,
    ModelAssetAlreadyAvailableError,
    ModelNotFoundError,
)
from ...workbench import AnvilWorkbench
from ..deps import get_workbench

logger = logging.getLogger(__name__)

router = APIRouter()


class ImportModelBody(BaseModel):
    """Request body for ``POST /v1/models/import``."""

    model_config = ConfigDict(extra="forbid")

    source: str
    identifier: str
    revision: str = "main"
    name: str | None = None


@router.post(
    "/models/import",
    status_code=202,
    responses={422: {"description": "Invalid source type"}},
)
async def import_model(
    body: ImportModelBody,
    workbench: Annotated[AnvilWorkbench, Depends(get_workbench)],
) -> dict[str, object]:
    """Submit an external model import job.

    Creates a ``ModelImportJob`` and fires metadata resolution as a
    background task (using its **own** session, not the request session).

    Raises
    ------
    HTTPException
        422 if the source type is invalid.
    """
    try:
        job_id = await workbench.model_imports.submit_import(
            source=body.source,
            identifier=body.identifier,
            revision=body.revision,
            name=body.name,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    _fire_background_import(job_id)

    return {"job_id": job_id, "status": "queued"}


def _fire_background_import(job_id: int) -> None:
    """Start the import worker in a background task with its own session.

    The request-scoped session from ``get_workbench`` is committed on
    return, so the worker builds a fresh session and workbench.
    """

    async def _worker() -> None:
        try:
            async with AsyncSessionLocal() as session:
                wb = AnvilWorkbench(session)
                await wb.model_imports.run_import(job_id)
                await session.commit()
        except Exception:
            logger.exception("Background import job %d failed", job_id)

    _task = asyncio.create_task(_worker())
    _task.add_done_callback(
        lambda t: logger.debug("Background import %d done: %s", job_id, t)
    )


@router.get("/models/import/jobs")
async def list_import_jobs(
    workbench: Annotated[AnvilWorkbench, Depends(get_workbench)],
) -> dict[str, object]:
    """Return all model-import jobs, newest first.

    Returns
    -------
    dict
        A JSON body with a ``"data"`` key containing a list of job dicts.
        Each job with ``external_model_id`` also includes an
        ``asset_availability`` field from the associated model.
        Jobs whose model has ``assets_pending`` also include
        ``downloaded_bytes`` and ``total_bytes`` aggregate progress.
    """
    jobs = await workbench.model_imports.list_jobs()
    data: list[dict[str, object]] = []
    for j in jobs:
        entry: dict[str, object] = {
            "job_id": j.id,
            "status": j.status,
            "source_type": j.source_type,
            "source_identifier": j.source_identifier,
            "revision": j.revision,
            "started_at": j.started_at.isoformat() if j.started_at else None,
            "finished_at": j.finished_at.isoformat() if j.finished_at else None,
            "error_code": j.error_code,
            "error_message": j.error_message,
            "external_model_id": j.external_model_id,
            "created_at": j.created_at.isoformat(),
            "asset_availability": None,
            "downloaded_bytes": 0,
            "total_bytes": 0,
        }
        if j.external_model_id is not None:
            model = await workbench.external_model_repo.get(j.external_model_id)
            if model is not None:
                entry["asset_availability"] = model.asset_availability
                if model.asset_availability == "assets_pending":
                    assets = await workbench.model_asset_repo.get_by_model(
                        j.external_model_id
                    )
                    entry["downloaded_bytes"] = sum(a.downloaded_bytes for a in assets)
                    entry["total_bytes"] = sum(a.size_bytes for a in assets)
        data.append(entry)
    return {"data": data}


@router.get(
    "/models/import/{job_id}/status",
    responses={404: {"description": "Import job not found"}},
)
async def import_job_status(
    job_id: int,
    workbench: Annotated[AnvilWorkbench, Depends(get_workbench)],
) -> dict[str, object]:
    """Poll the status of a model-import job."""
    job = await workbench.model_imports.get_job_status(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Import job not found")

    return {
        "job_id": job.id,
        "status": job.status,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "finished_at": job.finished_at.isoformat() if job.finished_at else None,
        "error_code": job.error_code,
        "error_message": job.error_message,
        "external_model_id": job.external_model_id,
    }


@router.post(
    "/models/import/{job_id}/retry",
    status_code=202,
    responses={404: {"description": "Original import job not found"}},
)
async def retry_import_job(
    job_id: int,
    workbench: Annotated[AnvilWorkbench, Depends(get_workbench)],
) -> dict[str, object]:
    """Re-submit a model-import job, creating a new job entry.

    Creates a fresh ``ModelImportJob`` with the same source/identifier/
    revision as the original and fires a background resolution task.

    Parameters
    ----------
    job_id : int
        Primary key of the job to retry.

    Returns
    -------
    dict
        A JSON body with the new ``job_id`` and ``"queued"`` status.

    Raises
    ------
    HTTPException
        404 if the original job is not found.
    """
    try:
        new_job_id = await workbench.model_imports.retry_import(job_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    _fire_background_import(new_job_id)

    return {"job_id": new_job_id, "status": "queued"}


@router.get("/models/external")
async def list_external_models(
    workbench: Annotated[AnvilWorkbench, Depends(get_workbench)],
) -> dict[str, object]:
    """Return all external model entries."""
    models = await workbench.model_imports.list_external_models()
    return {
        "data": [
            {
                "id": m.id,
                "display_name": m.display_name,
                "source_type": m.source_type,
                "source_identifier": m.source_identifier,
                "architecture_family": m.architecture_family,
                "parameter_count": m.parameter_count,
                "license": m.license,
                "tokenizer_family": m.tokenizer_family,
                "revision_sha": m.revision_sha,
                "runnable_status": m.runnable_status,
                "asset_availability": m.asset_availability,
                "created_at": m.created_at.isoformat(),
            }
            for m in models
        ]
    }


@router.get(
    "/models/external/{model_id}",
    responses={404: {"description": "External model not found"}},
)
async def get_external_model(
    model_id: int,
    workbench: Annotated[AnvilWorkbench, Depends(get_workbench)],
) -> dict[str, object]:
    """Return a single external model by ID."""
    model = await workbench.model_imports.get_external_model(model_id)
    if model is None:
        raise HTTPException(status_code=404, detail="External model not found")

    return {
        "id": model.id,
        "display_name": model.display_name,
        "source_type": model.source_type,
        "source_identifier": model.source_identifier,
        "architecture_family": model.architecture_family,
        "parameter_count": model.parameter_count,
        "license": model.license,
        "tokenizer_family": model.tokenizer_family,
        "revision_sha": model.revision_sha,
        "runnable_status": model.runnable_status,
        "runnable_reason": model.runnable_reason,
        "asset_availability": model.asset_availability,
        "config_json": model.config_json,
        "created_at": model.created_at.isoformat(),
        "updated_at": model.updated_at.isoformat(),
    }


@router.delete(
    "/models/external/{model_id}",
    responses={
        404: {"description": "External model not found"},
    },
)
async def delete_external_model(
    model_id: int,
    workbench: Annotated[AnvilWorkbench, Depends(get_workbench)],
) -> dict[str, str]:
    """Delete an external model and all associated assets.

    Cleans up downloaded asset files from the store, clears FK
    references on evaluation runs, and removes the model record
    (CASCADE handles ``model_assets``, ``asset_download_jobs``,
    ``lora_adapters``; ``SET NULL`` handles ``model_import_jobs``).

    Parameters
    ----------
    model_id : int
        ``ExternalModel`` primary key.
    workbench : AnvilWorkbench
        Session-bound workbench.

    Returns
    -------
    dict
        Confirmation message.

    Raises
    ------
    HTTPException
        404 if the model is not found.
    """
    model = await workbench.external_model_repo.get(model_id)
    if model is None:
        raise HTTPException(status_code=404, detail="External model not found")

    stmt = (
        update(EvaluationRun)
        .where(EvaluationRun.external_model_id == model_id)
        .values(external_model_id=-1)
    )
    await workbench.session.execute(stmt)
    stmt2 = (
        update(EvaluationRun)
        .where(EvaluationRun.base_external_model_id == model_id)
        .values(base_external_model_id=None)
    )
    await workbench.session.execute(stmt2)

    await workbench.model_imports.delete_external_model(
        model_id,
        model_asset_repo=workbench.model_asset_repo,
        store=workbench.model_store,
    )
    await workbench.session.commit()

    return {"message": f"External model '{model.display_name}' deleted"}


# ── Model asset download (feature 042) ──────────────────────────────


@router.post(
    "/models/{model_id}/download",
    status_code=202,
    responses={
        404: {"description": "Model not found"},
        409: {
            "description": "Assets already available, or a download is already in progress"
        },
    },
)
async def download_model_assets(
    model_id: int,
    workbench: Annotated[AnvilWorkbench, Depends(get_workbench)],
) -> dict[str, object]:
    """Trigger async download of model assets (weights, tokenizer, config).

    Returns HTTP 202 with a ``job_id`` for status polling.
    """
    try:
        job_id = await workbench.model_assets.submit_download(model_id)
    except ModelNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ModelAssetAlreadyAvailableError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except DuplicateDownloadError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    _fire_background_download(job_id)

    return {"job_id": job_id, "status": "queued"}


def _fire_background_download(job_id: int) -> None:
    """Start the asset download worker in a background task."""

    async def _worker() -> None:
        try:
            async with AsyncSessionLocal() as session:
                wb = AnvilWorkbench(session)
                await wb.model_assets.run_download(job_id)
                await session.commit()
        except Exception:
            logger.exception("Background asset download job %d failed", job_id)

    _task = asyncio.create_task(_worker())
    _task.add_done_callback(
        lambda t: logger.debug("Background asset download %d done: %s", job_id, t)
    )


@router.get(
    "/models/{model_id}/download/{job_id}/status",
    responses={
        404: {"description": "Download job not found"},
    },
)
async def asset_download_status(
    model_id: int,
    job_id: int,
    workbench: Annotated[AnvilWorkbench, Depends(get_workbench)],
) -> dict[str, object]:
    """Poll the status of an asset download job with aggregate progress."""
    status = await workbench.model_assets.get_job_status(job_id)
    if status is None:
        raise HTTPException(status_code=404, detail="Download job not found")
    return status


@router.get("/models/{model_id}/assets")
async def list_model_assets(
    model_id: int,
    workbench: Annotated[AnvilWorkbench, Depends(get_workbench)],
) -> dict[str, object]:
    """Return all assets for a model (read-only)."""
    assets = await workbench.model_assets.get_assets_for_model(model_id)
    return {
        "data": [
            {
                "id": a.id,
                "asset_type": a.asset_type,
                "filename": a.filename,
                "status": a.status,
                "size_bytes": a.size_bytes,
                "downloaded_bytes": a.downloaded_bytes,
                "sha256": a.sha256,
                "format": a.format,
                "created_at": a.created_at.isoformat(),
            }
            for a in assets
        ]
    }
