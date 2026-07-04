# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for RegistryListCommand — GET with optional search param."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from anvil.client._shared.http_method import HttpMethod
from anvil.client.registry.registry_list_command import RegistryListCommand


class TestRegistryListCommand:
    """RegistryListCommand: GET /v1/registry/models[?search=]."""

    @pytest.mark.asyncio
    async def test_execute_without_search(self) -> None:
        transport = AsyncMock()
        transport.request = AsyncMock(return_value={"models": []})
        cmd = RegistryListCommand(transport)
        result = await cmd.execute()
        transport.request.assert_called_once()
        args, kwargs = transport.request.call_args
        assert args[0] == HttpMethod.GET
        assert args[1] == "/v1/registry/models"
        assert kwargs.get("params") is None

    @pytest.mark.asyncio
    async def test_execute_with_search(self) -> None:
        transport = AsyncMock()
        transport.request = AsyncMock(return_value={"models": [{"model_id": "m1"}]})
        cmd = RegistryListCommand(transport)
        result = await cmd.execute(search="test")
        _, kwargs = transport.request.call_args
        assert kwargs["params"] == {"search": "test"}

    @pytest.mark.asyncio
    async def test_execute_extracts_models_list(self) -> None:
        transport = AsyncMock()
        transport.request = AsyncMock(
            return_value={"models": [{"model_id": "m1", "name": "M1"}]}
        )
        cmd = RegistryListCommand(transport)
        result = await cmd.execute()
        assert result == [{"model_id": "m1", "name": "M1"}]

    @pytest.mark.asyncio
    async def test_execute_handles_missing_models_key(self) -> None:
        transport = AsyncMock()
        transport.request = AsyncMock(return_value={})
        cmd = RegistryListCommand(transport)
        result = await cmd.execute()
        assert result == []
