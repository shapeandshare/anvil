# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""API routes for external model import and registry."""

from __future__ import annotations

import asyncio
import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict

from ...db.session import AsyncSessionLocal
from ...services.catalog.catalog_entry import CatalogEntry
from ...services.catalog.catalog_kind import CatalogKind
from ...services.catalog.catalog_unavailable_error import CatalogUnavailableError
from ...services.catalog.model_ref import ModelRef
from ...services.model_import.model_asset_service import (
    DuplicateDownloadError,
    ModelAssetAlreadyAvailableError,
    ModelNotFoundError,
)
from ...workbench import AnvilWorkbench
from ..deps import get_workbench

logger = logging.getLogger(__name__)

router = APIRouter()


####################################################################
# Unified catalog listing (US1)
####################################################################


@router.get(
    "/models",
    responses={
        503: {"description": "Model catalog unavailable"},
    },
)
async def list_models(
    workbench: Annotated[AnvilWorkbench, Depends(get_workbench)],
    kind: str | None = None,
    runnable_only: bool = False,
    include_archived: bool = False,
    search: str | None = None,
) -> dict[str, object]:
    """Unified model catalog listing.

    Returns one entry per latest active version of each logical model.
    """
    try:
        return await _do_list_models(workbench, kind, runnable_only, include_archived, search)
    except CatalogUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


async def _do_list_models(
    workbench: AnvilWorkbench,
    kind: str | None,
    runnable_only: bool,
    include_archived: bool,
    search: str | None,
) -> dict[str, object]:
    """Execute unified listing query against the catalog."""
    kind_filter: CatalogKind | None = None
    if kind is not None:
        try:
            kind_filter = CatalogKind(kind)
        except ValueError:
            raise HTTPException(
                status_code=400, detail=f"Invalid kind: {kind!r}"
            ) from None

    entries = await workbench.catalog.list_entries(
        kind=kind_filter,
        runnable_only=runnable_only,
        include_archived=include_archived,
        search=search,
    )
    return {"data": [_entry_to_dict(e) for e in entries]}


@router.get(
    "/models/{name}",
    responses={
        404: {"description": "Model not found"},
        503: {"description": "Model catalog unavailable"},
    },
)
async def get_logical_model(
    name: str,
    workbench: Annotated[AnvilWorkbench, Depends(get_workbench)],
) -> dict[str, object]:
    """Return logical model details with all versions."""
    try:
        return await _do_get_logical_model(workbench, name)
    except CatalogUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


async def _do_get_logical_model(
    workbench: AnvilWorkbench, name: str
) -> dict[str, object]:
    """Execute logical model detail query."""
    entries = await workbench.catalog.list_entries(include_archived=True)
    versions = [e for e in entries if e.ref.name == name]
    if not versions:
        raise HTTPException(status_code=404, detail=f"Model not found: {name}")

    first = versions[0]
    return {
        "name": first.ref.name,
        "display_name": first.display_name,
        "kind": str(first.kind),
        "source_type": first.source_type,
        "source_identifier": first.source_identifier,
        "lifecycle_state": str(first.lifecycle_state),
        "versions": [_entry_to_dict(v) for v in sorted(
            versions, key=lambda x: x.ref.version, reverse=True
        )],
    }


@router.get(
    "/models/{name}/versions/{version}",
    responses={
        404: {"description": "Model version not found"},
        503: {"description": "Model catalog unavailable"},
    },
)
async def get_model_version(
    name: str,
    version: int,
    workbench: Annotated[AnvilWorkbench, Depends(get_workbench)],
) -> dict[str, object]:
    """Return a specific model version with config manifest."""
    try:
        return await _do_get_model_version(workbench, name, version)
    except CatalogUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


async def _do_get_model_version(
    workbench: AnvilWorkbench, name: str, version: int
) -> dict[str, object]:
    """Execute model version detail query."""
    ref = ModelRef(name=name, version=version)
    entry = await workbench.catalog.get_entry(ref)
    if entry is None:
        raise HTTPException(
            status_code=404, detail=f"Model version not found: {name} v{version}"
        )
    result = _entry_to_dict(entry)

    # Fetch config manifest if available (external models)
    if entry.kind == CatalogKind.EXTERNAL:
        try:
            config = await workbench.catalog.get_config_manifest(ref)
            result["config"] = config
        except (CatalogUnavailableError, ValueError):
            result["config"] = None
    else:
        result["config"] = None

    return result


def _entry_to_dict(entry: CatalogEntry) -> dict[str, object]:
    """Convert a ``CatalogEntry`` to a plain dict for JSON serialisation."""
    return {
        "name": entry.ref.name,
        "version": entry.ref.version,
        "kind": str(entry.kind),
        "display_name": entry.display_name,
        "source_type": entry.source_type,
        "source_identifier": entry.source_identifier,
        "revision_sha": entry.revision_sha,
        "architecture_family": entry.architecture_family,
        "tokenizer_family": entry.tokenizer_family,
        "license": entry.license,
        "parameter_count": entry.parameter_count,
        "runnable_status": str(entry.runnable_status),
        "runnable_reason": entry.runnable_reason,
        "asset_availability": str(entry.asset_availability),
        "final_loss": entry.final_loss,
        "lifecycle_state": str(entry.lifecycle_state),
        "created_at": entry.created_at.isoformat() if entry.created_at else None,
        "is_playable": entry.is_playable(),
    }


####################################################################
# Existing import routes
####################################################################


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
        Each job includes ``registry_model_name`` and
        ``registry_model_version`` when the import has completed
        registration in the MLflow Model Catalog.
    """
    jobs = await workbench.model_imports.list_jobs()
    data = [
        {
            "job_id": j.id,
            "status": j.status,
            "source_type": j.source_type,
            "source_identifier": j.source_identifier,
            "revision": j.revision,
            "started_at": j.started_at.isoformat() if j.started_at else None,
            "finished_at": j.finished_at.isoformat() if j.finished_at else None,
            "error_code": j.error_code,
            "error_message": j.error_message,
            "registry_model_name": j.registry_model_name,
            "registry_model_version": j.registry_model_version,
            "created_at": j.created_at.isoformat(),
        }
        for j in jobs
    ]
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
        "registry_model_name": job.registry_model_name,
        "registry_model_version": job.registry_model_version,
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


# ── Archive (spec 064, US4) ────────────────────────────────────────


@router.delete(
    "/models/{name}/versions/{version}",
    responses={
        404: {"description": "Model not found"},
    },
)
async def archive_model(
    name: str,
    version: int,
    workbench: Annotated[AnvilWorkbench, Depends(get_workbench)],
) -> dict[str, object]:
    """Archive a model version (tag-only, FR-008, spec 064 US4).

    Marks the catalog entry as ``ARCHIVED``, removing it from active
    listings. The entry remains queryable for lineage (``include_archived``).
    Local asset files are cleaned up from FileStore.

    Parameters
    ----------
    name : str
        Catalog model name.
    version : int
        Catalog model version.
    workbench : AnvilWorkbench
        Session-bound workbench.

    Returns
    -------
    dict
        Confirmation with ``"status": "archived"``.

    Raises
    ------
    HTTPException
        404 if the model is not found.
    """
    from ...services.catalog.model_ref import ModelRef

    ref = ModelRef(name=name, version=version)
    entry = await workbench.catalog.get_entry(ref)
    if entry is None:
        raise HTTPException(
            status_code=404,
            detail=f"Model {name} v{version} not found in catalog",
        )

    await workbench.catalog.archive(ref)

    return {
        "status": "archived",
        "model_name": name,
        "model_version": version,
    }


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
