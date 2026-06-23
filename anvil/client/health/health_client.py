# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Health client — domain aggregator for server health operations.

``HealthClient`` provides ``get()`` for liveness and ``detailed()`` for
system metrics, delegating to ``HealthGetCommand`` and
``HealthDetailedCommand`` respectively.
"""

from __future__ import annotations

from .._shared.transport import Transport
from .health_detailed_command import HealthDetailedCommand
from .health_get_command import HealthGetCommand


class HealthClient:
    """Server health check operations.

    Provides ``get()`` for liveness and ``detailed()`` for system metrics.

    Parameters
    ----------
    transport : Transport
        The shared SDK transport instance.
    """

    def __init__(self, transport: Transport) -> None:
        self._get = HealthGetCommand(transport)
        self._detailed = HealthDetailedCommand(transport)

    async def get(self) -> dict[str, object]:
        """Check server liveness.

        Returns
        -------
        dict[str, object]
            Basic status information.
        """
        return await self._get.execute()

    async def detailed(self) -> dict[str, object]:
        """Get detailed system metrics.

        Returns
        -------
        dict[str, object]
            System metrics (CPU, memory, disk, GPU).
        """
        return await self._detailed.execute()