# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Training start command — start a new training run.

``TrainingStartCommand`` sends a ``POST /v1/training/start`` request
with a ``TrainingConfig`` payload and returns the server's response.
"""

from __future__ import annotations

from .._shared.abstract_command import AbstractCommand
from .._shared.http_method import HttpMethod
from .training_config import TrainingConfig


class TrainingStartCommand(AbstractCommand):
    """Start a new training run — ``POST /v1/training/start``."""

    async def execute(self, config: TrainingConfig) -> dict[str, object]:
        """Start a training run with the given configuration.

        Parameters
        ----------
        config : TrainingConfig
            Hyperparameters and data-source references for the run.

        Returns
        -------
        dict[str, object]
            The server response payload containing ``run_id``,
            ``mlflow_run_id``, and ``experiment_id``.
        """
        data: dict[str, object] = await self._transport.request(
            HttpMethod.POST,
            "/v1/training/start",
            json=config.model_dump(),
            response_model=dict,
        )
        return data