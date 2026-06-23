# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Experiment artifacts command — list run artifacts.

``ExperimentArtifactsCommand`` retrieves the artifact listing for a specific
run within an experiment via ``GET /v1/experiments/{eid}/runs/{rid}/artifacts``.
"""

from __future__ import annotations

from .._shared.abstract_command import AbstractCommand
from .._shared.http_method import HttpMethod


class ExperimentArtifactsCommand(AbstractCommand):
    """List run artifacts — ``GET /v1/experiments/{eid}/runs/{rid}/artifacts``."""

    async def execute(
        self,
        experiment_id: str,
        run_id: str,
    ) -> dict[str, object]:
        """Fetch the artifact listing for a specific run.

        Parameters
        ----------
        experiment_id : str
            The experiment identifier.
        run_id : str
            The run identifier within the experiment.

        Returns
        -------
        dict[str, object]
            Artifact listing data.
        """
        data: dict[str, object] = await self._transport.request(
            HttpMethod.GET,
            f"/v1/experiments/{experiment_id}/runs/{run_id}/artifacts",
            response_model=dict,
        )
        return data
