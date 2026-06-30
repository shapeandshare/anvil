"""Tracking service health state — degraded mode status, reason, and response models.

Provides the ``DegradedReason`` enumeration, ``DegradedState`` value object,
and ``TrackingStatus`` response model used by ``TrackingService`` and the
``/v1/health/detailed`` endpoint.
"""

from __future__ import annotations

import time
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel


class DegradedReason(StrEnum):
    """Enumeration of failure causes for tracking service degraded mode.

    Values determine whether automatic retry is attempted.
    """

    UNREACHABLE = "unreachable"
    """MLflow server is unreachable (connection error, timeout, socket error).
    Automatic retry with exponential backoff is attempted."""

    INCOMPATIBLE_VERSION = "incompatible_version"
    """MLflow server version is incompatible. No automatic retry."""

    AUTH_FAILURE = "auth_failure"
    """MLflow server rejected credentials (HTTP 401/403). No automatic retry."""

    PERMANENT_ERROR = "permanent_error"
    """Non-retryable MLflow error. No automatic retry."""

    UNKNOWN = "unknown"
    """Unexpected exception during reconnection attempt. No automatic retry."""

    @property
    def should_retry(self) -> bool:
        """Whether the tracking service should attempt automatic reconnection."""
        return self == DegradedReason.UNREACHABLE


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
