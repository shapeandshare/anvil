# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Services logs command — tail service logs.

``ServicesLogsCommand`` retrieves recent log lines from a specific service
via ``GET /v1/services/logs/{name}[?lines=]``.
"""

from __future__ import annotations

from .._shared.abstract_command import AbstractCommand
from .._shared.http_method import HttpMethod


class ServicesLogsCommand(AbstractCommand):
    """Tail service logs — ``GET /v1/services/logs/{name}[?lines=]``."""

    async def execute(
        self, name: str, lines: int | None = None,
    ) -> list[str]:
        """Retrieve recent log lines from a service.

        Parameters
        ----------
        name : str
            The service name.
        lines : int | None, optional
            Number of recent log lines to retrieve. ``None`` uses the
            server default.

        Returns
        -------
        list[str]
            A list of log line strings.
        """
        params = {"lines": str(lines)} if lines else None
        data: list[str] = await self._transport.request(
            HttpMethod.GET,
            f"/v1/services/logs/{name}",
            params=params,
            response_model=list,
        )
        return data
