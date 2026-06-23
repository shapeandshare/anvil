# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Services list command — list all background services.

``ServicesListCommand`` fetches all running and available background services
via ``GET /v1/services``.
"""

from __future__ import annotations

from .._shared.abstract_command import AbstractCommand
from .._shared.http_method import HttpMethod


class ServicesListCommand(AbstractCommand):
    """List all services — ``GET /v1/services``."""

    async def execute(self) -> list[dict[str, object]]:
        """Fetch all background services from the server.

        Returns
        -------
        list[dict[str, object]]
            A list of service records as raw dictionaries.
        """
        data: list[dict[str, object]] = await self._transport.request(
            HttpMethod.GET, "/v1/services", response_model=list,
        )
        return data
