"""Compute backends API route.

Returns available compute backends for training (local CPU, local GPU, Modal, etc.).
"""

from fastapi import APIRouter

from ...services.compute.registry import available_backends

router = APIRouter()


@router.get("/compute/backends")
async def list_compute_backends():
    """List all registered compute backends with availability status.

    Returns
    -------
    list
        A JSON array of dicts, each with:
          - ``value``: backend identifier (e.g. ``"auto"``, ``"local-cpu"``,
            ``"local-gpu"``, ``"modal"``)
          - ``label``: human-readable name
          - ``available``: bool
          - ``reason``: str | None — explanation if unavailable
    """
    return available_backends()
