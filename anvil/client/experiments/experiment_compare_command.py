# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Experiment compare command — compare multiple experiments.

``ExperimentCompareCommand`` fetches side-by-side comparison data for two or
more experiments via ``GET /v1/experiments/compare?id=...``.
"""

from __future__ import annotations

from .._shared.abstract_command import AbstractCommand
from .._shared.http_method import HttpMethod


class ExperimentCompareCommand(AbstractCommand):
    """Compare multiple experiments — ``GET /v1/experiments/compare?id=...``."""

    async def execute(self, *ids: str) -> dict[str, object]:
        """Fetch comparison data for the given experiment identifiers.

        Parameters
        ----------
        *ids : str
            One or more experiment identifiers to compare. At least one ID
            is required.

        Returns
        -------
        dict[str, object]
            Comparison data keyed by experiment identifier.
        """
        params = {"id": list(ids)}
        data: dict[str, object] = await self._transport.request(
            HttpMethod.GET,
            "/v1/experiments/compare",
            params=params,
            response_model=dict,
        )
        return data