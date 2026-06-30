"""Enumeration of failure causes for the tracking service degraded mode.

Values determine whether automatic retry is attempted.
"""

from __future__ import annotations

from enum import StrEnum


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
