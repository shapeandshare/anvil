# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for DatasetUploadCommand — POST with files."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from anvil.client._shared.http_method import HttpMethod
from anvil.client.datasets.dataset_upload_command import DatasetUploadCommand


class TestDatasetUploadCommand:
    """DatasetUploadCommand: POST /v1/datasets/upload."""

    @pytest.mark.asyncio
    async def test_execute_calls_transport_with_post(self) -> None:
        transport = AsyncMock()
        transport.request = AsyncMock(return_value={"uploaded": True})
        cmd = DatasetUploadCommand(transport)
        with (
            patch("anvil.client.datasets.dataset_upload_command.aiofiles") as af,
            patch("pathlib.Path.name", new_callable=lambda: "test.txt"),
        ):
            af.open.return_value.__aenter__.return_value.read.return_value = (
                b"file content"
            )
            result = await cmd.execute(dataset_id=1, file_path="/path/test.txt")
        transport.request.assert_called_once()
        args, kwargs = transport.request.call_args
        assert args[0] == HttpMethod.POST
        assert args[1] == "/v1/datasets/upload"
        assert "files" in kwargs

    @pytest.mark.asyncio
    async def test_execute_returns_transport_result(self) -> None:
        expected = {"uploaded": True, "dataset_id": 1}
        transport = AsyncMock()
        transport.request = AsyncMock(return_value=expected)
        cmd = DatasetUploadCommand(transport)
        with patch("anvil.client.datasets.dataset_upload_command.aiofiles") as af:
            af.open.return_value.__aenter__.return_value.read.return_value = b"data"
            result = await cmd.execute(dataset_id=1, file_path="/p/f.txt")
        assert result == expected

    @pytest.mark.asyncio
    async def test_execute_raises_when_aiofiles_missing(self) -> None:
        transport = AsyncMock()
        cmd = DatasetUploadCommand(transport)
        with patch("anvil.client.datasets.dataset_upload_command.aiofiles", None):
            with pytest.raises(ImportError, match="aiofiles"):
                await cmd.execute(dataset_id=1, file_path="/p/f.txt")
