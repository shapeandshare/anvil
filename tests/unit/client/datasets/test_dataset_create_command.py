# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for DatasetCreateCommand — POST with body + optional params."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from anvil.client._shared.http_method import HttpMethod
from anvil.client.datasets.dataset_create_command import DatasetCreateCommand


class TestDatasetCreateCommand:
    """DatasetCreateCommand: POST /v1/datasets."""

    @pytest.mark.asyncio
    async def test_execute_calls_transport_with_post(self) -> None:
        transport = AsyncMock()
        transport.request = AsyncMock(return_value={"id": 1})
        cmd = DatasetCreateCommand(transport)
        result = await cmd.execute(name="test-ds")
        transport.request.assert_called_once()
        args, kwargs = transport.request.call_args
        assert args[0] == HttpMethod.POST
        assert args[1] == "/v1/datasets"
        assert kwargs["json"] == {"name": "test-ds"}

    @pytest.mark.asyncio
    async def test_execute_with_description(self) -> None:
        transport = AsyncMock()
        transport.request = AsyncMock(return_value={"id": 2})
        cmd = DatasetCreateCommand(transport)
        result = await cmd.execute(name="test", description="A test dataset")
        _, kwargs = transport.request.call_args
        assert kwargs["json"] == {"name": "test", "description": "A test dataset"}

    @pytest.mark.asyncio
    async def test_execute_returns_transport_result(self) -> None:
        expected = {"id": 1, "name": "test"}
        transport = AsyncMock()
        transport.request = AsyncMock(return_value=expected)
        cmd = DatasetCreateCommand(transport)
        result = await cmd.execute(name="test")
        assert result == expected
