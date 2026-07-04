# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for ModelsImportCommand — POST with body + optional params."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from anvil.client._shared.http_method import HttpMethod
from anvil.client.models.models_import_command import ModelsImportCommand


class TestModelsImportCommand:
    """ModelsImportCommand: POST /v1/models/import."""

    @pytest.mark.asyncio
    async def test_execute_calls_transport_with_post(self) -> None:
        transport = AsyncMock()
        transport.request = AsyncMock(return_value={"job_id": 1})
        cmd = ModelsImportCommand(transport)
        result = await cmd.execute(source="huggingface", identifier="org/model")
        transport.request.assert_called_once()
        args, kwargs = transport.request.call_args
        assert args[0] == HttpMethod.POST
        assert args[1] == "/v1/models/import"
        assert kwargs["json"] == {
            "source": "huggingface",
            "identifier": "org/model",
            "revision": "main",
        }

    @pytest.mark.asyncio
    async def test_execute_with_custom_revision(self) -> None:
        transport = AsyncMock()
        transport.request = AsyncMock(return_value={"job_id": 1})
        cmd = ModelsImportCommand(transport)
        result = await cmd.execute(
            source="huggingface", identifier="org/model", revision="v2"
        )
        _, kwargs = transport.request.call_args
        assert kwargs["json"]["revision"] == "v2"

    @pytest.mark.asyncio
    async def test_execute_with_name(self) -> None:
        transport = AsyncMock()
        transport.request = AsyncMock(return_value={"job_id": 1})
        cmd = ModelsImportCommand(transport)
        result = await cmd.execute(
            source="local", identifier="/path/to/model", name="MyModel"
        )
        _, kwargs = transport.request.call_args
        assert kwargs["json"]["name"] == "MyModel"

    @pytest.mark.asyncio
    async def test_execute_without_name(self) -> None:
        transport = AsyncMock()
        transport.request = AsyncMock(return_value={"job_id": 1})
        cmd = ModelsImportCommand(transport)
        result = await cmd.execute(source="local", identifier="/p")
        _, kwargs = transport.request.call_args
        assert "name" not in kwargs["json"]

    @pytest.mark.asyncio
    async def test_execute_returns_transport_result(self) -> None:
        expected = {"job_id": 1, "status": "pending"}
        transport = AsyncMock()
        transport.request = AsyncMock(return_value=expected)
        cmd = ModelsImportCommand(transport)
        result = await cmd.execute(source="huggingface", identifier="org/m")
        assert result == expected
