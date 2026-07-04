# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for DownloadStatusCommand — GET with model_id + job_id."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from anvil.client._shared.http_method import HttpMethod
from anvil.client.models.download_status_command import DownloadStatusCommand


class TestDownloadStatusCommand:
    """DownloadStatusCommand: GET /v1/models/{model_id}/download/{job_id}/status."""

    @pytest.mark.asyncio
    async def test_execute_calls_transport_with_get(self) -> None:
        transport = AsyncMock()
        transport.request = AsyncMock(return_value={"status": "running"})
        cmd = DownloadStatusCommand(transport)
        result = await cmd.execute(model_id=1, job_id=5)
        transport.request.assert_called_once()
        args, _ = transport.request.call_args
        assert args[0] == HttpMethod.GET
        assert args[1] == "/v1/models/1/download/5/status"

    @pytest.mark.asyncio
    async def test_execute_returns_transport_result(self) -> None:
        expected = {"status": "completed", "total_assets": 3}
        transport = AsyncMock()
        transport.request = AsyncMock(return_value=expected)
        cmd = DownloadStatusCommand(transport)
        result = await cmd.execute(model_id=1, job_id=5)
        assert result == expected
