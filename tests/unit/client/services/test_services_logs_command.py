# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for ServicesLogsCommand — GET with required + optional params."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from anvil.client._shared.http_method import HttpMethod
from anvil.client.services.services_logs_command import ServicesLogsCommand


class TestServicesLogsCommand:
    """ServicesLogsCommand: GET /v1/services/logs/{name}[?lines=]."""

    @pytest.mark.asyncio
    async def test_execute_calls_transport_with_get(self) -> None:
        transport = AsyncMock()
        transport.request = AsyncMock(return_value=["log line 1"])
        cmd = ServicesLogsCommand(transport)
        result = await cmd.execute(name="web")
        transport.request.assert_called_once()
        args, kwargs = transport.request.call_args
        assert args[0] == HttpMethod.GET
        assert args[1] == "/v1/services/logs/web"
        assert kwargs.get("params") is None

    @pytest.mark.asyncio
    async def test_execute_with_lines_param(self) -> None:
        transport = AsyncMock()
        transport.request = AsyncMock(return_value=["line1", "line2"])
        cmd = ServicesLogsCommand(transport)
        result = await cmd.execute(name="mlflow", lines=50)
        _, kwargs = transport.request.call_args
        assert kwargs.get("params") == {"lines": "50"}

    @pytest.mark.asyncio
    async def test_execute_returns_transport_result(self) -> None:
        expected = ["line1", "line2", "line3"]
        transport = AsyncMock()
        transport.request = AsyncMock(return_value=expected)
        cmd = ServicesLogsCommand(transport)
        result = await cmd.execute(name="web")
        assert result == expected
