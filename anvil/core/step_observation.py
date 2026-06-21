# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Per-step training observation emitted by the core engines.

Defines :class:`CoreStepObservation`, a zero-dependency stdlib value object
the training engines pass to their progress callback each step. It carries
only primitive observations so the core engine remains free of third-party
dependencies (Constitution Article I); the service layer wraps it into a
Pydantic model for the SSE boundary.
"""

from typing import NamedTuple


class CoreStepObservation(NamedTuple):
    """A single training step's neutral observations.

    Parameters
    ----------
    step : int
        Zero-based training step index.
    loss : float
        Loss value at this step. May be non-finite (NaN/inf) on divergence.
    tokens : int
        Number of tokens actually processed at this step. The engines are
        unbatched and variable-length, so this varies per document and is the
        only correct basis for a tokens-per-second rate.
    grad_norm : float or None
        Global (un-clipped) gradient norm sampled after the backward pass.
        ``None`` when the engine does not compute it (e.g. the pure stdlib
        engine).
    """

    step: int
    loss: float
    tokens: int
    grad_norm: float | None
