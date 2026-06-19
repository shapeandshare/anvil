"""Result type for acceptable-use gate evaluations.

Returned by :meth:`GovernanceService.evaluate_submission` to
indicate whether data entering the system passes the no-harm gate.
"""

from pydantic import BaseModel

from .data_origin import DataOrigin


class GateDecision(BaseModel):
    """Outcome of a gate evaluation.

    Parameters
    ----------
    accepted : bool
        Whether the submission is permitted.
    reason : str | None
        Human-readable explanation (for rejections, a clear and
        respectful reason; for accepted submissions, ``None``).
    license_id : int | None
        The resolved ``license_catalog.id`` (``None`` if own-content).
    origin : DataOrigin
        Whether the accepted data is ``bundled`` sample data or
        ``user``-supplied.
    """

    accepted: bool
    reason: str | None = None
    license_id: int | None = None
    origin: DataOrigin = DataOrigin.USER