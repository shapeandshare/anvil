# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for DatasetListCommand — GET with optional query param."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from anvil.client._shared.http_method import HttpMethod
from anvil.client.datasets.dataset_list_command import DatasetListCommand


class TestDatasetListCommand:
    """DatasetListCommand: GET /v1/datasets[?q=]."""

    @pytest.mark.asyncio
    async def test_execute_calls_transport_with_get(self) -> None:
        transport = AsyncMock()
        transport.request = AsyncMock(return_value=[])
        cmd = DatasetListCommand(transport)
        result = await cmd.execute()
        transport.request.assert_called_once()
        args, kwargs = transport.request.call_args
        assert args[0] == HttpMethod.GET
        assert args[1] == "/v1/datasets"
        assert kwargs.get("params") is None

    @pytest.mark.asyncio
    async def test_execute_with_query(self) -> None:
        transport = AsyncMock()
        transport.request = AsyncMock(return_value=[{"id": 1}])
        cmd = DatasetListCommand(transport)
        result = await cmd.execute(query="test")
        _, kwargs = transport.request.call_args
        assert kwargs.get("params") == {"q": "test"}

    @pytest.mark.asyncio
    async def test_execute_returns_transport_result(self) -> None:
        expected = [{"id": 1}, {"id": 2}]
        transport = AsyncMock()
        transport.request = AsyncMock(return_value=expected)
        cmd = DatasetListCommand(transport)
        result = await cmd.execute()
        assert result == expected
