# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Health detailed command — system metrics probe.

``HealthDetailedCommand`` retrieves detailed system metrics (CPU, memory,
disk, GPU) by issuing ``GET /v1/health/detailed``.
"""

from __future__ import annotations

from .._shared.abstract_command import AbstractCommand
from .._shared.http_method import HttpMethod


class HealthDetailedCommand(AbstractCommand):
    """Get detailed system metrics (CPU, memory, disk, GPU) — ``GET /v1/health/detailed``."""

    async def execute(self) -> dict[str, object]:
        """Retrieve detailed system health metrics.

        Returns
        -------
        dict[str, object]
            System metrics including CPU, memory, disk, and GPU information.
        """
        data: dict[str, object] = await self._transport.request(
            HttpMethod.GET, "/v1/health/detailed", response_model=dict,
        )
        return data