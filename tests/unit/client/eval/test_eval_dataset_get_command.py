# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for EvalDatasetGetCommand — GET with required name param."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from anvil.client._shared.http_method import HttpMethod
from anvil.client.eval.eval_dataset_get_command import EvalDatasetGetCommand


class TestEvalDatasetGetCommand:
    """EvalDatasetGetCommand: GET /v1/eval-datasets/{name}."""

    @pytest.mark.asyncio
    async def test_execute_calls_transport_with_get(self) -> None:
        transport = AsyncMock()
        transport.request = AsyncMock(return_value={"name": "eval-ds"})
        cmd = EvalDatasetGetCommand(transport)
        result = await cmd.execute(name="eval-ds")
        transport.request.assert_called_once()
        args, _ = transport.request.call_args
        assert args[0] == HttpMethod.GET
        assert args[1] == "/v1/eval-datasets/eval-ds"

    @pytest.mark.asyncio
    async def test_execute_returns_transport_result(self) -> None:
        expected = {"name": "eval-ds", "source": "corpus1"}
        transport = AsyncMock()
        transport.request = AsyncMock(return_value=expected)
        cmd = EvalDatasetGetCommand(transport)
        result = await cmd.execute(name="eval-ds")
        assert result == expected
