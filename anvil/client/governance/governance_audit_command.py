# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Governance audit command — query audit trail.

``GovernanceAuditCommand`` retrieves audit log entries from the server
via ``GET /v1/governance/audit[?target_type=&target_id=&action_type=&limit=&offset=]``.
"""

from __future__ import annotations

from .._shared.abstract_command import AbstractCommand
from .._shared.http_method import HttpMethod


class GovernanceAuditCommand(AbstractCommand):
    """Query audit trail — ``GET /v1/governance/audit[?target_type=&target_id=&action_type=&limit=&offset=]``."""

    async def execute(
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
            Filter by action type (e.g. ``"create"``, ``"delete"``).
        limit : int | None, optional
            Maximum number of entries to return.
        offset : int | None, optional
            Number of entries to skip for pagination.

        Returns
        -------
        list[dict[str, object]]
            A list of audit log entry records.
        """
        params: dict[str, str] = {}
        if target_type is not None:
            params["target_type"] = target_type
        if target_id is not None:
            params["target_id"] = target_id
        if action_type is not None:
            params["action_type"] = action_type
        if limit is not None:
            params["limit"] = str(limit)
        if offset is not None:
            params["offset"] = str(offset)
        data: list[dict[str, object]] = await self._transport.request(
            HttpMethod.GET,
            "/v1/governance/audit",
            params=params or None,
            response_model=list,
        )
        return data
