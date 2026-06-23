# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Governance client — domain aggregator for audit and license operations.

``GovernanceClient`` provides a single entry point for all governance
operations: audit trail queries and license metadata retrieval. It delegates
each operation to its corresponding command class.
"""

from __future__ import annotations

from .._shared.transport import Transport
from .governance_audit_command import GovernanceAuditCommand
from .governance_licenses_command import GovernanceLicensesCommand


class GovernanceClient:
    """Governance operations.

    Aggregates all governance commands behind a single facade. Each public
    method maps to one server API operation.

    Parameters
    ----------
    transport : Transport
        The shared SDK transport instance.
    """

    def __init__(self, transport: Transport) -> None:
        self._audit_cmd = GovernanceAuditCommand(transport)
        self._licenses_cmd = GovernanceLicensesCommand(transport)

    async def audit(
        self,
        target_type: str | None = None,
        target_id: str | None = None,
        action_type: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[dict[str, object]]:
        """Retrieve audit log entries.

        Parameters
        ----------
        target_type : str | None, optional
            Filter by target resource type.
        target_id : str | None, optional
            Filter by target resource identifier.
        action_type : str | None, optional
            Filter by action type.
        limit : int | None, optional
            Maximum number of entries to return.
        offset : int | None, optional
            Number of entries to skip for pagination.

        Returns
        -------
        list[dict[str, object]]
            A list of audit log entry records.
        """
        return await self._audit_cmd.execute(
            target_type=target_type,
            target_id=target_id,
            action_type=action_type,
            limit=limit,
            offset=offset,
        )

    async def licenses(self) -> list[dict[str, object]]:
        """List all available license metadata.

        Returns
        -------
        list[dict[str, object]]
            A list of license records.
        """
        return await self._licenses_cmd.execute()
