# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for DownloadAssetsCommand — POST with required model_id."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from anvil.client._shared.http_method import HttpMethod
from anvil.client.models.download_assets_command import DownloadAssetsCommand


class TestDownloadAssetsCommand:
    """DownloadAssetsCommand: POST /v1/models/{model_id}/download."""

    @pytest.mark.asyncio
    async def test_execute_calls_transport_with_post(self) -> None:
        transport = AsyncMock()
        transport.request = AsyncMock(return_value={"job_id": 1})
        cmd = DownloadAssetsCommand(transport)
        result = await cmd.execute(model_id=1)
        transport.request.assert_called_once()
        args, _ = transport.request.call_args
        assert args[0] == HttpMethod.POST
        assert args[1] == "/v1/models/1/download"

    @pytest.mark.asyncio
    async def test_execute_returns_transport_result(self) -> None:
        expected = {"job_id": 1, "status": "started"}
        transport = AsyncMock()
        transport.request = AsyncMock(return_value=expected)
        cmd = DownloadAssetsCommand(transport)
        result = await cmd.execute(model_id=1)
        assert result == expected
