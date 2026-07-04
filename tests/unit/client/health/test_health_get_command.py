# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for HealthGetCommand — no-arg GET returning dict."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from anvil.client._shared.http_method import HttpMethod
from anvil.client.health.health_get_command import HealthGetCommand


class TestHealthGetCommand:
    """HealthGetCommand: GET /v1/health → dict."""

    @pytest.mark.asyncio
    async def test_execute_calls_transport_with_get(self) -> None:
        transport = AsyncMock()
        transport.request = AsyncMock(return_value={"status": "ok"})
        cmd = HealthGetCommand(transport)
        result = await cmd.execute()
        transport.request.assert_called_once()
        args, _ = transport.request.call_args
        assert args[0] == HttpMethod.GET
        assert args[1] == "/v1/health"

    @pytest.mark.asyncio
    async def test_execute_returns_transport_result(self) -> None:
        expected = {"status": "ok", "version": "1.0"}
        transport = AsyncMock()
        transport.request = AsyncMock(return_value=expected)
        cmd = HealthGetCommand(transport)
        result = await cmd.execute()
        assert result == expected
