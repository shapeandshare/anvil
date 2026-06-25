# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Compute backends API route.

Returns available compute backends for training (local CPU, local GPU, Modal, etc.).
"""

from typing import Any

from fastapi import APIRouter

from ...services.compute.registry import available_backends

router = APIRouter()


@router.get("/compute/backends")
async def list_compute_backends() -> list[dict[str, Any]]:
    """List all registered compute backends with availability status.

    Returns
    -------
    list
        A JSON array of dicts, each with:
          - ``value``: backend identifier (e.g. ``ComputeBackend.AUTO``,
            ``ComputeBackend.LOCAL_CPU``, ``ComputeBackend.LOCAL_GPU``,
            ``ComputeBackend.MODAL``)
          - ``label``: human-readable name
          - ``available``: bool
          - ``reason``: str | None — explanation if unavailable
    """
    return available_backends()
