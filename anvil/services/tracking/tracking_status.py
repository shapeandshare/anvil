"""Response model for the tracking service status block.

Returned by ``TrackingService`` as part of the ``/v1/health/detailed`` endpoint.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from .degraded_reason import DegradedReason


class TrackingStatus(BaseModel):
    """Tracking service status block returned by ``GET /v1/health/detailed``."""

    status: Literal["active", "degraded"]
    """Current tracking health."""

    reason: DegradedReason | None = None
    """Failure cause when degraded, or ``None`` when active."""

    message: str = ""
    """Human-readable description of the failure or empty string when active."""

    last_attempt: float | None = None
    """Unix timestamp of the last reconnection attempt, or ``None``."""
