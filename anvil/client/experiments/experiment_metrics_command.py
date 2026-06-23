# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Experiment metrics command — fetch experiment metrics.

``ExperimentMetricsCommand`` retrieves metrics for a single experiment via
``GET /v1/experiments/{id}/metrics``.
"""

from __future__ import annotations

from .._shared.abstract_command import AbstractCommand
from .._shared.http_method import HttpMethod


class ExperimentMetricsCommand(AbstractCommand):
    """Get experiment metrics — ``GET /v1/experiments/{id}/metrics``."""

    async def execute(self, experiment_id: str) -> dict[str, object]:
        """Fetch metrics for the given experiment.

        Parameters
        ----------
        experiment_id : str
            The unique experiment identifier.

        Returns
        -------
        dict[str, object]
            Metrics data keyed by metric name.
        """
        data: dict[str, object] = await self._transport.request(
            HttpMethod.GET,
            f"/v1/experiments/{experiment_id}/metrics",
            response_model=dict,
        )
        return data
