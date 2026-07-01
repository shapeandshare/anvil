"""LoRA adapter management endpoints.

Provides routes for listing adapters, looking up individual adapters,
and triggering adapter merge operations.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from ...services.training.merge_service import AdapterMergeService
from ...storage.local import LocalFileStore
from ...workbench import AnvilWorkbench
from ..deps import get_workbench

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/models/{model_id}/adapters")
async def list_adapters(
    model_id: int,
    workbench: AnvilWorkbench = Depends(get_workbench),
) -> list[dict[str, Any]]:
    """List all LoRA adapters for a given base model.

    Parameters
    ----------
    model_id : int
        The base model's external model ID.
    workbench : AnvilWorkbench
        Request-scoped workbench with access to the adapter repository.

    Returns
    -------
    list[dict[str, Any]]
        List of adapter summaries with ``adapter_id``, ``method``,
        ``lora_rank``, ``final_loss``, ``created_at``, and
        ``merged_at``.
    """
    adapters = await workbench.lora_adapter_repo.get_by_model(model_id)
    return [
        {
            "adapter_id": a.adapter_id,
            "label": a.label,
            "method": a.method,
            "lora_rank": a.lora_rank,
            "final_loss": a.final_loss,
            "created_at": a.created_at.isoformat() if a.created_at else None,
            "merged_at": a.merged_at.isoformat() if a.merged_at else None,
        }
        for a in adapters
    ]


@router.get("/models/{model_id}/adapters/{adapter_id}")
async def get_adapter(
    model_id: int,
    adapter_id: str,
    workbench: AnvilWorkbench = Depends(get_workbench),
) -> dict[str, Any]:
    """Get details for a single LoRA adapter.

    Parameters
    ----------
    model_id : int
        The base model's external model ID.
    adapter_id : str
        Adapter identifier (e.g. ``"run_42"``).
    workbench : AnvilWorkbench
        Request-scoped workbench with access to the adapter repository.

    Returns
    -------
    dict[str, Any]
        Adapter detail including all stored fields.

    Raises
    ------
    HTTPException
        If the adapter is not found (404).
    """
    adapter = await workbench.lora_adapter_repo.get_by_adapter_id(model_id, adapter_id)
    if adapter is None:
        # Collect available IDs for the error message
        available = await workbench.lora_adapter_repo.get_by_model(model_id)
        available_ids = [a.adapter_id for a in available]
        raise HTTPException(
            status_code=404,
            detail={
                "error": f"Adapter {adapter_id!r} not found for model {model_id}",
                "available_adapters": available_ids,
            },
        )
    return {
        "id": adapter.id,
        "external_model_id": adapter.external_model_id,
        "adapter_id": adapter.adapter_id,
        "label": adapter.label,
        "method": adapter.method,
        "storage_path": adapter.storage_path,
        "lora_rank": adapter.lora_rank,
        "lora_alpha": adapter.lora_alpha,
        "lora_target_modules": adapter.lora_target_modules,
        "lora_dropout": adapter.lora_dropout,
        "lora_bias": adapter.lora_bias,
        "final_loss": adapter.final_loss,
        "final_step": adapter.final_step,
        "created_at": adapter.created_at.isoformat() if adapter.created_at else None,
        "merged_at": adapter.merged_at.isoformat() if adapter.merged_at else None,
    }


@router.post("/models/{model_id}/adapters/{adapter_id}/merge")
async def merge_adapter(
    model_id: int,
    adapter_id: str,
    workbench: AnvilWorkbench = Depends(get_workbench),
) -> dict[str, Any]:
    """Merge a LoRA adapter into its base model.

    Produces a standalone merged model artifact with no adapter
    dependency. The original adapter files are deleted and the
    adapter is marked as merged.

    Parameters
    ----------
    model_id : int
        The base model's external model ID.
    adapter_id : str
        Adapter identifier (e.g. ``"run_42"``).
    workbench : AnvilWorkbench
        Request-scoped workbench.

    Returns
    -------
    dict
        ``merged_path`` — the storage path of the merged artifact.

    Raises
    ------
    HTTPException
        If the adapter is not found (404) or merge fails (500).
    """
    store = LocalFileStore()
    merge_svc = AdapterMergeService(workbench.lora_adapter_repo, store)
    try:
        merged_path = await merge_svc.merge(model_id, adapter_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except RuntimeError as e:
        logger.exception("Adapter merge failed for %s/%s", model_id, adapter_id)
        raise HTTPException(status_code=500, detail=str(e)) from e

    return {"merged_path": merged_path}
