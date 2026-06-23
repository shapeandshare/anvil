# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Health GET command — server liveness probe.

``HealthGetCommand`` checks whether the anvil server is alive and responding
by issuing ``GET /v1/health``. This endpoint is auth-exempt (FR-010).
"""

from __future__ import annotations

from .._shared.abstract_command import AbstractCommand
from .._shared.http_method import HttpMethod


class HealthGetCommand(AbstractCommand):
    """Check server liveness — ``GET /v1/health``.

    Returns a dict with basic status. This endpoint is auth-exempt (FR-010).
    """

    async def execute(self) -> dict[str, object]:
        """Perform a liveness check against the server.

        Returns
        -------
        dict[str, object]
            Basic status information from the server.
        """
        data: dict[str, object] = await self._transport.request(
            HttpMethod.GET, "/v1/health", response_model=dict,
        )
        return data