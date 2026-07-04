# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for ModelsGetCommand — GET with required model name."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from anvil.client._shared.http_method import HttpMethod
from anvil.client.models.models_get_command import ModelsGetCommand


class TestModelsGetCommand:
    """ModelsGetCommand: GET /v1/models/{name}."""

    @pytest.mark.asyncio
    async def test_execute_calls_transport_with_get(self) -> None:
        transport = AsyncMock()
        transport.request = AsyncMock(return_value={"name": "test-model"})
        cmd = ModelsGetCommand(transport)
        result = await cmd.execute(name="test-model")
        transport.request.assert_called_once()
        args, _ = transport.request.call_args
        assert args[0] == HttpMethod.GET
        assert args[1] == "/v1/models/test-model"

    @pytest.mark.asyncio
    async def test_execute_returns_transport_result(self) -> None:
        expected = {"name": "test-model", "kind": "external"}
        transport = AsyncMock()
        transport.request = AsyncMock(return_value=expected)
        cmd = ModelsGetCommand(transport)
        result = await cmd.execute(name="test-model")
        assert result == expected
