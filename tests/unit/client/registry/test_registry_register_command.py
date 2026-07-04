# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for RegistryRegisterCommand — POST with experiment_id body."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from anvil.client._shared.http_method import HttpMethod
from anvil.client.registry.registry_register_command import RegistryRegisterCommand


class TestRegistryRegisterCommand:
    """RegistryRegisterCommand: POST /v1/registry/models."""

    @pytest.mark.asyncio
    async def test_execute_calls_transport_with_post(self) -> None:
        transport = AsyncMock()
        transport.request = AsyncMock(return_value={"model_id": "m1"})
        cmd = RegistryRegisterCommand(transport)
        result = await cmd.execute(experiment_id="exp1")
        transport.request.assert_called_once()
        args, kwargs = transport.request.call_args
        assert args[0] == HttpMethod.POST
        assert args[1] == "/v1/registry/models"
        assert kwargs["json"] == {"experiment_id": "exp1"}

    @pytest.mark.asyncio
    async def test_execute_returns_transport_result(self) -> None:
        expected = {"model_id": "m1", "name": "Registered"}
        transport = AsyncMock()
        transport.request = AsyncMock(return_value=expected)
        cmd = RegistryRegisterCommand(transport)
        result = await cmd.execute(experiment_id="exp1")
        assert result == expected
