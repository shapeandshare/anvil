# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Experiment data transfer object.

``Experiment`` is a Pydantic ``BaseModel`` representing a single experiment
record as returned by the anvil server API for experiment tracking.
"""

from __future__ import annotations

from pydantic import BaseModel


class Experiment(BaseModel):
    """A single experiment record from the anvil server.

    Parameters
    ----------
    id : str
        Unique experiment identifier.
    name : str
        Human-readable experiment name.
    run_count : int, optional
        Number of runs under this experiment. Defaults to ``0``.
    best_loss : float | None, optional
        Lowest loss achieved across all runs, if any.
    duration : float | None, optional
        Total wall-clock duration across all runs, if available.
    mlflow_url : str | None, optional
        Direct URL to the experiment in the MLflow UI, if available.
    """

    id: str
    name: str
    run_count: int = 0
    best_loss: float | None = None
    duration: float | None = None
    mlflow_url: str | None = None
