# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for EvalPerplexityCommand — POST with required + optional params."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from anvil.client._shared.http_method import HttpMethod
from anvil.client.eval.eval_perplexity_command import EvalPerplexityCommand


class TestEvalPerplexityCommand:
    """EvalPerplexityCommand: POST /v1/eval/perplexity."""

    @pytest.mark.asyncio
    async def test_execute_calls_transport_with_post(self) -> None:
        transport = AsyncMock()
        transport.request = AsyncMock(return_value={"perplexity": 5.0})
        cmd = EvalPerplexityCommand(transport)
        result = await cmd.execute(model_id="m1", dataset_name="eval-ds")
        transport.request.assert_called_once()
        args, kwargs = transport.request.call_args
        assert args[0] == HttpMethod.POST
        assert args[1] == "/v1/eval/perplexity"
        assert kwargs["json"] == {
            "model_id": "m1",
            "dataset_name": "eval-ds",
        }

    @pytest.mark.asyncio
    async def test_execute_with_max_samples(self) -> None:
        transport = AsyncMock()
        transport.request = AsyncMock(return_value={"perplexity": 3.0})
        cmd = EvalPerplexityCommand(transport)
        result = await cmd.execute(
            model_id="m1", dataset_name="eval-ds", max_samples=100
        )
        _, kwargs = transport.request.call_args
        assert kwargs["json"]["max_samples"] == 100

    @pytest.mark.asyncio
    async def test_execute_without_max_samples(self) -> None:
        transport = AsyncMock()
        transport.request = AsyncMock(return_value={"perplexity": 3.0})
        cmd = EvalPerplexityCommand(transport)
        result = await cmd.execute(model_id="m1", dataset_name="eval-ds")
        _, kwargs = transport.request.call_args
        assert "max_samples" not in kwargs["json"]

    @pytest.mark.asyncio
    async def test_execute_returns_transport_result(self) -> None:
        expected = {"perplexity": 4.5}
        transport = AsyncMock()
        transport.request = AsyncMock(return_value=expected)
        cmd = EvalPerplexityCommand(transport)
        result = await cmd.execute(model_id="m1", dataset_name="eval-ds")
        assert result == expected
