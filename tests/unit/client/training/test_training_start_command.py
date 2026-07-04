# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for TrainingStartCommand — POST with TrainingConfig body."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from anvil.client._shared.http_method import HttpMethod
from anvil.client.training.training_config import TrainingConfig
from anvil.client.training.training_start_command import TrainingStartCommand


class TestTrainingStartCommand:
    """TrainingStartCommand: POST /v1/training/start."""

    @pytest.mark.asyncio
    async def test_execute_calls_transport_with_post(self) -> None:
        transport = AsyncMock()
        transport.request = AsyncMock(
            return_value={
                "run_id": "run1",
                "mlflow_run_id": "m1",
                "experiment_id": "e1",
            }
        )
        config = TrainingConfig()
        cmd = TrainingStartCommand(transport)
        result = await cmd.execute(config=config)
        transport.request.assert_called_once()
        args, kwargs = transport.request.call_args
        assert args[0] == HttpMethod.POST
        assert args[1] == "/v1/training/start"
        assert kwargs["json"] == config.model_dump()

    @pytest.mark.asyncio
    async def test_execute_returns_transport_result(self) -> None:
        expected = {
            "run_id": "run1",
            "mlflow_run_id": "m1",
            "experiment_id": "e1",
        }
        transport = AsyncMock()
        transport.request = AsyncMock(return_value=expected)
        cmd = TrainingStartCommand(transport)
        config = TrainingConfig()
        result = await cmd.execute(config=config)
        assert result == expected
