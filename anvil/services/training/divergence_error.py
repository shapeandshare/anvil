"""Training divergence exception — raised when loss becomes non-finite.

Provides :class:`DivergenceError`, raised by ``TrainingService`` from the
progress callback to halt a run whose loss has gone to NaN/inf, mirroring the
``StopRequested`` raise-to-halt pattern.
"""

from .divergence_reason import DivergenceReason


class DivergenceError(Exception):
    """Raised to halt a run that has diverged (non-finite loss).

    Parameters
    ----------
    step : int
        Training step at which divergence was detected.
    reason : DivergenceReason
        Classification of the divergence.
    """

    def __init__(self, step: int, reason: DivergenceReason) -> None:
        self.step = step
        self.reason = reason
        super().__init__(f"Training diverged at step {step}: {reason.value}")
