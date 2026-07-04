# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for ExperimentDownloadCommand — GET download with optional dest."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from anvil.client.experiments.experiment_download_command import (
    ExperimentDownloadCommand,
)


class TestExperimentDownloadCommand:
    """ExperimentDownloadCommand: GET /v1/experiments/{eid}/runs/{rid}/download."""

    @pytest.mark.asyncio
    async def test_execute_without_dest_calls_download(self) -> None:
        transport = AsyncMock()
        transport.download = AsyncMock(return_value=b"content")
        cmd = ExperimentDownloadCommand(transport)
        result = await cmd.execute(experiment_id="exp1", run_id="run1", path="model.pt")
        transport.download.assert_called_once()
        args, kwargs = transport.download.call_args
        assert args[0] == "/v1/experiments/exp1/runs/run1/download"
        assert kwargs["params"] == {"path": "model.pt"}
        assert kwargs.get("dest") is None

    @pytest.mark.asyncio
    async def test_execute_with_dest(self) -> None:
        transport = AsyncMock()
        transport.download = AsyncMock(return_value=Path("/tmp/out.pt"))
        cmd = ExperimentDownloadCommand(transport)
        result = await cmd.execute(
            experiment_id="exp1", run_id="run1", path="model.pt", dest="/tmp/out.pt"
        )
        _, kwargs = transport.download.call_args
        assert kwargs["dest"] == Path("/tmp/out.pt")

    @pytest.mark.asyncio
    async def test_execute_returns_bytes(self) -> None:
        transport = AsyncMock()
        transport.download = AsyncMock(return_value=b"binary data")
        cmd = ExperimentDownloadCommand(transport)
        result = await cmd.execute(experiment_id="exp1", run_id="run1", path="model.pt")
        assert result == b"binary data"

    @pytest.mark.asyncio
    async def test_execute_with_dest_returns_path_string(self) -> None:
        transport = AsyncMock()
        transport.download = AsyncMock(return_value=Path("/tmp/out.pt"))
        cmd = ExperimentDownloadCommand(transport)
        result = await cmd.execute(
            experiment_id="exp1", run_id="run1", path="model.pt", dest="/tmp/out.pt"
        )
        assert result == "/tmp/out.pt"
