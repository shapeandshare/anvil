"""Outcomes of audited lifecycle events.

Records whether an action completed successfully, was rejected by
a gate, or encountered an error.
"""

from enum import StrEnum


class AuditOutcome(StrEnum):
    """Outcome of an audited action.

    Values
    ------
    SUCCESS
        The action completed without error.
    REJECTED
        The action was rejected (e.g. by the acceptable-use gate).
    ERROR
        The action encountered an error and did not complete.
    """

    SUCCESS = "success"
    REJECTED = "rejected"
    ERROR = "error"