# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for ServicesRestartAllCommand — no-arg POST returning dict."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from anvil.client._shared.http_method import HttpMethod
from anvil.client.services.services_restart_all_command import ServicesRestartAllCommand


class TestServicesRestartAllCommand:
    """ServicesRestartAllCommand: POST /v1/services/restart-all → dict."""

    @pytest.mark.asyncio
    async def test_execute_calls_transport_with_post(self) -> None:
        transport = AsyncMock()
        transport.request = AsyncMock(return_value={"status": "restarting"})
        cmd = ServicesRestartAllCommand(transport)
        result = await cmd.execute()
        transport.request.assert_called_once()
        args, _ = transport.request.call_args
        assert args[0] == HttpMethod.POST
        assert args[1] == "/v1/services/restart-all"

    @pytest.mark.asyncio
    async def test_execute_returns_transport_result(self) -> None:
        expected = {"status": "restarting"}
        transport = AsyncMock()
        transport.request = AsyncMock(return_value=expected)
        cmd = ServicesRestartAllCommand(transport)
        result = await cmd.execute()
        assert result == expected
