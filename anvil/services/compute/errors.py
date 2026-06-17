"""Compute-backend exceptions.

Follows anvil's degraded-mode convention: non-fatal errors return empty values
and set ``self._degraded = True`` instead of raising. Only raise when the
caller explicitly opted into a capability that is missing (D4).
"""

from __future__ import annotations


class ComputeBackendUnavailable(Exception):
    """Raised when the user explicitly selected a backend that is not available.

    D4 rule: implicit capability upgrades (e.g. GPU→CPU) silently fall back.
    This exception is ONLY raised for *explicit* selections that cannot be
    honoured — it is never caught silently.
    """


class RemoteSubmissionError(Exception):
    """Raised when a remote job submission fails (auth, connectivity, quota)."""


class RemotePollError(Exception):
    """Raised when polling a remote job fails persistently."""
