# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Services restart-all command — restart all background services.

``ServicesRestartAllCommand`` triggers a restart of all background services
on the server via ``POST /v1/services/restart-all``.
"""

from __future__ import annotations

from .._shared.abstract_command import AbstractCommand
from .._shared.http_method import HttpMethod


class ServicesRestartAllCommand(AbstractCommand):
    """Restart all services — ``POST /v1/services/restart-all``."""

    async def execute(self) -> dict[str, object]:
        """Trigger a restart of all background services.

        Returns
        -------
        dict[str, object]
            A response payload confirming the restart request.
        """
        data: dict[str, object] = await self._transport.request(
            HttpMethod.POST, "/v1/services/restart-all", response_model=dict,
        )
        return data
