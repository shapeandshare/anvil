"""Rolling training throughput and divergence classification.

Provides :class:`ThroughputTracker`, a rolling-window estimator of step rate
and token rate, and :func:`classify_divergence`, which detects non-finite
loss. Both are neutral, theme-independent helpers used by the
``TrainingService`` progress callback to build :class:`StepMetrics` and to
decide when to raise :class:`DivergenceError`.
"""

import math
from collections import deque

from .divergence_reason import DivergenceReason


def classify_divergence(loss: float) -> DivergenceReason | None:
    """Classify a loss value as a divergence reason, if any.

    Parameters
    ----------
    loss : float
        The loss value to inspect.

    Returns
    -------
    DivergenceReason or None
        ``LOSS_NAN`` if ``loss`` is NaN, ``LOSS_INF`` if it is infinite,
        otherwise ``None``.
    """
    if math.isnan(loss):
        return DivergenceReason.LOSS_NAN
    if math.isinf(loss):
        return DivergenceReason.LOSS_INF
    return None


class ThroughputTracker:
    """Rolling-window estimator of step rate and token throughput.

    Token rate is computed from the actual per-step token counts summed over
    the window divided by the window's elapsed wall-clock time. This is exact
    for the engines' unbatched, variable-length steps and does not assume any
    fixed batch size or context length.

    Parameters
    ----------
    window : int
        Maximum number of recent steps to retain in the rolling window.
    """

    def __init__(self, window: int = 20) -> None:
        self._times: deque[float] = deque(maxlen=window)
        self._tokens: deque[int] = deque(maxlen=window)

    def record(self, tokens: int, now: float) -> None:
        """Record one step's token count at a wall-clock timestamp.

        Parameters
        ----------
        tokens : int
            Tokens processed at this step.
        now : float
            Monotonic timestamp (seconds) for this step.
        """
        self._times.append(now)
        self._tokens.append(tokens)

    @property
    def _window_elapsed(self) -> float:
        if len(self._times) < 2:
            return 0.0
        return self._times[-1] - self._times[0]

    @property
    def steps_per_sec(self) -> float | None:
        """Rolling steps-per-second, or ``None`` until two samples exist."""
        elapsed = self._window_elapsed
        if elapsed <= 0.0:
            return None
        return (len(self._times) - 1) / elapsed

    @property
    def tokens_per_sec(self) -> float | None:
        """Rolling tokens-per-second over the window, or ``None``.

        Divides the total tokens currently held in the window by the window's
        elapsed wall-clock time. Returns ``None`` until at least two samples
        bound a non-zero interval.
        """
        elapsed = self._window_elapsed
        if elapsed <= 0.0:
            return None
        return sum(self._tokens) / elapsed

    def eta_sec(self, step: int, total_steps: int) -> float | None:
        """Estimate seconds remaining, or ``None`` if no rate is available.

        Parameters
        ----------
        step : int
            Current step index.
        total_steps : int
            Total planned steps.

        Returns
        -------
        float or None
            Estimated seconds remaining, or ``None``.
        """
        rate = self.steps_per_sec
        if not rate or rate <= 0.0:
            return None
        remaining = max(0, total_steps - step - 1)
        return remaining / rate
