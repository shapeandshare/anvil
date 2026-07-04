# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for TrainingStopCommand — POST with required run_id."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from anvil.client._shared.http_method import HttpMethod
from anvil.client.training.training_stop_command import TrainingStopCommand


class TestTrainingStopCommand:
    """TrainingStopCommand: POST /v1/training/{run_id}/stop."""

    @pytest.mark.asyncio
    async def test_execute_calls_transport_with_post(self) -> None:
        transport = AsyncMock()
        transport.request = AsyncMock(return_value={"stopped": True})
        cmd = TrainingStopCommand(transport)
        result = await cmd.execute(run_id="run1")
        transport.request.assert_called_once()
        args, _ = transport.request.call_args
        assert args[0] == HttpMethod.POST
        assert args[1] == "/v1/training/run1/stop"

    @pytest.mark.asyncio
    async def test_execute_returns_transport_result(self) -> None:
        expected = {"stopped": True}
        transport = AsyncMock()
        transport.request = AsyncMock(return_value=expected)
        cmd = TrainingStopCommand(transport)
        result = await cmd.execute(run_id="run1")
        assert result == expected
