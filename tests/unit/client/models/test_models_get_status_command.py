# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for ModelsGetStatusCommand — GET with required job_id."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from anvil.client._shared.http_method import HttpMethod
from anvil.client.models.models_get_status_command import ModelsGetStatusCommand


class TestModelsGetStatusCommand:
    """ModelsGetStatusCommand: GET /v1/models/import/{job_id}/status."""

    @pytest.mark.asyncio
    async def test_execute_calls_transport_with_get(self) -> None:
        transport = AsyncMock()
        transport.request = AsyncMock(return_value={"status": "completed"})
        cmd = ModelsGetStatusCommand(transport)
        result = await cmd.execute(job_id=1)
        transport.request.assert_called_once()
        args, _ = transport.request.call_args
        assert args[0] == HttpMethod.GET
        assert args[1] == "/v1/models/import/1/status"

    @pytest.mark.asyncio
    async def test_execute_returns_transport_result(self) -> None:
        expected = {"status": "completed", "external_model_id": 42}
        transport = AsyncMock()
        transport.request = AsyncMock(return_value=expected)
        cmd = ModelsGetStatusCommand(transport)
        result = await cmd.execute(job_id=1)
        assert result == expected
