"""Resolved compute backend identifier enumeration."""

from enum import StrEnum


class ComputeBackendResult(StrEnum):
    """Resolved compute backend identifier stored in result objects.

    Attributes
    ----------
    LOCAL : str
        Local execution (``"local"``).
    MODAL : str
        Modal cloud GPU execution (``"modal"``).
    """

    LOCAL = "local"
    MODAL = "modal"