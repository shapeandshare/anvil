# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for ExperimentArtifactsCommand — GET with experiment + run IDs."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from anvil.client._shared.http_method import HttpMethod
from anvil.client.experiments.experiment_artifacts_command import (
    ExperimentArtifactsCommand,
)


class TestExperimentArtifactsCommand:
    """ExperimentArtifactsCommand: GET /v1/experiments/{eid}/runs/{rid}/artifacts."""

    @pytest.mark.asyncio
    async def test_execute_calls_transport_with_get(self) -> None:
        transport = AsyncMock()
        transport.request = AsyncMock(return_value={"files": []})
        cmd = ExperimentArtifactsCommand(transport)
        result = await cmd.execute(experiment_id="exp1", run_id="run1")
        transport.request.assert_called_once()
        args, _ = transport.request.call_args
        assert args[0] == HttpMethod.GET
        assert args[1] == "/v1/experiments/exp1/runs/run1/artifacts"

    @pytest.mark.asyncio
    async def test_execute_returns_transport_result(self) -> None:
        expected = {"files": ["model.pt"]}
        transport = AsyncMock()
        transport.request = AsyncMock(return_value=expected)
        cmd = ExperimentArtifactsCommand(transport)
        result = await cmd.execute(experiment_id="exp1", run_id="run1")
        assert result == expected
