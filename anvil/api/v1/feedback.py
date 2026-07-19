# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Visual Feedback Annotation API routes (feature 001).

Provides HTTP endpoints for creating, listing, retrieving, and managing
feedback reports with visual annotations. Endpoints cover screenshot
capture, annotation export, status transitions, and batch operations.
"""

from __future__ import annotations

import json
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request, UploadFile
from starlette.responses import StreamingResponse

from ...api.deps import get_workbench
from ...workbench import AnvilWorkbench

router = APIRouter()


@router.post("/feedback", status_code=201)
async def create_feedback_report(
    workbench: Annotated[AnvilWorkbench, Depends(get_workbench)],
    page_url: str = Form(..., description="URL of the page being reviewed"),
    viewport_width: int = Form(..., description="Viewport width in pixels"),
    viewport_height: int = Form(..., description="Viewport height in pixels"),
    annotations: str = Form("[]", description="JSON array of annotation objects"),
    reporter_id: str = Form("default", description="Reporter identifier"),
    notes_summary: str | None = Form(None, description="Optional summary note"),
    document_title: str | None = Form(
        None, description="Document title at annotation time"
    ),
    user_agent: str | None = Form(None, description="Browser user agent string"),
    screenshot: UploadFile | None = None,
    annotated: UploadFile | None = None,
) -> dict[str, Any]:
    """Create a new feedback report.

    Accepts multipart form data with optional screenshot files and
    a JSON-encoded ``annotations`` field. Returns the created report
    identifier.

    Parameters
    ----------
    workbench : AnvilWorkbench
        Injected session-bound workbench.
    page_url : str
        URL of the page being reviewed.
    viewport_width : int
        Browser viewport width in pixels at capture time.
    viewport_height : int
        Browser viewport height in pixels at capture time.
    annotations : str
        JSON array of annotation objects, each with ``type``,
        ``note``, and ``data`` fields.
    reporter_id : str
        Identifier of the reporter.
    notes_summary : str, optional
        Optional summary note.
    screenshot : UploadFile, optional
        Raw screenshot PNG file.
    annotated : UploadFile, optional
        Annotated screenshot PNG file.

    Returns
    -------
    dict[str, Any]
        ``{"ok": True, "id": <report_id>}``

    Raises
    ------
    HTTPException
        400 if any annotation note exceeds 2000 characters.
    """
    # Parse and validate annotations
    parsed_annotations: list[dict[str, Any]] = []
    if annotations and annotations != "[]":
        try:
            parsed_annotations = json.loads(annotations)
            if not isinstance(parsed_annotations, list):
                parsed_annotations = []
        except (json.JSONDecodeError, ValueError):
            parsed_annotations = []

    # Validate note lengths and annotation data schemas
    for ann in parsed_annotations:
        note = ann.get("note", "")
        if note and len(note) > 2000:
            raise HTTPException(
                status_code=400,
                detail="Annotation note exceeds 2000 character limit",
            )

        ann_type = ann.get("type", "element")
        ann_data_raw = ann.get("data", "{}")

        # Parse data if it's a string
        ann_data: Any = ann_data_raw
        if isinstance(ann_data_raw, str):
            try:
                ann_data = json.loads(ann_data_raw)
            except (json.JSONDecodeError, ValueError):
                ann_data = {}

        if ann_type == "circle":
            if not isinstance(ann_data, dict):
                raise HTTPException(
                    status_code=400,
                    detail="Circle annotation data must be a JSON object",
                )
            if "cx" not in ann_data or "cy" not in ann_data or "radius" not in ann_data:
                raise HTTPException(
                    status_code=400,
                    detail="Circle annotation requires cx, cy, and radius fields",
                )
            if not all(
                isinstance(ann_data.get(k), (int, float))
                for k in ("cx", "cy", "radius")
            ):
                raise HTTPException(
                    status_code=400,
                    detail="Circle annotation cx, cy, radius must be numeric",
                )
            if ann_data["radius"] <= 0:
                raise HTTPException(
                    status_code=400,
                    detail="Circle annotation radius must be positive",
                )

        elif ann_type == "freehand":
            if not isinstance(ann_data, dict):
                raise HTTPException(
                    status_code=400,
                    detail="Freehand annotation data must be a JSON object",
                )
            if "path" not in ann_data or "bounds" not in ann_data:
                raise HTTPException(
                    status_code=400,
                    detail="Freehand annotation requires path and bounds fields",
                )
            if not isinstance(ann_data["path"], list) or len(ann_data["path"]) < 2:
                raise HTTPException(
                    status_code=400,
                    detail="Freehand annotation path must be an array with at least 2 points",
                )
            for point in ann_data["path"]:
                if not isinstance(point, (list, tuple)) or len(point) != 2:
                    raise HTTPException(
                        status_code=400,
                        detail="Each freehand path point must be an [x, y] pair",
                    )
            bounds = ann_data["bounds"]
            if not isinstance(bounds, dict) or not all(
                k in bounds for k in ("minX", "minY", "maxX", "maxY")
            ):
                raise HTTPException(
                    status_code=400,
                    detail="Freehand annotation bounds must have minX, minY, maxX, maxY",
                )

    # Read screenshot files
    screenshot_data: bytes | None = None
    if screenshot is not None:
        screenshot_data = await screenshot.read()

    annotated_data: bytes | None = None
    if annotated is not None:
        annotated_data = await annotated.read()

    report = await workbench.feedback.submit_report(
        page_url=page_url,
        viewport_width=viewport_width,
        viewport_height=viewport_height,
        screenshot_data=screenshot_data,
        annotated_data=annotated_data,
        annotations=parsed_annotations,
        reporter_id=reporter_id,
        notes_summary=notes_summary,
        document_title=document_title,
        user_agent=user_agent,
    )
    return {"ok": True, "id": report.id}


@router.get("/feedback")
async def list_feedback_reports(
    workbench: Annotated[AnvilWorkbench, Depends(get_workbench)],
    status: str | None = Query(None, description="Filter by status"),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
) -> dict[str, Any]:
    """List all feedback reports.

    Returns a paginated list of feedback reports with summary
    metadata (status, created_at, annotation count, screenshot
    thumbnail).

    Parameters
    ----------
    workbench : AnvilWorkbench
        Injected session-bound workbench.
    status : str, optional
        Optional status filter.
    page : int
        Page number (1-indexed).
    per_page : int
        Number of results per page.

    Returns
    -------
    dict[str, Any]
        ``{"ok": True, "reports": [...], "total": <count>}``
    """
    reports, total = await workbench.feedback.list_reports(
        status=status,
        page=page,
        per_page=per_page,
    )
    return {
        "ok": True,
        "reports": [
            {
                "id": r.id,
                "page_url": r.page_url,
                "viewport_width": r.viewport_width,
                "viewport_height": r.viewport_height,
                "status": r.status,
                "reporter_id": r.reporter_id,
                "notes_summary": r.notes_summary,
                "document_title": r.document_title,
                "user_agent": r.user_agent,
                "screenshot_path": r.screenshot_path,
                "annotated_path": r.annotated_path,
                "annotation_count": len(r.annotations) if r.annotations else 0,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "updated_at": r.updated_at.isoformat() if r.updated_at else None,
            }
            for r in reports
        ],
        "total": total,
    }


@router.get("/feedback/{report_id}")
async def get_feedback_report(
    report_id: int,
    workbench: Annotated[AnvilWorkbench, Depends(get_workbench)],
) -> dict[str, Any]:
    """Get a single feedback report by ID.

    Returns full report details including all annotations and
    screenshot metadata.

    Parameters
    ----------
    report_id : int
        The unique identifier of the feedback report.
    workbench : AnvilWorkbench
        Injected session-bound workbench.

    Returns
    -------
    dict[str, Any]
        ``{"ok": True, "report": {...}}``
    """
    report = await workbench.feedback.get_report(report_id)
    if report is None:
        raise HTTPException(
            status_code=404,
            detail=f"Feedback report {report_id} not found",
        )
    annotations = report.annotations or []
    return {
        "ok": True,
        "report": {
            "id": report.id,
            "page_url": report.page_url,
            "viewport_width": report.viewport_width,
            "viewport_height": report.viewport_height,
            "status": report.status,
            "reporter_id": report.reporter_id,
            "notes_summary": report.notes_summary,
            "screenshot_path": report.screenshot_path,
            "annotated_path": report.annotated_path,
            "annotations": [
                {
                    "id": a.id,
                    "annotation_type": a.annotation_type,
                    "note": a.note,
                    "data": a.data,
                    "order": a.order,
                    "created_at": a.created_at.isoformat() if a.created_at else None,
                }
                for a in annotations
            ],
            "created_at": report.created_at.isoformat() if report.created_at else None,
            "updated_at": report.updated_at.isoformat() if report.updated_at else None,
        },
    }


@router.get("/feedback/{report_id}/screenshot")
async def get_feedback_screenshot(
    report_id: int,
    workbench: Annotated[AnvilWorkbench, Depends(get_workbench)],
) -> StreamingResponse:
    """Get the screenshot associated with a feedback report.

    Returns the screenshot image data (PNG) as a streaming response.

    Parameters
    ----------
    report_id : int
        The unique identifier of the feedback report.
    workbench : AnvilWorkbench
        Injected session-bound workbench.

    Returns
    -------
    StreamingResponse
        The screenshot PNG bytes with appropriate content type.

    Raises
    ------
    HTTPException
        If the report or screenshot is not found.
    """
    report = await workbench.feedback.get_report(report_id)
    if report is None or report.screenshot_path is None:
        raise HTTPException(
            status_code=404,
            detail="Screenshot not found for this report",
        )

    store = workbench.feedback._store  # pylint: disable=protected-access
    return StreamingResponse(
        store.get(report.screenshot_path),
        media_type="image/png",
        headers={
            "Content-Disposition": f'inline; filename="screenshot_{report_id}.png"'
        },
    )


@router.get("/feedback/{report_id}/export")
async def export_feedback_report(
    report_id: int,
    workbench: Annotated[AnvilWorkbench, Depends(get_workbench)],
) -> dict[str, Any]:
    """Export a feedback report in a shareable format.

    Returns a serialised representation of the report including
    all annotations, screenshot metadata, and notes suitable for
    external sharing or archival.

    Parameters
    ----------
    report_id : int
        The unique identifier of the feedback report.
    workbench : AnvilWorkbench
        Injected session-bound workbench.

    Returns
    -------
    dict[str, Any]
        ``{"ok": True, "export": {...}}``
    """
    export = await workbench.feedback.export_report(report_id)
    if export is None:
        raise HTTPException(
            status_code=404,
            detail=f"Feedback report {report_id} not found",
        )
    return {"ok": True, "export": export}


@router.patch("/feedback/{report_id}/status")
async def update_feedback_status(
    report_id: int,
    workbench: Annotated[AnvilWorkbench, Depends(get_workbench)],
    request: Request,
) -> dict[str, Any]:
    """Update the status of a feedback report.

    Accepts a new status value (``open``, ``in_progress``,
    ``resolved``) and transitions the report accordingly.

    Parameters
    ----------
    report_id : int
        The unique identifier of the feedback report.
    workbench : AnvilWorkbench
        Injected session-bound workbench.
    request : Request
        The incoming HTTP request (for JSON body parsing).

    Returns
    -------
    dict[str, Any]
        ``{"ok": True}``
    """
    body = await request.json()
    new_status = body.get("status")
    if new_status is None:
        raise HTTPException(
            status_code=400,
            detail="Missing required field: status",
        )
    report = await workbench.feedback.update_status(report_id, new_status)
    if report is None:
        raise HTTPException(
            status_code=404,
            detail=f"Feedback report {report_id} not found",
        )
    return {"ok": True}


@router.delete("/feedback/{report_id}")
async def delete_feedback_report(
    report_id: int,
    workbench: Annotated[AnvilWorkbench, Depends(get_workbench)],
) -> dict[str, Any]:
    """Delete a feedback report.

    Permanently removes the report and its associated screenshot
    and annotations.

    Parameters
    ----------
    report_id : int
        The unique identifier of the feedback report.
    workbench : AnvilWorkbench
        Injected session-bound workbench.

    Returns
    -------
    dict[str, Any]
        ``{"ok": True}``
    """
    deleted = await workbench.feedback.delete_report(report_id)
    if not deleted:
        raise HTTPException(
            status_code=404,
            detail=f"Feedback report {report_id} not found",
        )
    return {"ok": True}


@router.post("/feedback/batch-delete")
async def batch_delete_feedback_reports(
    workbench: Annotated[AnvilWorkbench, Depends(get_workbench)],
    request: Request,
) -> dict[str, Any]:
    """Batch delete multiple feedback reports.

    Accepts a list of report IDs and deletes them all in a
    single operation.

    Parameters
    ----------
    workbench : AnvilWorkbench
        Injected session-bound workbench.
    request : Request
        The incoming HTTP request (for JSON body parsing).

    Returns
    -------
    dict[str, Any]
        ``{"ok": True, "deleted": <count>}``
    """
    body = await request.json()
    ids = body.get("ids", [])
    if not isinstance(ids, list) or not ids:
        raise HTTPException(
            status_code=400,
            detail="Missing or invalid required field: ids (must be a non-empty list of integers)",
        )
    deleted = await workbench.feedback.batch_delete(ids)
    return {"ok": True, "deleted": deleted}
