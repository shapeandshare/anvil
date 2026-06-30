"""Current health state of the tracking service.

Replaces the boolean ``_degraded`` flag with a typed state machine.
An internal ``recovering`` phase exists during retry but is not
exposed as a separate UI state — the endpoint reports ``degraded``
until the retry succeeds and the service transitions back to ``active``.
"""

from __future__ import annotations

import time
from typing import Literal

from pydantic import BaseModel

from .degraded_reason import DegradedReason


class DegradedState(BaseModel):
    """Current health state of the tracking service.

    Replaces the boolean ``_degraded`` flag with a typed state machine.
    An internal ``recovering`` phase exists during retry but is not
    exposed as a separate UI state — the endpoint reports ``degraded``
    until the retry succeeds and the service transitions back to ``active``.
    """

    status: Literal["active", "degraded"]
    """Current tracking health: ``active`` or ``degraded``."""

    reason: DegradedReason | None = None
    """Why the service is degraded, or ``None`` if active."""

    message: str = ""
    """Human-readable description of the failure."""

    last_attempt: float | None = None
    """Unix timestamp of the last reconnection attempt, or ``None``."""

    retry_count: int = 0
    """Consecutive retry attempts. Reset to 0 on successful recovery."""

    @classmethod
    def active(cls) -> DegradedState:
        """Return a healthy active state."""
        return cls(status="active")

    @classmethod
    def degraded(
        cls,
        reason: DegradedReason,
        message: str = "",
    ) -> DegradedState:
        """Return a degraded state with the given reason and message.

        Parameters
        ----------
        reason : DegradedReason
            The failure cause.
        message : str, optional
            Human-readable description.
        """
        return cls(
            status="degraded",
            reason=reason,
            message=message,
            last_attempt=time.time(),
        )
