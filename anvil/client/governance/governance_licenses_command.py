# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Governance licenses command — list license metadata.

``GovernanceLicensesCommand`` retrieves available license metadata from the
server via ``GET /v1/governance/licenses``.
"""

from __future__ import annotations

from .._shared.abstract_command import AbstractCommand
from .._shared.http_method import HttpMethod


class GovernanceLicensesCommand(AbstractCommand):
    """List licenses — ``GET /v1/governance/licenses``."""

    async def execute(self) -> list[dict[str, object]]:
        """Retrieve all available license metadata.

        Returns
        -------
        list[dict[str, object]]
            A list of license record as raw dictionaries.
        """
        data: list[dict[str, object]] = await self._transport.request(
            HttpMethod.GET, "/v1/governance/licenses", response_model=list,
        )
        return data
