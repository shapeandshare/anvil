# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Dataset list command — list all datasets.

``DatasetListCommand`` fetches all datasets from the server via
``GET /v1/datasets``, with an optional search query parameter.
"""

from __future__ import annotations

from .._shared.abstract_command import AbstractCommand
from .._shared.http_method import HttpMethod


class DatasetListCommand(AbstractCommand):
    """List all datasets — ``GET /v1/datasets[?q=]``."""

    async def execute(self, query: str | None = None) -> list[dict[str, object]]:
        """Fetch all datasets from the server.

        Parameters
        ----------
        query : str | None, optional
            Optional search query to filter datasets.

        Returns
        -------
        list[dict[str, object]]
            A list of dataset records as raw dictionaries.
        """
        params = {"q": query} if query else None
        data: list[dict[str, object]] = await self._transport.request(
            HttpMethod.GET, "/v1/datasets", params=params, response_model=list,
        )
        return data
