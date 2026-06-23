# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Experiment delete command — delete an experiment.

``ExperimentDeleteCommand`` removes an experiment from the server via
``DELETE /v1/experiments/{id}``.
"""

from __future__ import annotations

from .._shared.abstract_command import AbstractCommand
from .._shared.http_method import HttpMethod


class ExperimentDeleteCommand(AbstractCommand):
    """Delete an experiment — ``DELETE /v1/experiments/{id}``."""

    async def execute(self, experiment_id: str) -> dict[str, object]:
        """Delete an experiment from the server.

        Parameters
        ----------
        experiment_id : str
            The unique experiment identifier.

        Returns
        -------
        dict[str, object]
            A response payload confirming the deletion.
        """
        data: dict[str, object] = await self._transport.request(
            HttpMethod.DELETE,
            f"/v1/experiments/{experiment_id}",
            response_model=dict,
        )
        return data