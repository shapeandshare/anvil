# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for RegistryGetCommand — GET with required model_id."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from anvil.client._shared.http_method import HttpMethod
from anvil.client.registry.registry_get_command import RegistryGetCommand


class TestRegistryGetCommand:
    """RegistryGetCommand: GET /v1/registry/models/{id}."""

    @pytest.mark.asyncio
    async def test_execute_calls_transport_with_get(self) -> None:
        transport = AsyncMock()
        transport.request = AsyncMock(return_value={"model_id": "m1"})
        cmd = RegistryGetCommand(transport)
        result = await cmd.execute(model_id="m1")
        transport.request.assert_called_once()
        args, _ = transport.request.call_args
        assert args[0] == HttpMethod.GET
        assert args[1] == "/v1/registry/models/m1"

    @pytest.mark.asyncio
    async def test_execute_returns_transport_result(self) -> None:
        expected = {"model_id": "m1", "name": "MyModel"}
        transport = AsyncMock()
        transport.request = AsyncMock(return_value=expected)
        cmd = RegistryGetCommand(transport)
        result = await cmd.execute(model_id="m1")
        assert result == expected
