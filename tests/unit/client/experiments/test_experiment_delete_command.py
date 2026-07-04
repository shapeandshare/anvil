# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for ExperimentDeleteCommand — DELETE with required ID param."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from anvil.client._shared.http_method import HttpMethod
from anvil.client.experiments.experiment_delete_command import ExperimentDeleteCommand


class TestExperimentDeleteCommand:
    """ExperimentDeleteCommand: DELETE /v1/experiments/{id}."""

    @pytest.mark.asyncio
    async def test_execute_calls_transport_with_delete(self) -> None:
        transport = AsyncMock()
        transport.request = AsyncMock(return_value={"deleted": True})
        cmd = ExperimentDeleteCommand(transport)
        result = await cmd.execute(experiment_id="exp1")
        transport.request.assert_called_once()
        args, _ = transport.request.call_args
        assert args[0] == HttpMethod.DELETE
        assert args[1] == "/v1/experiments/exp1"

    @pytest.mark.asyncio
    async def test_execute_returns_transport_result(self) -> None:
        expected = {"deleted": True}
        transport = AsyncMock()
        transport.request = AsyncMock(return_value=expected)
        cmd = ExperimentDeleteCommand(transport)
        result = await cmd.execute(experiment_id="exp1")
        assert result == expected
