# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for InferenceModelsCommand — no-arg GET returning dict."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from anvil.client._shared.http_method import HttpMethod
from anvil.client.inference.inference_models_command import InferenceModelsCommand


class TestInferenceModelsCommand:
    """InferenceModelsCommand: GET /v1/inference/models → dict."""

    @pytest.mark.asyncio
    async def test_execute_calls_transport_with_get(self) -> None:
        transport = AsyncMock()
        transport.request = AsyncMock(return_value={"models": []})
        cmd = InferenceModelsCommand(transport)
        result = await cmd.execute()
        transport.request.assert_called_once()
        args, _ = transport.request.call_args
        assert args[0] == HttpMethod.GET
        assert args[1] == "/v1/inference/models"

    @pytest.mark.asyncio
    async def test_execute_returns_transport_result(self) -> None:
        expected = {"models": [{"id": "m1", "name": "default"}]}
        transport = AsyncMock()
        transport.request = AsyncMock(return_value=expected)
        cmd = InferenceModelsCommand(transport)
        result = await cmd.execute()
        assert result == expected
