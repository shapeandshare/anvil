# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for DatasetDeleteCommand — DELETE with optional force param."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from anvil.client._shared.http_method import HttpMethod
from anvil.client.datasets.dataset_delete_command import DatasetDeleteCommand


class TestDatasetDeleteCommand:
    """DatasetDeleteCommand: DELETE /v1/datasets/{id}[?force=]."""

    @pytest.mark.asyncio
    async def test_execute_calls_transport_with_delete(self) -> None:
        transport = AsyncMock()
        transport.request = AsyncMock(return_value={"deleted": True})
        cmd = DatasetDeleteCommand(transport)
        result = await cmd.execute(dataset_id=1)
        transport.request.assert_called_once()
        args, kwargs = transport.request.call_args
        assert args[0] == HttpMethod.DELETE
        assert args[1] == "/v1/datasets/1"
        assert kwargs.get("params") is None

    @pytest.mark.asyncio
    async def test_execute_with_force(self) -> None:
        transport = AsyncMock()
        transport.request = AsyncMock(return_value={"deleted": True})
        cmd = DatasetDeleteCommand(transport)
        result = await cmd.execute(dataset_id=1, force=True)
        _, kwargs = transport.request.call_args
        assert kwargs.get("params") == {"force": "true"}

    @pytest.mark.asyncio
    async def test_execute_returns_transport_result(self) -> None:
        expected = {"deleted": True}
        transport = AsyncMock()
        transport.request = AsyncMock(return_value=expected)
        cmd = DatasetDeleteCommand(transport)
        result = await cmd.execute(dataset_id=1)
        assert result == expected
