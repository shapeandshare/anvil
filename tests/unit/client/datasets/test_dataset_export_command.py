# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for DatasetExportCommand — GET download with optional params."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from anvil.client.datasets.dataset_export_command import DatasetExportCommand


class TestDatasetExportCommand:
    """DatasetExportCommand: GET /v1/datasets/{id}/export?format=."""

    @pytest.mark.asyncio
    async def test_execute_without_dest_calls_download(self) -> None:
        transport = AsyncMock()
        transport.download = AsyncMock(return_value=b"content")
        cmd = DatasetExportCommand(transport)
        result = await cmd.execute(dataset_id=1)
        transport.download.assert_called_once()
        args, kwargs = transport.download.call_args
        assert args[0] == "/v1/datasets/1/export"
        assert kwargs["params"] == {"format": "txt"}
        assert kwargs.get("dest") is None

    @pytest.mark.asyncio
    async def test_execute_with_dest(self) -> None:
        transport = AsyncMock()
        transport.download = AsyncMock(return_value=Path("/tmp/out.txt"))
        cmd = DatasetExportCommand(transport)
        result = await cmd.execute(dataset_id=1, dest="/tmp/out.txt")
        transport.download.assert_called_once()
        _, kwargs = transport.download.call_args
        assert kwargs["dest"] == Path("/tmp/out.txt")

    @pytest.mark.asyncio
    async def test_execute_with_custom_format(self) -> None:
        transport = AsyncMock()
        transport.download = AsyncMock(return_value=b"content")
        cmd = DatasetExportCommand(transport)
        result = await cmd.execute(dataset_id=1, fmt="jsonl")
        _, kwargs = transport.download.call_args
        assert kwargs["params"] == {"format": "jsonl"}

    @pytest.mark.asyncio
    async def test_execute_returns_bytes(self) -> None:
        transport = AsyncMock()
        transport.download = AsyncMock(return_value=b"raw data")
        cmd = DatasetExportCommand(transport)
        result = await cmd.execute(dataset_id=1)
        assert result == b"raw data"

    @pytest.mark.asyncio
    async def test_execute_with_dest_returns_path_string(self) -> None:
        transport = AsyncMock()
        transport.download = AsyncMock(return_value=Path("/tmp/out.txt"))
        cmd = DatasetExportCommand(transport)
        result = await cmd.execute(dataset_id=1, dest="/tmp/out.txt")
        assert result == "/tmp/out.txt"
