# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for TrainingStreamCommand — SSE stream with run_id."""

from __future__ import annotations

from collections.abc import AsyncIterator
from unittest.mock import MagicMock

import pytest

from anvil.client.training.training_stream_command import TrainingStreamCommand


class TestTrainingStreamCommand:
    """TrainingStreamCommand: GET /v1/training/stream/{run_id}."""

    @pytest.mark.asyncio
    async def test_execute_calls_transport_stream_sse(self) -> None:
        transport = MagicMock()
        transport.stream_sse = MagicMock(return_value=MagicMock(spec=AsyncIterator))
        cmd = TrainingStreamCommand(transport)
        result = await cmd.execute(run_id="run1")
        transport.stream_sse.assert_called_once_with(
            "/v1/training/stream/run1",
        )

    @pytest.mark.asyncio
    async def test_execute_returns_transport_stream(self) -> None:
        expected = MagicMock(spec=AsyncIterator)
        transport = MagicMock()
        transport.stream_sse = MagicMock(return_value=expected)
        cmd = TrainingStreamCommand(transport)
        result = await cmd.execute(run_id="run1")
        assert result is expected
