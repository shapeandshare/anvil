# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Backup & Restore API routes (feature 026).

Provides HTTP endpoints for creating, listing, verifying, restoring, and
deleting full-deployment backups.  Audit events (FR-031) are emitted at
the route layer via the session-bound ``workbench.audit`` (research R11).
"""

import asyncio
import json
from collections.abc import AsyncGenerator
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

from ...services.governance.audit_action import AuditAction
from ...services.governance.audit_outcome import AuditOutcome
from ...services.governance.audit_target_type import AuditTargetType
from ...workbench import AnvilWorkbench
from ..deps import get_workbench

router = APIRouter()


@router.post("/backup", status_code=202)
async def create_backup(
    request: Request,
    wb: Annotated[AnvilWorkbench, Depends(get_workbench)],
) -> dict[str, Any]:
    """Initiate a full deployment backup.

    Returns 202 with the new backup id.  The caller observes progress
    via ``GET /v1/backup/stream/{id}``.
    """
    svc = request.app.state.backup_service

    try:
        result = await svc.create_backup(repo=wb.backup_repo)
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    # Audit: backup_create.
    try:
        await wb.audit.record(
            action_type=AuditAction.BACKUP_CREATE.value,
            target_type=AuditTargetType.BACKUP.value,
            target_id=result.backup_id,
            actor="system",
            outcome=AuditOutcome.SUCCESS.value,
            params={"backup_id": result.backup_id},
        )
    except (RuntimeError, ValueError):
        pass

    # Audit: one backup_delete per rotated id.
    for rid in result.rotated_backup_ids:
        try:
            await wb.audit.record(
                action_type=AuditAction.BACKUP_DELETE.value,
                target_type=AuditTargetType.BACKUP.value,
                target_id=rid,
                actor="system",
                outcome=AuditOutcome.SUCCESS.value,
                params={"reason": "auto-rotation", "triggered_by": result.backup_id},
            )
        except (RuntimeError, ValueError):
            pass

    return {"backup_id": result.backup_id, "status": "creating"}


@router.get("/backup")
async def list_backups(
    request: Request,
    wb: Annotated[AnvilWorkbench, Depends(get_workbench)],
) -> list[dict[str, Any]]:
    """Return all backup operations as a list of summaries."""
    svc = request.app.state.backup_service
    summaries = await svc.list_backups(repo=wb.backup_repo)
    return [s.model_dump(mode="json") for s in summaries]


@router.get("/backup/status")
async def backup_status(
    request: Request,
    wb: Annotated[AnvilWorkbench, Depends(get_workbench)],
) -> dict[str, Any]:
    """Return backup storage status for the Operations page."""
    svc = request.app.state.backup_service
    status = await svc.storage_status(repo=wb.backup_repo)
    return status.model_dump(mode="json")  # type: ignore[no-any-return]


@router.post("/backup/cleanup-safety", response_model=None)
async def cleanup_safety(
    request: Request,
    wb: Annotated[AnvilWorkbench, Depends(get_workbench)],
) -> dict[str, Any] | JSONResponse:
    """Remove all pre-restore safety snapshots (FR-020).

    Returns the count of deleted snapshots.
    """
    svc = getattr(request.app.state, "backup_service", None)
    if svc is None:
        return JSONResponse(
            status_code=503,
            content={
                "detail": "Backup service not available (not initialized during startup)"
            },
        )
    try:
        count = await svc.cleanup_safety(repo=wb.backup_repo)
    except (ValueError, RuntimeError, OSError) as exc:
        return JSONResponse(
            status_code=500, content={"detail": str(exc), "code": type(exc).__name__}
        )
    return {"deleted_count": count}


@router.get("/backup/stream/{operation_id}")
async def stream_backup_progress(
    operation_id: str, request: Request
) -> StreamingResponse:
    """SSE stream for backup/restore progress.

    Mirrors the training SSE contract
    (``anvil/api/v1/training.py:stream_training``).
    """
    svc = request.app.state.backup_service
    queue = svc.stream_for(operation_id)

    if queue is None:

        async def _done() -> AsyncGenerator[str, None]:
            yield "event: error\ndata: " + json.dumps(
                {"message": "Operation not found or already completed"}
            ) + "\n\n"

        return StreamingResponse(
            _done(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    async def event_stream() -> AsyncGenerator[str, None]:
        while True:
            try:
                msg = await asyncio.wait_for(queue.get(), timeout=30)
                yield f"event: {msg.event}\ndata: {msg.model_dump_json()}\n\n"
                if msg.event in ("complete", "error"):
                    break
            except TimeoutError:
                yield "event: heartbeat\ndata: {}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/backup/{backup_id}", response_model=None)
async def get_backup(
    backup_id: str,
    request: Request,
    wb: Annotated[AnvilWorkbench, Depends(get_workbench)],
) -> dict[str, Any] | JSONResponse:
    """Return a single backup summary."""
    svc = request.app.state.backup_service
    summary = await svc.get_backup(repo=wb.backup_repo, backup_id=backup_id)
    if summary is None:
        return JSONResponse(status_code=404, content={"detail": "Backup not found"})
    return summary.model_dump(mode="json")  # type: ignore[no-any-return]


@router.get("/backup/{backup_id}/preview", response_model=None)
async def preview_restore(
    backup_id: str,
    request: Request,
    wb: Annotated[AnvilWorkbench, Depends(get_workbench)],
) -> dict[str, Any] | JSONResponse:
    """Return restore preview for a given backup (FR-024).

    Fetches the backup manifest and returns deployment version, schema
    revision, compatibility assessment, entry count, and size.  Called
    by the operations page before showing the restore confirmation
    modal.
    """
    svc = request.app.state.backup_service
    try:
        preview = await svc.restore_preview(backup_id)
    except ValueError as exc:
        return JSONResponse(status_code=404, content={"detail": str(exc)})
    return preview.model_dump(mode="json")  # type: ignore[no-any-return]


@router.post("/backup/{backup_id}/verify")
async def verify_backup(
    backup_id: str,
    request: Request,
    wb: Annotated[AnvilWorkbench, Depends(get_workbench)],
) -> dict[str, Any]:
    """Verify integrity of a backup archive (FR-025)."""
    svc = request.app.state.backup_service
    result = await svc.verify(backup_id, repo=wb.backup_repo)
    return result.model_dump(mode="json")  # type: ignore[no-any-return]


@router.post("/backup/{backup_id}/restore", status_code=202, response_model=None)
async def restore_backup(
    backup_id: str,
    request: Request,
    wb: Annotated[AnvilWorkbench, Depends(get_workbench)],
) -> dict[str, Any] | JSONResponse:
    """Restore a deployment from a backup."""
    body = await request.json()
    confirm = body.get("confirm", "")
    svc = request.app.state.backup_service

    try:
        result = await svc.restore(
            backup_id=backup_id,
            confirm=confirm,
            repo=wb.backup_repo,
        )
    except ValueError as exc:
        return JSONResponse(status_code=400, content={"detail": str(exc)})
    except PermissionError as exc:
        return JSONResponse(status_code=409, content={"detail": str(exc)})
    except RuntimeError as exc:
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    try:
        await wb.audit.record(
            action_type=AuditAction.BACKUP_RESTORE.value,
            target_type=AuditTargetType.BACKUP.value,
            target_id=backup_id,
            actor="system",
            outcome=AuditOutcome.SUCCESS.value,
            params={"safety_snapshot_id": result.get("safety_snapshot_id")},
        )
    except (RuntimeError, ValueError):
        pass

    return dict(result)


@router.delete("/backup/{backup_id}", response_model=None)
async def delete_backup(
    backup_id: str,
    request: Request,
    wb: Annotated[AnvilWorkbench, Depends(get_workbench)],
) -> dict[str, Any] | JSONResponse:
    """Delete a backup archive and its DB record."""
    svc = request.app.state.backup_service
    try:
        await svc.delete_backup(backup_id, repo=wb.backup_repo)
    except ValueError as exc:
        return JSONResponse(status_code=404, content={"detail": str(exc)})
    except PermissionError as exc:
        return JSONResponse(status_code=403, content={"detail": str(exc)})

    try:
        await wb.audit.record(
            action_type=AuditAction.BACKUP_DELETE.value,
            target_type=AuditTargetType.BACKUP.value,
            target_id=backup_id,
            actor="system",
            outcome=AuditOutcome.SUCCESS.value,
        )
    except (RuntimeError, ValueError):
        pass

    return {"deleted": backup_id}
