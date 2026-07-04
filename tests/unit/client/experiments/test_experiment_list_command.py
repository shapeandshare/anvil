# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for ExperimentListCommand — no-arg GET returning list."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from anvil.client._shared.http_method import HttpMethod
from anvil.client.experiments.experiment_list_command import ExperimentListCommand


class TestExperimentListCommand:
    """ExperimentListCommand: GET /v1/experiments → list."""

    @pytest.mark.asyncio
    async def test_execute_calls_transport_with_get(self) -> None:
        transport = AsyncMock()
        transport.request = AsyncMock(return_value=[])
        cmd = ExperimentListCommand(transport)
        result = await cmd.execute()
        transport.request.assert_called_once()
        args, _ = transport.request.call_args
        assert args[0] == HttpMethod.GET
        assert args[1] == "/v1/experiments"

    @pytest.mark.asyncio
    async def test_execute_returns_transport_result(self) -> None:
        expected = [{"id": "exp1"}]
        transport = AsyncMock()
        transport.request = AsyncMock(return_value=expected)
        cmd = ExperimentListCommand(transport)
        result = await cmd.execute()
        assert result == expected
