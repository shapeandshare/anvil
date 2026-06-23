# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Services client — domain aggregator for service lifecycle operations.

``ServicesClient`` provides a single entry point for all service management
operations: list, logs, and restart-all. It delegates each operation to its
corresponding command class.
"""

from __future__ import annotations

import builtins

from .._shared.transport import Transport
from .services_list_command import ServicesListCommand
from .services_logs_command import ServicesLogsCommand
from .services_restart_all_command import ServicesRestartAllCommand


class ServicesClient:
    """Service lifecycle operations.

    Aggregates all service commands behind a single facade. Each public method
    maps to one server API operation.

    Parameters
    ----------
    transport : Transport
        The shared SDK transport instance.
    """

    def __init__(self, transport: Transport) -> None:
        self._list_cmd = ServicesListCommand(transport)
        self._logs_cmd = ServicesLogsCommand(transport)
        self._restart_all_cmd = ServicesRestartAllCommand(transport)

    async def list(self) -> builtins.list[dict[str, object]]:
        """List all background services.

        Returns
        -------
        List[dict[str, object]]
            A list of service records.
        """
        return await self._list_cmd.execute()

    async def logs(
        self,
        name: str,
        lines: int | None = None,
    ) -> builtins.list[str]:
        """Retrieve recent log lines from a service.

        Parameters
        ----------
        name : str
            The service name.
        lines : int | None, optional
            Number of recent log lines to retrieve.

        Returns
        -------
        List[str]
            A list of log line strings.
        """
        return await self._logs_cmd.execute(name, lines=lines)

    async def restart_all(self) -> dict[str, object]:
        """Restart all background services.

        Returns
        -------
        dict[str, object]
            A response payload confirming the restart request.
        """
        return await self._restart_all_cmd.execute()
