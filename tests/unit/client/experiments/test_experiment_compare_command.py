# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for ExperimentCompareCommand — GET with variadic IDs."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from anvil.client._shared.http_method import HttpMethod
from anvil.client.experiments.experiment_compare_command import ExperimentCompareCommand


class TestExperimentCompareCommand:
    """ExperimentCompareCommand: GET /v1/experiments/compare?id=..."""

    @pytest.mark.asyncio
    async def test_execute_calls_transport_with_get(self) -> None:
        transport = AsyncMock()
        transport.request = AsyncMock(return_value={})
        cmd = ExperimentCompareCommand(transport)
        result = await cmd.execute("exp1", "exp2")
        transport.request.assert_called_once()
        args, kwargs = transport.request.call_args
        assert args[0] == HttpMethod.GET
        assert args[1] == "/v1/experiments/compare"
        assert kwargs["params"] == {"id": ["exp1", "exp2"]}

    @pytest.mark.asyncio
    async def test_execute_with_single_id(self) -> None:
        transport = AsyncMock()
        transport.request = AsyncMock(return_value={})
        cmd = ExperimentCompareCommand(transport)
        result = await cmd.execute("exp1")
        _, kwargs = transport.request.call_args
        assert kwargs["params"] == {"id": ["exp1"]}

    @pytest.mark.asyncio
    async def test_execute_returns_transport_result(self) -> None:
        expected = {"exp1": {}, "exp2": {}}
        transport = AsyncMock()
        transport.request = AsyncMock(return_value=expected)
        cmd = ExperimentCompareCommand(transport)
        result = await cmd.execute("exp1", "exp2")
        assert result == expected
