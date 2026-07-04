# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for GovernanceAuditCommand — GET with many optional filters."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from anvil.client._shared.http_method import HttpMethod
from anvil.client.governance.governance_audit_command import GovernanceAuditCommand


class TestGovernanceAuditCommand:
    """GovernanceAuditCommand: GET /v1/governance/audit[?filters]."""

    @pytest.mark.asyncio
    async def test_execute_without_filters(self) -> None:
        transport = AsyncMock()
        transport.request = AsyncMock(return_value=[])
        cmd = GovernanceAuditCommand(transport)
        result = await cmd.execute()
        transport.request.assert_called_once()
        args, kwargs = transport.request.call_args
        assert args[0] == HttpMethod.GET
        assert args[1] == "/v1/governance/audit"
        assert kwargs.get("params") is None

    @pytest.mark.asyncio
    async def test_execute_with_target_type(self) -> None:
        transport = AsyncMock()
        transport.request = AsyncMock(return_value=[])
        cmd = GovernanceAuditCommand(transport)
        result = await cmd.execute(target_type="dataset")
        _, kwargs = transport.request.call_args
        assert kwargs["params"]["target_type"] == "dataset"

    @pytest.mark.asyncio
    async def test_execute_with_all_filters(self) -> None:
        transport = AsyncMock()
        transport.request = AsyncMock(return_value=[])
        cmd = GovernanceAuditCommand(transport)
        result = await cmd.execute(
            target_type="model",
            target_id="m1",
            action_type="delete",
            limit=10,
            offset=0,
        )
        _, kwargs = transport.request.call_args
        params = kwargs["params"]
        assert params["target_type"] == "model"
        assert params["target_id"] == "m1"
        assert params["action_type"] == "delete"
        assert params["limit"] == "10"
        assert params["offset"] == "0"

    @pytest.mark.asyncio
    async def test_execute_returns_transport_result(self) -> None:
        expected = [{"id": 1, "action": "create"}]
        transport = AsyncMock()
        transport.request = AsyncMock(return_value=expected)
        cmd = GovernanceAuditCommand(transport)
        result = await cmd.execute()
        assert result == expected
