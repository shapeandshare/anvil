# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for ContentSessionValidateCommand — POST with required session_id."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from anvil.client._shared.http_method import HttpMethod
from anvil.client.content.content_session_validate_command import (
    ContentSessionValidateCommand,
)


class TestContentSessionValidateCommand:
    """ContentSessionValidateCommand: POST /v1/content/sessions/{id}/validate."""

    @pytest.mark.asyncio
    async def test_execute_calls_transport_with_post(self) -> None:
        transport = AsyncMock()
        transport.request = AsyncMock(return_value={"valid": True})
        cmd = ContentSessionValidateCommand(transport)
        result = await cmd.execute(session_id=1)
        transport.request.assert_called_once()
        args, _ = transport.request.call_args
        assert args[0] == HttpMethod.POST
        assert args[1] == "/v1/content/sessions/1/validate"

    @pytest.mark.asyncio
    async def test_execute_returns_transport_result(self) -> None:
        expected = {"valid": True, "issues": []}
        transport = AsyncMock()
        transport.request = AsyncMock(return_value=expected)
        cmd = ContentSessionValidateCommand(transport)
        result = await cmd.execute(session_id=1)
        assert result == expected
