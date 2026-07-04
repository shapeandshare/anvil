# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for GovernanceLicensesCommand — no-arg GET returning list."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from anvil.client._shared.http_method import HttpMethod
from anvil.client.governance.governance_licenses_command import (
    GovernanceLicensesCommand,
)


class TestGovernanceLicensesCommand:
    """GovernanceLicensesCommand: GET /v1/governance/licenses → list."""

    @pytest.mark.asyncio
    async def test_execute_calls_transport_with_get(self) -> None:
        transport = AsyncMock()
        transport.request = AsyncMock(return_value=[])
        cmd = GovernanceLicensesCommand(transport)
        result = await cmd.execute()
        transport.request.assert_called_once()
        args, _ = transport.request.call_args
        assert args[0] == HttpMethod.GET
        assert args[1] == "/v1/governance/licenses"

    @pytest.mark.asyncio
    async def test_execute_returns_transport_result(self) -> None:
        expected = [{"name": "MIT"}, {"name": "Apache-2.0"}]
        transport = AsyncMock()
        transport.request = AsyncMock(return_value=expected)
        cmd = GovernanceLicensesCommand(transport)
        result = await cmd.execute()
        assert result == expected
