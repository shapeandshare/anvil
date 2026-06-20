"""Enumeration of training-divergence reasons.

Defines :class:`DivergenceReason`, the neutral, theme-independent classification
of why a run diverged. Surfaced on the SSE ``divergence`` event.
"""

from enum import StrEnum


class DivergenceReason(StrEnum):
    """Why a training run was classified as diverged."""

    LOSS_NAN = "loss_nan"
    LOSS_INF = "loss_inf"
    GRAD_EXPLOSION = "grad_explosion"
