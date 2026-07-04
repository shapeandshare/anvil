# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for EvalDatasetCreateCommand — POST with body + optional description."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from anvil.client._shared.http_method import HttpMethod
from anvil.client.eval.eval_dataset_create_command import EvalDatasetCreateCommand


class TestEvalDatasetCreateCommand:
    """EvalDatasetCreateCommand: POST /v1/eval-datasets."""

    @pytest.mark.asyncio
    async def test_execute_calls_transport_with_post(self) -> None:
        transport = AsyncMock()
        transport.request = AsyncMock(return_value={"id": 1})
        cmd = EvalDatasetCreateCommand(transport)
        result = await cmd.execute(name="eval-ds", source="corpus1")
        transport.request.assert_called_once()
        args, kwargs = transport.request.call_args
        assert args[0] == HttpMethod.POST
        assert args[1] == "/v1/eval-datasets"
        assert kwargs["json"] == {"name": "eval-ds", "source": "corpus1"}

    @pytest.mark.asyncio
    async def test_execute_with_description(self) -> None:
        transport = AsyncMock()
        transport.request = AsyncMock(return_value={"id": 2})
        cmd = EvalDatasetCreateCommand(transport)
        result = await cmd.execute(
            name="ds", source="corpus1", description="My eval ds"
        )
        _, kwargs = transport.request.call_args
        assert kwargs["json"] == {
            "name": "ds",
            "source": "corpus1",
            "description": "My eval ds",
        }

    @pytest.mark.asyncio
    async def test_execute_returns_transport_result(self) -> None:
        expected = {"id": 1, "name": "eval-ds"}
        transport = AsyncMock()
        transport.request = AsyncMock(return_value=expected)
        cmd = EvalDatasetCreateCommand(transport)
        result = await cmd.execute(name="eval-ds", source="corpus1")
        assert result == expected
