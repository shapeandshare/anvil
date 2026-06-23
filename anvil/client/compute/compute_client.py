# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Compute client — domain aggregator for compute backend operations.

``ComputeClient`` provides a single entry point for discovering available
compute backends on the anvil server.
"""

from __future__ import annotations

from .._shared.transport import Transport
from .compute_backends_command import ComputeBackendsCommand


class ComputeClient:
    """Compute backend operations.

    Aggregates all compute commands behind a single facade. Each public method
    maps to one server API operation.

    Parameters
    ----------
    transport : Transport
        The shared SDK transport instance.
    """

    def __init__(self, transport: Transport) -> None:
        self._backends_cmd = ComputeBackendsCommand(transport)

    async def backends(self) -> list[dict[str, object]]:
        """List all available compute backends.

        Returns
        -------
        list[dict[str, object]]
            A list of compute backend records.
        """
        return await self._backends_cmd.execute()
