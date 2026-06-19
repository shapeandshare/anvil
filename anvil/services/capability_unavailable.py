"""Capability unavailable exception — raised when an MLflow capability is not supported.

Provides the ``CapabilityUnavailable`` exception class used by
``TrackingService`` when a requested MLflow capability (such as
managed evaluation datasets) is not available.
"""


class CapabilityUnavailable(Exception):
    """Raised when an MLflow capability (e.g. genai datasets) is unavailable."""

    pass
