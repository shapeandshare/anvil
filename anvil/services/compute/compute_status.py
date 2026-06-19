"""Lifecycle status enumeration for compute runs.

``ComputeStatus`` enumerates the lifecycle states a compute run can pass
through, from submission through completion or failure.
"""

from enum import StrEnum


class ComputeStatus(StrEnum):
    """Lifecycle status of a compute run.

    Attributes
    ----------
    SUBMITTED : str
        Remote job accepted by the backend, not yet running (``"submitted"``).
    RUNNING : str
        Remote job in progress (``"running"``).
    COMPLETED : str
        Training finished successfully (``"completed"``).
    FAILED : str
        Training finished with an error (``"failed"``).
    """

    SUBMITTED = "submitted"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
