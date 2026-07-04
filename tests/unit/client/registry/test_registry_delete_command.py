# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for RegistryDeleteCommand — DELETE with optional version."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from anvil.client._shared.http_method import HttpMethod
from anvil.client.registry.registry_delete_command import RegistryDeleteCommand


class TestRegistryDeleteCommand:
    """RegistryDeleteCommand: DELETE /v1/registry/models/{id}[/versions/{version}]."""

    @pytest.mark.asyncio
    async def test_execute_without_version(self) -> None:
        transport = AsyncMock()
        transport.request = AsyncMock(return_value={"deleted": True})
        cmd = RegistryDeleteCommand(transport)
        result = await cmd.execute(model_id="m1")
        transport.request.assert_called_once()
        args, _ = transport.request.call_args
        assert args[0] == HttpMethod.DELETE
        assert args[1] == "/v1/registry/models/m1"

    @pytest.mark.asyncio
    async def test_execute_with_version(self) -> None:
        transport = AsyncMock()
        transport.request = AsyncMock(return_value={"deleted": True})
        cmd = RegistryDeleteCommand(transport)
        result = await cmd.execute(model_id="m1", version="v2")
        args, _ = transport.request.call_args
        assert args[1] == "/v1/registry/models/m1/versions/v2"

    @pytest.mark.asyncio
    async def test_execute_returns_transport_result(self) -> None:
        expected = {"deleted": True}
        transport = AsyncMock()
        transport.request = AsyncMock(return_value=expected)
        cmd = RegistryDeleteCommand(transport)
        result = await cmd.execute(model_id="m1")
        assert result == expected
