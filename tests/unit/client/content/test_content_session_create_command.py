# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for ContentSessionCreateCommand — POST with required + optional params."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from anvil.client._shared.http_method import HttpMethod
from anvil.client.content.content_session_create_command import (
    ContentSessionCreateCommand,
)


class TestContentSessionCreateCommand:
    """ContentSessionCreateCommand: POST /v1/content/sessions."""

    @pytest.mark.asyncio
    async def test_execute_calls_transport_with_post(self) -> None:
        transport = AsyncMock()
        transport.request = AsyncMock(return_value={"id": 1})
        cmd = ContentSessionCreateCommand(transport)
        result = await cmd.execute(corpus_id=1)
        transport.request.assert_called_once()
        args, kwargs = transport.request.call_args
        assert args[0] == HttpMethod.POST
        assert args[1] == "/v1/content/sessions"
        assert kwargs["json"] == {"corpus_id": 1}

    @pytest.mark.asyncio
    async def test_execute_with_name(self) -> None:
        transport = AsyncMock()
        transport.request = AsyncMock(return_value={"id": 2})
        cmd = ContentSessionCreateCommand(transport)
        result = await cmd.execute(corpus_id=1, name="My Session")
        _, kwargs = transport.request.call_args
        assert kwargs["json"] == {"corpus_id": 1, "name": "My Session"}

    @pytest.mark.asyncio
    async def test_execute_returns_transport_result(self) -> None:
        expected = {"id": 1, "corpus_id": 1}
        transport = AsyncMock()
        transport.request = AsyncMock(return_value=expected)
        cmd = ContentSessionCreateCommand(transport)
        result = await cmd.execute(corpus_id=1)
        assert result == expected
