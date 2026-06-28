# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Eval dataset endpoints for v1 API.

Provides CRUD operations for evaluation datasets used in model evaluation
workflows. Delegates to the MLflow-backed ``TrackingService`` for storage.
"""

from typing import Any

from fastapi import APIRouter, HTTPException

from ...services._shared.capability_unavailable import CapabilityUnavailable
from ...services.tracking.tracking import TrackingService
from .schemas_eval import AppendRecordsBody, CreateEvalDatasetBody

router = APIRouter()
_tracking_svc = TrackingService()


@router.post("/eval-datasets")
async def create_eval_dataset(body: CreateEvalDatasetBody) -> dict[str, Any]:
    """Create a new evaluation dataset.

    Parameters
    ----------
    body : CreateEvalDatasetBody
        Request body with ``name`` and optional ``tags``.

    Returns
    -------
    dict
        Availability flag, dataset name, and dataset identifier.

    Raises
    ------
    HTTPException
        If ``name`` is missing (400).
    """
    name = body.name
    if not name:
        raise HTTPException(status_code=400, detail="name required")
    tags = body.tags
    try:
        dataset = await _tracking_svc.create_eval_dataset(name=name, tags=tags)
        return {"available": True, "name": name, "dataset": str(dataset)}
    except CapabilityUnavailable as e:
        return {"available": False, "reason": str(e)}


@router.post("/eval-datasets/{name}/records")
async def append_eval_records(name: str, body: AppendRecordsBody) -> dict[str, Any]:
    """Append evaluation records to an existing dataset.

    Parameters
    ----------
    name : str
        The name of the evaluation dataset.
    body : AppendRecordsBody
        Request body with a ``records`` key containing a list of records.

    Returns
    -------
    dict
        Availability flag and count of appended records.
    """
    records = body.records
    try:
        count = await _tracking_svc.append_eval_records(name=name, records=records)
        return {"available": True, "appended": count}
    except CapabilityUnavailable as e:
        return {"available": False, "reason": str(e)}


@router.get("/eval-datasets/{name}")
async def get_eval_dataset(name: str) -> dict[str, Any]:
    """Retrieve an evaluation dataset by name.

    Parameters
    ----------
    name : str
        The name of the evaluation dataset.

    Returns
    -------
    dict
        Availability flag and dataset details.

    Raises
    ------
    HTTPException
        If the dataset is not found (404).
    """
    try:
        dataset = await _tracking_svc.get_eval_dataset(name=name)
        if dataset is None:
            raise HTTPException(status_code=404, detail=f"Dataset '{name}' not found")
        return {"available": True, "name": name, "dataset": str(dataset)}
    except CapabilityUnavailable as e:
        return {"available": False, "reason": str(e)}
