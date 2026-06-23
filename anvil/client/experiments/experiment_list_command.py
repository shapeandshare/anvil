# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Experiment list command — list all experiments.

``ExperimentListCommand`` fetches all experiments from the server via
``GET /v1/experiments``.
"""

from __future__ import annotations

from .._shared.abstract_command import AbstractCommand
from .._shared.http_method import HttpMethod


class ExperimentListCommand(AbstractCommand):
    """List all experiments — ``GET /v1/experiments``."""

    async def execute(self) -> list[dict[str, object]]:
        """Fetch all experiments from the server.

        Returns
        -------
        list[dict[str, object]]
            A list of experiment records as raw dictionaries.
        """
        data: list[dict[str, object]] = await self._transport.request(
            HttpMethod.GET,
            "/v1/experiments",
            response_model=list,
        )
        return data
