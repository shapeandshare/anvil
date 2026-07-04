"""LoRA adapter management endpoints.

Provides routes for listing adapters, looking up individual adapters,
and triggering adapter merge operations — all keyed by ModelRef.
"""

from __future__ import annotations

import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException

from ...services.catalog.model_ref import ModelRef
from ...workbench import AnvilWorkbench
from ..deps import get_workbench

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/models/{name}/versions/{version}/adapters")
async def list_adapters(
    name: str,
    version: int,
    workbench: Annotated[AnvilWorkbench, Depends(get_workbench)],
) -> list[dict[str, Any]]:
    """List all LoRA adapters for a given base model (ModelRef path).

    Parameters
    ----------
    name : str
        Catalog model name.
    version : int
        Catalog model version.
    workbench : AnvilWorkbench
        Request-scoped workbench with access to the adapter repository.

    Returns
    -------
    list[dict[str, Any]]
        List of adapter summaries with ``adapter_id``, ``method``,
        ``lora_rank``, ``final_loss``, ``created_at``, and
        ``merged_at``.
    """
    ref = ModelRef(name=name, version=version)
    adapters = await workbench.lora_adapter_repo.get_by_model_ref(ref)
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


@router.get(
    "/models/{name}/versions/{version}/adapters/{adapter_id}",
    responses={404: {"description": "Adapter not found"}},
)
async def get_adapter(
    name: str,
    version: int,
    adapter_id: str,
    workbench: Annotated[AnvilWorkbench, Depends(get_workbench)],
) -> dict[str, Any]:
    """Get details for a single LoRA adapter.

    Parameters
    ----------
    name : str
        Catalog model name.
    version : int
        Catalog model version.
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
    ref = ModelRef(name=name, version=version)
    adapter = await workbench.lora_adapter_repo.get_by_adapter_id_modelref(
        ref, adapter_id
    )
    if adapter is None:
        available = await workbench.lora_adapter_repo.get_by_model_ref(ref)
        available_ids = [a.adapter_id for a in available]
        raise HTTPException(
            status_code=404,
            detail={
                "error": f"Adapter {adapter_id!r} not found for model {name} v{version}",
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


@router.post(
    "/models/{name}/versions/{version}/adapters/{adapter_id}/merge",
    responses={
        404: {"description": "Adapter not found"},
        500: {"description": "Merge operation failed"},
    },
)
async def merge_adapter(
    name: str,
    version: int,
    adapter_id: str,
    workbench: Annotated[AnvilWorkbench, Depends(get_workbench)],
) -> dict[str, Any]:
    """Merge a LoRA adapter into its base model.

    Produces a standalone merged model artifact with no adapter
    dependency. The original adapter files are preserved (non-
    destructive). Call ``.../merge-and-export`` for the full
    pipeline including safetensors conversion and MLflow lineage.

    Parameters
    ----------
    name : str
        Catalog model name.
    version : int
        Catalog model version.
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
    ref = ModelRef(name=name, version=version)
    try:
        merged_path = await workbench.merge_service.merge_by_ref(ref, adapter_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except RuntimeError as e:
        logger.exception("Adapter merge failed")
        raise HTTPException(status_code=500, detail=str(e)) from e

    return {"merged_path": merged_path}


@router.post(
    "/models/{name}/versions/{version}/adapters/{adapter_id}/merge-and-export",
    responses={
        404: {"description": "Adapter not found or license check failed"},
        500: {"description": "Merge or export operation failed"},
    },
)
async def merge_and_export_adapter(
    name: str,
    version: int,
    adapter_id: str,
    workbench: Annotated[AnvilWorkbench, Depends(get_workbench)],
) -> dict[str, Any]:
    """Full merge+export pipeline with safetensors and MLflow lineage.

    Merges the LoRA adapter into the base model, exports directly to
    HuggingFace format (safetensors + config + tokenizer), publishes
    atomically, and registers MLflow lineage.

    Parameters
    ----------
    name : str
        Catalog model name.
    version : int
        Catalog model version.
    adapter_id : str
        Adapter identifier (e.g. ``"run_42"``).
    workbench : AnvilWorkbench
        Request-scoped workbench.

    Returns
    -------
    dict
        ``path`` — the storage path of the merged artifact, and
        ``lineage`` — MLflow registration result.

    Raises
    ------
    HTTPException
        If the adapter is not found (404), export fails (500), or
        license check fails.
    """
    ref = ModelRef(name=name, version=version)
    result = await workbench.merge_service.merge_and_export_by_ref(ref, adapter_id)
    if "error" in result:
        err = str(result["error"])
        if "not found" in err or "license" in err:
            raise HTTPException(status_code=404, detail=err)
        logger.exception(
            "Merge+export failed for %s v%s/%s: %s", name, version, adapter_id, err
        )
        raise HTTPException(status_code=500, detail=err)
    return result