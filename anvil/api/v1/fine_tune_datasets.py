# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Fine-tune dataset and chat template API endpoints for v1.

Provides CRUD for chat templates and async job-based fine-tune dataset
preparation — submit a JSONL dataset, poll status, retrieve results.
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.models.fine_tune_dataset import FineTuneDataset
from ...db.session import AsyncSessionLocal
from ...services._shared.fine_tune_dataset_status import FineTuneDatasetStatus
from ...services.finetuning.chat_template_service import ChatTemplateService
from ...storage.local import LocalFileStore
from ...workbench import AnvilWorkbench
from ..deps import get_workbench
from .schemas_fine_tune_datasets import (
    CreateChatTemplateBody,
    CreateFineTuneDatasetBody,
    PreparationSummary,
)

router = APIRouter()

# In-memory task tracking for background preparation jobs.
_tasks: dict[int, asyncio.Task[Any]] = {}


# ── Chat Template Endpoints ──────────────────────────────────────────────


@router.post("/chat-templates", status_code=201)
async def create_chat_template(
    body: CreateChatTemplateBody,
    workbench: AnvilWorkbench = Depends(get_workbench),
) -> dict[str, object]:
    """Create a new chat template.

    Parameters
    ----------
    body : CreateChatTemplateBody
        The template to create.
    workbench : AnvilWorkbench
        Injected session-bound workbench.

    Returns
    -------
    dict
        The created template metadata.

    Raises
    ------
    HTTPException
        409 if the name already exists, 422 on validation failure.
    """
    svc = ChatTemplateService(workbench._session)
    try:
        template = await svc.create(
            name=body.name,
            template_string=body.template_string,
            tokenizer_family=body.tokenizer_family,
            description=body.description,
            base_model_ref=body.base_model_ref,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {
        "id": template.id,
        "name": template.name,
        "tokenizer_family": template.tokenizer_family,
        "status": template.status,
        "created_at": template.created_at.isoformat(),
    }


@router.get("/chat-templates")
async def list_chat_templates(
    tokenizer_family: str | None = None,
    status: str | None = None,
    workbench: AnvilWorkbench = Depends(get_workbench),
) -> dict[str, object]:
    """List chat templates with optional filters.

    Parameters
    ----------
    tokenizer_family : str, optional
        Filter by tokenizer family.
    status : str, optional
        Filter by template status.
    workbench : AnvilWorkbench
        Injected session-bound workbench.

    Returns
    -------
    dict
        ``{"items": [...], "total": N}``
    """
    svc = ChatTemplateService(workbench._session)
    templates = await svc.list_(
        tokenizer_family=tokenizer_family,
        status=status,
    )
    items = [
        {
            "id": t.id,
            "name": t.name,
            "tokenizer_family": t.tokenizer_family,
            "status": t.status,
            "created_at": t.created_at.isoformat(),
        }
        for t in templates
    ]
    return {"items": items, "total": len(items)}


# ── Fine-Tune Dataset Endpoints ──────────────────────────────────────────


@router.post("/fine-tune-datasets", status_code=202)
async def create_fine_tune_dataset(
    body: CreateFineTuneDatasetBody,
    workbench: AnvilWorkbench = Depends(get_workbench),
) -> dict[str, object]:
    """Submit a new fine-tune dataset preparation job.

    Enforces one active preparation per source dataset (returns 409
    on concurrent request). Launches a background ``asyncio.create_task``
    worker with an isolated session.

    Parameters
    ----------
    body : CreateFineTuneDatasetBody
        The preparation job parameters.
    workbench : AnvilWorkbench
        Injected session-bound workbench.

    Returns
    -------
    dict
        ``{"job_id": ..., "fine_tune_dataset_id": ..., "status": "preparing"}``

    Raises
    ------
    HTTPException
        404 if the source dataset is not found, 409 on concurrent preparation.
    """
    # Validate source dataset exists
    dataset = await workbench.dataset_repo.get(body.dataset_id)
    if dataset is None:
        raise HTTPException(status_code=404, detail="Dataset not found")

    # Enforce one active preparation per source dataset
    ftd_repo = workbench.ftd_repo
    active = await ftd_repo.get_active_for_dataset(body.dataset_id)
    if active is not None:
        raise HTTPException(
            status_code=409,
            detail=f"Dataset {body.dataset_id} already has an active preparation job ({active.id})",
        )

    # Create the FineTuneDataset entry
    ftd = FineTuneDataset(
        dataset_id=body.dataset_id,
        chat_template_id=body.chat_template_id,
        base_model_ref=body.base_model_ref,
        status=FineTuneDatasetStatus.PREPARING,
        record_type=body.record_type,
        started_at=datetime.now(UTC),
    )
    saved = await ftd_repo.add(ftd)

    # Fire background worker
    job_id = saved.id
    _tasks[job_id] = asyncio.create_task(
        _run_preparation_worker(job_id, body.batch_size)
    )

    return {
        "job_id": job_id,
        "fine_tune_dataset_id": job_id,
        "status": FineTuneDatasetStatus.PREPARING,
    }


async def _run_preparation_worker(job_id: int, batch_size: int) -> None:
    """Background worker for fine-tune dataset preparation.

    Runs in an isolated session and asyncio task. Reads the
    ``FineTuneDataset`` entry and existing dataset samples, renders
    them with the chat template, and writes the prepared output.

    Parameters
    ----------
    job_id : int
        The ``FineTuneDataset`` primary key.
    batch_size : int
        Records per batch.
    """
    from ...db.repositories.curation import SampleRepository
    from ...db.repositories.fine_tune_datasets import FineTuneDatasetRepository
    from ...services.finetuning.preparation_job import run_preparation

    try:
        async with AsyncSessionLocal() as session:
            workbench = AnvilWorkbench(session)
            repo = FineTuneDatasetRepository(session)
            ftd = await repo.get(job_id)
            if ftd is None:
                return

            template_string = await _resolve_template_string(session, ftd)
            sample_repo = SampleRepository(session)
            samples = await sample_repo.get_active_texts(ftd.dataset_id)
            records = await _samples_to_records(workbench.store, samples)
            output_path = f"{ftd.dataset_id}/prepared/{job_id}.jsonl"

            await run_preparation(
                session=session,
                fine_tune_dataset_id=job_id,
                records=records,
                template_string=template_string,
                bos_token="",
                record_type=ftd.record_type,
                batch_size=batch_size,
                store=workbench.store,
                output_path=output_path,
            )
    except Exception as exc:
        await _mark_failed(job_id, str(exc))
    finally:
        _tasks.pop(job_id, None)


async def _resolve_template_string(session: AsyncSession, ftd: FineTuneDataset) -> str:
    """Resolve the chat template string for a job (FR-005 a -> b -> c)."""
    svc = ChatTemplateService(session)
    if ftd.chat_template_id is not None:
        explicit = await svc.get(ftd.chat_template_id)
        if explicit is not None:
            return explicit.template_string
    template, _warning = await svc.get_default_template_for_model(
        base_model_ref=ftd.base_model_ref,
        tokenizer_family="char",
    )
    return template.template_string


async def _samples_to_records(
    store: LocalFileStore,
    samples: object,
) -> list[dict[str, Any]]:
    """Read each active sample's JSONL text from *store* and parse it.

    Each curated sample's stored text is expected to be a JSON object
    (one JSONL record). Non-JSON samples are emitted as an unparseable
    marker so they are counted as failed records (skip-and-continue).
    """
    from ...db.models.sample import Sample

    iterable = list(samples) if isinstance(samples, (list, tuple)) else []
    records: list[dict[str, Any]] = []
    for sample in iterable:
        if not isinstance(sample, Sample):
            continue
        text = await _read_text(store, sample.file_path)
        try:
            parsed = json.loads(text)
        except (json.JSONDecodeError, ValueError):
            records.append({"__unparseable__": text[:200]})
            continue
        records.append(
            parsed if isinstance(parsed, dict) else {"__unparseable__": text[:200]}
        )
    return records


async def _read_text(store: LocalFileStore, path: str) -> str:
    """Read a stored file fully and decode it as UTF-8 text."""
    chunks: list[bytes] = []
    async for chunk in store.get(path):
        chunks.append(chunk)
    return b"".join(chunks).decode("utf-8")


async def _mark_failed(job_id: int, error: str) -> None:
    """Transition a job to ``failed`` with an error summary."""
    from ...db.repositories.fine_tune_datasets import FineTuneDatasetRepository

    async with AsyncSessionLocal() as session:
        repo = FineTuneDatasetRepository(session)
        summary = json.dumps(
            {
                "total": 0,
                "succeeded": 0,
                "failed": 0,
                "errors": [{"row": -1, "error": error}],
            }
        )
        await repo.update_status(
            id=job_id,
            status=FineTuneDatasetStatus.FAILED,
            summary_json=summary,
            finished_at=datetime.now(UTC),
        )
        await session.commit()


@router.get("/fine-tune-datasets/jobs/{job_id}/status")
async def get_job_status(
    job_id: int,
    workbench: AnvilWorkbench = Depends(get_workbench),
) -> dict[str, object]:
    """Poll preparation job status.

    Parameters
    ----------
    job_id : int
        The preparation job identifier.
    workbench : AnvilWorkbench
        Injected session-bound workbench.

    Returns
    -------
    dict
        Job status with timestamps and optional summary.

    Raises
    ------
    HTTPException
        404 if the job is not found.
    """
    ftd = await workbench.ftd_repo.get(job_id)
    if ftd is None:
        raise HTTPException(status_code=404, detail="Job not found")
    summary = None
    if ftd.summary_json:
        try:
            data = json.loads(ftd.summary_json)
            summary = PreparationSummary(
                total=data.get("total", 0),
                succeeded=data.get("succeeded", 0),
                failed=data.get("failed", 0),
                errors=data.get("errors", []),
            )
        except (json.JSONDecodeError, TypeError):
            pass
    return {
        "job_id": job_id,
        "fine_tune_dataset_id": ftd.id,
        "status": ftd.status,
        "started_at": ftd.started_at.isoformat() if ftd.started_at else None,
        "finished_at": ftd.finished_at.isoformat() if ftd.finished_at else None,
        "summary": summary.model_dump() if summary else None,
    }


@router.get("/fine-tune-datasets/{ftd_id}")
async def get_fine_tune_dataset(
    ftd_id: int,
    workbench: AnvilWorkbench = Depends(get_workbench),
) -> dict[str, object]:
    """Get a prepared fine-tune dataset by ID.

    Parameters
    ----------
    ftd_id : int
        The fine-tune dataset primary key.
    workbench : AnvilWorkbench
        Injected session-bound workbench.

    Returns
    -------
    dict
        Full fine-tune dataset metadata.

    Raises
    ------
    HTTPException
        404 if not found.
    """
    ftd = await workbench.ftd_repo.get(ftd_id)
    if ftd is None:
        raise HTTPException(status_code=404, detail="Fine-tune dataset not found")
    return _serialize_ftd(ftd)


@router.get("/fine-tune-datasets")
async def list_fine_tune_datasets(
    dataset_id: int | None = None,
    status: str | None = None,
    base_model_ref: int | None = None,
    workbench: AnvilWorkbench = Depends(get_workbench),
) -> dict[str, object]:
    """List fine-tune datasets with optional filters.

    Parameters
    ----------
    dataset_id : int, optional
        Filter by source dataset.
    status : str, optional
        Filter by job status.
    base_model_ref : int, optional
        Filter by base model.
    workbench : AnvilWorkbench
        Injected session-bound workbench.

    Returns
    -------
    dict
        ``{"items": [...], "total": N}``
    """
    items = await workbench.ftd_repo.get_all(
        dataset_id=dataset_id,
        status=status,
        base_model_ref=base_model_ref,
    )
    return {
        "items": [_serialize_ftd(f) for f in items],
        "total": len(items),
    }


@router.post("/fine-tune-datasets/{ftd_id}/retry", status_code=202)
async def retry_fine_tune_dataset(
    ftd_id: int,
    body: dict[str, Any] | None = None,
    workbench: AnvilWorkbench = Depends(get_workbench),
) -> dict[str, Any]:
    """Retry a failed fine-tune dataset preparation.

    Creates a new preparation job for a ``FineTuneDataset`` entry
    that is in ``failed`` status.

    Parameters
    ----------
    ftd_id : int
        The failed fine-tune dataset ID.
    body : dict, optional
        Not used; kept for API consistency.
    workbench : AnvilWorkbench
        Injected session-bound workbench.

    Returns
    -------
    dict
        ``{"job_id": ..., "fine_tune_dataset_id": ..., "status": "preparing"}``

    Raises
    ------
    HTTPException
        404 if not found, 409 if status is not ``failed``.
    """
    ftd = await workbench.ftd_repo.get(ftd_id)
    if ftd is None:
        raise HTTPException(status_code=404, detail="Fine-tune dataset not found")
    if ftd.status != FineTuneDatasetStatus.FAILED:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot retry: status is '{ftd.status}', expected 'failed'",
        )

    from ...db.models.fine_tune_dataset import FineTuneDataset as FTDM

    new_entry = FTDM(
        dataset_id=ftd.dataset_id,
        chat_template_id=ftd.chat_template_id,
        base_model_ref=ftd.base_model_ref,
        status=FineTuneDatasetStatus.PREPARING,
        record_type=ftd.record_type,
        started_at=datetime.now(UTC),
    )
    saved = await workbench.ftd_repo.add(new_entry)
    job_id = saved.id
    _tasks[job_id] = asyncio.create_task(_run_preparation_worker(job_id, 1000))
    return {
        "job_id": job_id,
        "fine_tune_dataset_id": job_id,
        "status": FineTuneDatasetStatus.PREPARING,
    }


def _serialize_ftd(ftd: FineTuneDataset) -> dict[str, Any]:
    summary = None
    if ftd.summary_json:
        try:
            data = json.loads(ftd.summary_json)
            summary = {
                "total": data.get("total", 0),
                "succeeded": data.get("succeeded", 0),
                "failed": data.get("failed", 0),
                "errors": data.get("errors", []),
            }
        except (json.JSONDecodeError, TypeError):
            pass
    return {
        "id": ftd.id,
        "dataset_id": ftd.dataset_id,
        "chat_template_id": ftd.chat_template_id,
        "base_model_ref": ftd.base_model_ref,
        "status": ftd.status,
        "record_type": ftd.record_type,
        "record_count": ftd.record_count,
        "summary": summary,
        "created_at": ftd.created_at.isoformat() if ftd.created_at else None,
        "updated_at": ftd.updated_at.isoformat() if ftd.updated_at else None,
    }
