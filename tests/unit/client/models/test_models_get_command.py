# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for ModelsGetCommand — GET with required model_id."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from anvil.client._shared.http_method import HttpMethod
from anvil.client.models.models_get_command import ModelsGetCommand


class TestModelsGetCommand:
    """ModelsGetCommand: GET /v1/models/external/{model_id}."""

    @pytest.mark.asyncio
    async def test_execute_calls_transport_with_get(self) -> None:
        transport = AsyncMock()
        transport.request = AsyncMock(return_value={"id": 1})
        cmd = ModelsGetCommand(transport)
        result = await cmd.execute(model_id=42)
        transport.request.assert_called_once()
        args, _ = transport.request.call_args
        assert args[0] == HttpMethod.GET
        assert args[1] == "/v1/models/external/42"

    @pytest.mark.asyncio
    async def test_execute_returns_transport_result(self) -> None:
        expected = {"id": 1, "source": "huggingface"}
        transport = AsyncMock()
        transport.request = AsyncMock(return_value=expected)
        cmd = ModelsGetCommand(transport)
        result = await cmd.execute(model_id=1)
        assert result == expected
