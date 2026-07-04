# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for DatasetGetCommand — GET with required ID param."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from anvil.client._shared.http_method import HttpMethod
from anvil.client.datasets.dataset_get_command import DatasetGetCommand


class TestDatasetGetCommand:
    """DatasetGetCommand: GET /v1/datasets/{id}."""

    @pytest.mark.asyncio
    async def test_execute_calls_transport_with_get(self) -> None:
        transport = AsyncMock()
        transport.request = AsyncMock(return_value={"id": 1})
        cmd = DatasetGetCommand(transport)
        result = await cmd.execute(dataset_id=42)
        transport.request.assert_called_once()
        args, _ = transport.request.call_args
        assert args[0] == HttpMethod.GET
        assert args[1] == "/v1/datasets/42"

    @pytest.mark.asyncio
    async def test_execute_returns_transport_result(self) -> None:
        expected = {"id": 42, "name": "test"}
        transport = AsyncMock()
        transport.request = AsyncMock(return_value=expected)
        cmd = DatasetGetCommand(transport)
        result = await cmd.execute(dataset_id=42)
        assert result == expected
