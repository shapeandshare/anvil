"""API routes for the interactive teaching loop.

Provides REST endpoints for managing teaching sessions, running rounds,
inspecting results, and comparing models side-by-side.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException

from ...api.deps import get_workbench
from ...workbench import AnvilWorkbench
from .schemas_teach import (
    CompareRoundsBody,
    CreateSessionBody,
    InspectRoundBody,
    RollbackBody,
    StartRoundBody,
    UpdateStatusBody,
)

router = APIRouter()

_SESSION_NOT_FOUND = "Session not found"


########################################################################
# Session CRUD
########################################################################


@router.post("/teach/sessions")
async def create_session(
    body: CreateSessionBody,
    workbench: Annotated[AnvilWorkbench, Depends(get_workbench)],
) -> dict[str, Any]:
    """Create a new teaching session."""
    session = await workbench.teaching.create_session(
        name=body.name,
        description=body.description,
        seed_experiment_id=body.seed_experiment_id,
    )
    return {
        "id": session.id,
        "name": session.name,
        "description": session.description,
        "seed_experiment_id": session.seed_experiment_id,
        "current_base_experiment_id": session.current_base_experiment_id,
        "status": session.status,
        "created_at": str(session.created_at) if session.created_at else None,
        "updated_at": str(session.updated_at) if session.updated_at else None,
    }


@router.get("/teach/sessions")
async def list_sessions(
    workbench: Annotated[AnvilWorkbench, Depends(get_workbench)],
    status: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> dict[str, Any]:
    """List teaching sessions with optional status filter."""
    sessions, total = await workbench.teaching.list_sessions(
        status=status, limit=limit, offset=offset
    )
    return {
        "sessions": [
            {
                "id": s.id,
                "name": s.name,
                "description": s.description,
                "seed_experiment_id": s.seed_experiment_id,
                "current_base_experiment_id": s.current_base_experiment_id,
                "status": s.status,
                "created_at": str(s.created_at) if s.created_at else None,
                "updated_at": str(s.updated_at) if s.updated_at else None,
            }
            for s in sessions
        ],
        "total": total,
    }


@router.get(
    "/teach/sessions/{session_id}",
    responses={404: {"description": _SESSION_NOT_FOUND}},
)
async def get_session(
    session_id: int,
    workbench: Annotated[AnvilWorkbench, Depends(get_workbench)],
) -> dict[str, Any]:
    """Get a single teaching session by ID."""
    session = await workbench.teaching.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=_SESSION_NOT_FOUND)
    return {
        "id": session.id,
        "name": session.name,
        "description": session.description,
        "seed_experiment_id": session.seed_experiment_id,
        "current_base_experiment_id": session.current_base_experiment_id,
        "status": session.status,
        "created_at": str(session.created_at) if session.created_at else None,
        "updated_at": str(session.updated_at) if session.updated_at else None,
    }


@router.delete(
    "/teach/sessions/{session_id}",
    status_code=204,
    responses={404: {"description": _SESSION_NOT_FOUND}},
)
async def delete_session(
    session_id: int,
    workbench: Annotated[AnvilWorkbench, Depends(get_workbench)],
) -> None:
    """Delete a teaching session. Does NOT cascade to MLflow runs."""
    deleted = await workbench.teaching.delete_session(session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=_SESSION_NOT_FOUND)


@router.patch(
    "/teach/sessions/{session_id}/status",
    responses={404: {"description": _SESSION_NOT_FOUND}},
)
async def update_session_status(
    session_id: int,
    body: UpdateStatusBody,
    workbench: Annotated[AnvilWorkbench, Depends(get_workbench)],
) -> dict[str, Any]:
    """Update the status of a teaching session."""
    session = await workbench.teaching.update_status(session_id, body.status)
    if session is None:
        raise HTTPException(status_code=404, detail=_SESSION_NOT_FOUND)
    return {
        "id": session.id,
        "status": session.status,
    }


@router.post(
    "/teach/sessions/{session_id}/rollback",
    responses={404: {"description": _SESSION_NOT_FOUND}},
)
async def rollback_session(
    session_id: int,
    body: RollbackBody,
    workbench: Annotated[AnvilWorkbench, Depends(get_workbench)],
) -> dict[str, Any]:
    """Roll back a session's chain head to a previous round."""
    session = await workbench.teaching.rollback_to_round(
        session_id, body.target_experiment_id
    )
    if session is None:
        raise HTTPException(status_code=404, detail=_SESSION_NOT_FOUND)
    return {
        "id": session.id,
        "current_base_experiment_id": session.current_base_experiment_id,
    }


