"""Governance and audit endpoints for v1 API.

Provides routes for audit trail inspection, chain integrity verification,
provenance reports, license catalog browsing, and takedown requests.
Exposed through ``AnvilWorkbench`` via ``workbench.audit`` and
``workbench.governance``.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from ...api.deps import get_workbench
from ...workbench import AnvilWorkbench
from .schemas import TakedownBody

router = APIRouter()


def _serialise_audit_event(event) -> dict:
    """Serialize an ``AuditEvent`` ORM instance to a plain dict.

    Parameters
    ----------
    event : AuditEvent
        The ORM instance to serialise.

    Returns
    -------
    dict
        Fields matching ``AuditEventOut``.
    """
    return {
        "id": event.id,
        "sequence": event.sequence,
        "action_type": event.action_type,
        "target_type": event.target_type,
        "target_id": event.target_id,
        "actor": event.actor,
        "outcome": event.outcome,
        "reason": event.reason,
        "event_timestamp": str(event.event_timestamp),
    }


@router.get("/governance/audit")
async def list_audit_events(
    workbench: AnvilWorkbench = Depends(get_workbench),
    target_type: str | None = Query(None),
    target_id: str | None = Query(None),
    action_type: str | None = Query(None),
    limit: int = Query(200),
    offset: int = Query(0),
):
    """List audit events with optional filters.

    Parameters
    ----------
    workbench : AnvilWorkbench
        Injected session-bound workbench.
    target_type : str | None
        Filter by target entity type (e.g. ``"dataset"``, ``"corpus"``).
    target_id : str | None
        Filter by target entity ID.
    action_type : str | None
        Filter by action type (e.g. ``"upload"``, ``"takedown"``).
    limit : int, optional
        Maximum events to return. Defaults to ``200``.
    offset : int, optional
        Number of events to skip. Defaults to ``0``.

    Returns
    -------
    dict
        List of ``AuditEventOut`` dicts and ``"error": None``.
    """
    events = await workbench.audit.list_events(
        target_type=target_type,
        target_id=target_id,
        action_type=action_type,
        limit=limit,
        offset=offset,
    )
    return {
        "data": [_serialise_audit_event(e) for e in events],
        "error": None,
    }


@router.get("/governance/audit/verify")
async def verify_audit_chain(
    workbench: AnvilWorkbench = Depends(get_workbench),
):
    """Verify the integrity of the entire audit hash chain.

    Parameters
    ----------
    workbench : AnvilWorkbench
        Injected session-bound workbench.

    Returns
    -------
    dict
        ``ChainVerifyOut`` data and ``"error": None``.
    """
    result = await workbench.audit.verify_chain()
    return {
        "data": {
            "valid": result.valid,
            "break_at_sequence": result.break_at_sequence,
            "entries_checked": result.entries_checked,
        },
        "error": None,
    }


@router.get("/governance/datasets/{id}/report")
async def dataset_governance_report(
    id: int,
    workbench: AnvilWorkbench = Depends(get_workbench),
):
    """Return a combined provenance and audit report for a dataset.

    Composes the provenance view with the audit trail filtered to that
    dataset.

    Parameters
    ----------
    id : int
        The dataset ID.
    workbench : AnvilWorkbench
        Injected session-bound workbench.

    Returns
    -------
    dict
        ``DatasetGovernanceReportOut`` data and ``"error": None``.

    Raises
    ------
    HTTPException
        If the dataset is not found (404).
    """
    dataset = await workbench.dataset_repo.get(id)
    if dataset is None:
        raise HTTPException(status_code=404, detail="Dataset not found")

    provenance = await workbench.governance.get_provenance(
        target_type="dataset",
        target_id=id,
    )
    audit_events = await workbench.audit.list_events(
        target_type="dataset",
        target_id=str(id),
    )
    return {
        "data": {
            "provenance": {
                "source_description": provenance.source_description,
                "license": provenance.license,
                "attribution": provenance.attribution,
                "origin": provenance.origin.value if provenance.origin else "user",
            },
            "audit": [_serialise_audit_event(e) for e in audit_events],
        },
        "error": None,
    }


@router.get("/governance/licenses")
async def list_licenses(
    workbench: AnvilWorkbench = Depends(get_workbench),
):
    """List all approved licenses in the governance catalog.

    Parameters
    ----------
    workbench : AnvilWorkbench
        Injected session-bound workbench.

    Returns
    -------
    dict
        List of license dicts with ``id``, ``identifier``, ``display_name``,
        ``requires_attribution``, ``redistribution_allowed``,
        ``is_own_content_sentinel``, and ``"error": None``.
    """
    licenses = await workbench.governance.list_licenses()
    return {
        "data": [
            {
                "id": lic.id,
                "identifier": lic.identifier,
                "display_name": lic.display_name,
                "requires_attribution": lic.requires_attribution,
                "redistribution_allowed": lic.redistribution_allowed,
                "is_own_content_sentinel": lic.is_own_content_sentinel,
            }
            for lic in licenses
        ],
        "error": None,
    }


@router.post("/datasets/{id}/takedown")
async def takedown_dataset(
    id: int,
    body: TakedownBody,
    workbench: AnvilWorkbench = Depends(get_workbench),
):
    """Submit a takedown request for a dataset.

    Records the takedown event in the audit chain and marks the dataset
    for review. Logs the reason provided by the requestor.

    Parameters
    ----------
    id : int
        The dataset ID.
    body : TakedownBody
        Request body with ``reason`` for the takedown.
    workbench : AnvilWorkbench
        Injected session-bound workbench.

    Returns
    -------
    dict
        Confirmation message and ``"error": None``.

    Raises
    ------
    HTTPException
        If the dataset is not found (404).
    """
    dataset = await workbench.dataset_repo.get(id)
    if dataset is None:
        raise HTTPException(status_code=404, detail="Dataset not found")

    await workbench.audit.record(
        action_type="takedown",
        target_type="dataset",
        target_id=str(id),
        actor="system:takedown",
        outcome="success",
        reason=body.reason,
        params={"dataset_name": dataset.name},
    )

    return {
        "data": {"message": "Takedown request recorded"},
        "error": None,
    }
