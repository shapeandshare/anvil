# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Experiment get command — fetch a single experiment.

``ExperimentGetCommand`` retrieves a single experiment by its identifier via
``GET /v1/experiments/{id}``.
"""

from __future__ import annotations

from .._shared.abstract_command import AbstractCommand
from .._shared.http_method import HttpMethod


class ExperimentGetCommand(AbstractCommand):
    """Get a single experiment — ``GET /v1/experiments/{id}``."""

    async def execute(self, experiment_id: str) -> dict[str, object]:
        """Fetch a single experiment by its identifier.

        Parameters
        ----------
        experiment_id : str
            The unique experiment identifier.

        Returns
        -------
        dict[str, object]
            The experiment record.
        """
        data: dict[str, object] = await self._transport.request(
            HttpMethod.GET,
            f"/v1/experiments/{experiment_id}",
            response_model=dict,
        )
        return data