########################################################################
# Rounds
########################################################################


@router.post(
    "/teach/sessions/{session_id}/rounds",
    responses={
        404: {"description": _SESSION_NOT_FOUND},
        422: {"description": "Validation error"},
    },
)
async def start_round(
    session_id: int,
    body: StartRoundBody,
    workbench: Annotated[AnvilWorkbench, Depends(get_workbench)],
) -> dict[str, Any]:
    """Start a new teaching round.

    Creates a teaching dataset, imports examples, and launches a
    training run.  Method is forced to ``"full"``.
    """
    session = await workbench.teaching.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=_SESSION_NOT_FOUND)
    try:
        result = await workbench.teaching.start_round(
            session_id=session_id,
            examples=body.examples,
            training_config=body.training_config,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return result


@router.get(
    "/teach/sessions/{session_id}/rounds",
    responses={404: {"description": _SESSION_NOT_FOUND}},
)
async def list_rounds(
    session_id: int,
    workbench: Annotated[AnvilWorkbench, Depends(get_workbench)],
) -> dict[str, Any]:
    """List teaching rounds for a session.

    Queries MLflow for runs tagged with the given teaching session ID.
    Returns experiment IDs in round-index order.
    """
    session = await workbench.teaching.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=_SESSION_NOT_FOUND)

    experiments = await workbench.tracking.list_experiments()
    session_rounds = []
    for exp in experiments:
        tags = exp.get("tags", {})
        if isinstance(tags, dict) and tags.get("teaching_session_id") == str(
            session_id
        ):
            session_rounds.append(
                {
                    "experiment_id": exp.get("id"),
                    "mlflow_run_id": exp.get("mlflow_run_id"),
                    "round_index": tags.get("teaching_round_index"),
                    "status": exp.get("status"),
                    "final_loss": exp.get("final_loss"),
                    "created_at": exp.get("created_at"),
                }
            )
    session_rounds.sort(key=lambda r: int(r["round_index"]) if r["round_index"] else 0)
    return {"rounds": session_rounds}


########################################################################
# Inspection and comparison
########################################################################


@router.post(
    "/teach/sessions/{session_id}/rounds/{round_index}/inspect",
    responses={
        404: {"description": _SESSION_NOT_FOUND},
        422: {"description": "Validation error"},
    },
)
async def inspect_round(
    session_id: int,
    round_index: int,
    body: InspectRoundBody,
    workbench: Annotated[AnvilWorkbench, Depends(get_workbench)],
) -> dict[str, Any]:
    """Inspect a round by generating text from its trained model.

    Parameters
    ----------
    session_id : int
        The teaching session ID (validated for existence).
    round_index : int
        Round index (used for route symmetry).
    body : InspectRoundBody
        Experiment ID, prompts, and generation parameters.
    workbench : AnvilWorkbench
        Injected workbench.

    Returns
    -------
    dict
        Per-prompt generated results.
    """
    session = await workbench.teaching.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=_SESSION_NOT_FOUND)

    try:
        results = await workbench.teaching.inspect_round(
            experiment_id=body.experiment_id,
            prompts=body.prompts,
            temperature=body.temperature,
            max_tokens=body.max_tokens,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return {"results": results}


@router.post(
    "/teach/sessions/compare",
    responses={422: {"description": "Validation error"}},
)
async def compare_rounds(
    body: CompareRoundsBody,
    workbench: Annotated[AnvilWorkbench, Depends(get_workbench)],
) -> dict[str, Any]:
    """Side-by-side comparison of two rounds."""
    try:
        results = await workbench.teaching.compare_rounds(
            left_experiment_id=body.left_experiment_id,
            right_experiment_id=body.right_experiment_id,
            prompts=body.prompts,
            temperature=body.temperature,
            max_tokens=body.max_tokens,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return {"results": results}
