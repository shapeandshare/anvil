# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for ContentVersionTagCommand — POST with version_id + tag."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from anvil.client._shared.http_method import HttpMethod
from anvil.client.content.content_version_tag_command import ContentVersionTagCommand


class TestContentVersionTagCommand:
    """ContentVersionTagCommand: POST /v1/content/versions/{id}/tag."""

    @pytest.mark.asyncio
    async def test_execute_calls_transport_with_post(self) -> None:
        transport = AsyncMock()
        transport.request = AsyncMock(return_value={"version_id": 1})
        cmd = ContentVersionTagCommand(transport)
        result = await cmd.execute(version_id=1, tag="production")
        transport.request.assert_called_once()
        args, kwargs = transport.request.call_args
        assert args[0] == HttpMethod.POST
        assert args[1] == "/v1/content/versions/1/tag"
        assert kwargs["json"] == {"tag": "production"}

    @pytest.mark.asyncio
    async def test_execute_returns_transport_result(self) -> None:
        expected = {"version_id": 1, "tag": "production"}
        transport = AsyncMock()
        transport.request = AsyncMock(return_value=expected)
        cmd = ContentVersionTagCommand(transport)
        result = await cmd.execute(version_id=1, tag="production")
        assert result == expected
