# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for DatasetUpdateCommand — PUT with optional body fields."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from anvil.client._shared.http_method import HttpMethod
from anvil.client.datasets.dataset_update_command import DatasetUpdateCommand


class TestDatasetUpdateCommand:
    """DatasetUpdateCommand: PUT /v1/datasets/{id}."""

    @pytest.mark.asyncio
    async def test_execute_calls_transport_with_put(self) -> None:
        transport = AsyncMock()
        transport.request = AsyncMock(return_value={"id": 1})
        cmd = DatasetUpdateCommand(transport)
        result = await cmd.execute(dataset_id=1)
        transport.request.assert_called_once()
        args, kwargs = transport.request.call_args
        assert args[0] == HttpMethod.PUT
        assert args[1] == "/v1/datasets/1"
        assert kwargs["json"] == {}

    @pytest.mark.asyncio
    async def test_execute_with_name(self) -> None:
        transport = AsyncMock()
        transport.request = AsyncMock(return_value={"id": 1})
        cmd = DatasetUpdateCommand(transport)
        result = await cmd.execute(dataset_id=1, name="new-name")
        _, kwargs = transport.request.call_args
        assert kwargs["json"] == {"name": "new-name"}

    @pytest.mark.asyncio
    async def test_execute_with_description(self) -> None:
        transport = AsyncMock()
        transport.request = AsyncMock(return_value={"id": 1})
        cmd = DatasetUpdateCommand(transport)
        result = await cmd.execute(dataset_id=1, description="new desc")
        _, kwargs = transport.request.call_args
        assert kwargs["json"] == {"description": "new desc"}

    @pytest.mark.asyncio
    async def test_execute_with_both(self) -> None:
        transport = AsyncMock()
        transport.request = AsyncMock(return_value={"id": 1})
        cmd = DatasetUpdateCommand(transport)
        result = await cmd.execute(dataset_id=1, name="n", description="d")
        _, kwargs = transport.request.call_args
        assert kwargs["json"] == {"name": "n", "description": "d"}

    @pytest.mark.asyncio
    async def test_execute_returns_transport_result(self) -> None:
        expected = {"id": 1, "name": "updated"}
        transport = AsyncMock()
        transport.request = AsyncMock(return_value=expected)
        cmd = DatasetUpdateCommand(transport)
        result = await cmd.execute(dataset_id=1)
        assert result == expected
