from typing import Any

from fastapi import APIRouter, HTTPException

from microgpt.services.tracking import CapabilityUnavailable, TrackingService

router = APIRouter()
_tracking_svc = TrackingService()


@router.post("/eval-datasets")
async def create_eval_dataset(body: dict) -> dict[str, Any]:
    name = body.get("name")
    if not name:
        raise HTTPException(status_code=400, detail="name required")
    tags = body.get("tags")
    try:
        dataset = await _tracking_svc.create_eval_dataset(name=name, tags=tags)
        return {"available": True, "name": name, "dataset": str(dataset)}
    except CapabilityUnavailable as e:
        return {"available": False, "reason": str(e)}


@router.post("/eval-datasets/{name}/records")
async def append_eval_records(name: str, body: dict) -> dict[str, Any]:
    records = body.get("records", [])
    try:
        count = await _tracking_svc.append_eval_records(name=name, records=records)
        return {"available": True, "appended": count}
    except CapabilityUnavailable as e:
        return {"available": False, "reason": str(e)}


@router.get("/eval-datasets/{name}")
async def get_eval_dataset(name: str) -> dict[str, Any]:
    try:
        dataset = await _tracking_svc.get_eval_dataset(name=name)
        if dataset is None:
            raise HTTPException(status_code=404, detail=f"Dataset '{name}' not found")
        return {"available": True, "name": name, "dataset": str(dataset)}
    except CapabilityUnavailable as e:
        return {"available": False, "reason": str(e)}
