# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for TrainingStatusCommand — GET with required run_id."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from anvil.client._shared.http_method import HttpMethod
from anvil.client.training.training_status_command import TrainingStatusCommand


class TestTrainingStatusCommand:
    """TrainingStatusCommand: GET /v1/training/{run_id}/status."""

    @pytest.mark.asyncio
    async def test_execute_calls_transport_with_get(self) -> None:
        transport = AsyncMock()
        transport.request = AsyncMock(return_value={"status": "running", "step": 42})
        cmd = TrainingStatusCommand(transport)
        result = await cmd.execute(run_id="run1")
        transport.request.assert_called_once()
        args, _ = transport.request.call_args
        assert args[0] == HttpMethod.GET
        assert args[1] == "/v1/training/run1/status"

    @pytest.mark.asyncio
    async def test_execute_returns_transport_result(self) -> None:
        expected = {"status": "completed", "loss": 0.5}
        transport = AsyncMock()
        transport.request = AsyncMock(return_value=expected)
        cmd = TrainingStatusCommand(transport)
        result = await cmd.execute(run_id="run1")
        assert result == expected
