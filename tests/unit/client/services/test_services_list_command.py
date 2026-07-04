# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for ServicesListCommand — no-arg GET returning list."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from anvil.client._shared.http_method import HttpMethod
from anvil.client.services.services_list_command import ServicesListCommand


class TestServicesListCommand:
    """ServicesListCommand: GET /v1/services → list."""

    @pytest.mark.asyncio
    async def test_execute_calls_transport_with_get(self) -> None:
        transport = AsyncMock()
        transport.request = AsyncMock(return_value=[{"name": "web"}])
        cmd = ServicesListCommand(transport)
        result = await cmd.execute()
        transport.request.assert_called_once()
        args, _ = transport.request.call_args
        assert args[0] == HttpMethod.GET
        assert args[1] == "/v1/services"

    @pytest.mark.asyncio
    async def test_execute_returns_transport_result(self) -> None:
        expected = [{"name": "web"}, {"name": "mlflow"}]
        transport = AsyncMock()
        transport.request = AsyncMock(return_value=expected)
        cmd = ServicesListCommand(transport)
        result = await cmd.execute()
        assert result == expected
