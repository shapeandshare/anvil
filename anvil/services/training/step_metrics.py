# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Per-step training metrics serialized to the SSE ``metrics`` event.

Defines :class:`StepMetrics`, the neutral, theme-independent payload the
service layer builds each step from a :class:`CoreStepObservation` plus
service-derived timing fields. The backend emits only neutral signals; themes
own their own mapping, so this model MUST NOT carry theme-specific values.
"""

from pydantic import BaseModel, ConfigDict


class StepMetrics(BaseModel):
    """Neutral per-step metrics payload.

    Parameters
    ----------
    step : int
        Training step index.
    loss : float
        Loss at this step.
    device : str
        Compute device (``cpu`` / ``cuda:0`` / ``mps``).
    elapsed_sec : float
        Wall-clock seconds since the run started.
    steps_per_sec : float or None
        Rolling step rate, or ``None`` until a rate is available.
    eta_sec : float or None
        Estimated seconds remaining, or ``None``.
    grad_norm : float or None
        Global gradient norm, or ``None`` when unavailable.
    tokens_per_sec : float or None
        Rolling token throughput, or ``None`` until a rate is available.
    """

    model_config = ConfigDict(extra="forbid")

    step: int
    loss: float
    device: str
    elapsed_sec: float
    steps_per_sec: float | None = None
    eta_sec: float | None = None
    grad_norm: float | None = None
    tokens_per_sec: float | None = None
