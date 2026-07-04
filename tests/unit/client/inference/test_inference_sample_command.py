# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for InferenceSampleCommand — POST with body."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from anvil.client._shared.http_method import HttpMethod
from anvil.client.inference.inference_sample_command import InferenceSampleCommand


class TestInferenceSampleCommand:
    """InferenceSampleCommand: POST /v1/inference/sample."""

    @pytest.mark.asyncio
    async def test_execute_calls_transport_with_post(self) -> None:
        transport = AsyncMock()
        transport.request = AsyncMock(return_value={"text": "hello"})
        cmd = InferenceSampleCommand(transport)
        result = await cmd.execute(model_id="m1", prompt="Hello")
        transport.request.assert_called_once()
        args, kwargs = transport.request.call_args
        assert args[0] == HttpMethod.POST
        assert args[1] == "/v1/inference/sample"
        assert kwargs["json"] == {
            "model_id": "m1",
            "prompt": "Hello",
            "temperature": 0.7,
        }

    @pytest.mark.asyncio
    async def test_execute_with_custom_temperature(self) -> None:
        transport = AsyncMock()
        transport.request = AsyncMock(return_value={"text": "world"})
        cmd = InferenceSampleCommand(transport)
        result = await cmd.execute(model_id="m1", prompt="Hi", temperature=0.9)
        _, kwargs = transport.request.call_args
        assert kwargs["json"]["temperature"] == 0.9

    @pytest.mark.asyncio
    async def test_execute_returns_transport_result(self) -> None:
        expected = {"text": "generated output"}
        transport = AsyncMock()
        transport.request = AsyncMock(return_value=expected)
        cmd = InferenceSampleCommand(transport)
        result = await cmd.execute(model_id="m1", prompt="test")
        assert result == expected
